#!/usr/bin/env python3
"""Idempotent edits to system config files that other software also owns.

Each subcommand makes the smallest change that gets the file into the desired
state, and only writes (after backing the file up) when something differs.
With --check it changes nothing and exits 1 if a change is needed.

    merge-config.py es-system SNIPPET.xml [--file /etc/emulationstation/es_systems.cfg]
    merge-config.py gdm-autologin USER
    merge-config.py session USER SESSION

Exit status: 0 = already correct, 1 = changed (or would change with --check).
"""

import argparse
import datetime
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

STAMP = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")


def write(path, text, check):
    if check:
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        shutil.copy2(path, path.with_name(f"{path.name}.bak-{STAMP}"))
    path.write_text(text)
    return 1


def es_system(snippet, file, check):
    """Insert or replace the <system> whose <name> matches the snippet's."""
    wanted = ET.parse(snippet).getroot()
    name = wanted.findtext("name")

    def fields(el):
        return {c.tag: (c.text or "").strip() for c in el}

    if file.exists():
        root = ET.parse(file).getroot()
    else:
        root = ET.Element("systemList")
    current = [s for s in root.findall("system") if s.findtext("name") == name]
    if len(current) == 1 and fields(current[0]) == fields(wanted):
        return 0
    for s in current:
        root.remove(s)
    root.insert(0, wanted)
    ET.indent(root, space="  ")
    return write(file, '<?xml version="1.0"?>\n' + ET.tostring(root, encoding="unicode") + "\n", check)


def ini_set(path, section, wanted, check, create_template=None):
    """Make the active keys in [section] equal `wanted` (dict), keeping comments
    and other keys. Commented-out copies of the keys are left alone."""
    if path.exists():
        lines = path.read_text().splitlines()
    elif create_template is not None:
        lines = create_template.splitlines()
    else:
        lines = []

    hdr = next((i for i, l in enumerate(lines) if l.strip() == f"[{section}]"), None)
    if hdr is None:
        lines += ["", f"[{section}]"] if lines else [f"[{section}]"]
        hdr = len(lines) - 1
    end = next((i for i in range(hdr + 1, len(lines)) if lines[i].lstrip().startswith("[")),
               len(lines))

    active = {}
    for i in range(hdr + 1, end):
        m = re.match(r"^\s*([A-Za-z0-9_-]+)\s*=\s*(.*?)\s*$", lines[i])
        if m:
            active.setdefault(m.group(1), []).append((i, m.group(2)))
    if path.exists() and all(
            len(active.get(k, [])) == 1 and active[k][0][1] == v for k, v in wanted.items()):
        return 0

    drop = {i for k in wanted for i, _ in active.get(k, [])}
    body = [l for i, l in enumerate(lines[hdr + 1:end], hdr + 1) if i not in drop]
    new = lines[:hdr + 1] + [f"{k}={v}" for k, v in wanted.items()] + body + lines[end:]
    return write(path, "\n".join(new) + "\n", check)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--check", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("es-system")
    a.add_argument("snippet", type=Path)
    a.add_argument("--file", type=Path, default=Path("/etc/emulationstation/es_systems.cfg"))
    g = sub.add_parser("gdm-autologin")
    g.add_argument("user")
    g.add_argument("--file", type=Path, default=Path("/etc/gdm3/custom.conf"))
    s = sub.add_parser("session")
    s.add_argument("user")
    s.add_argument("session")
    args = p.parse_args()

    if args.cmd == "es-system":
        rc = es_system(args.snippet, args.file, args.check)
    elif args.cmd == "gdm-autologin":
        rc = ini_set(args.file, "daemon",
                     {"AutomaticLoginEnable": "true", "AutomaticLogin": args.user}, args.check)
    else:
        rc = ini_set(Path(f"/var/lib/AccountsService/users/{args.user}"), "User",
                     {"Session": args.session}, args.check,
                     create_template="[User]\nSystemAccount=false")
    sys.exit(rc)


if __name__ == "__main__":
    main()
