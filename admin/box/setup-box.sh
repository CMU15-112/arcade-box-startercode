#!/bin/bash
# Configure the arcade box from the files in this repo. Runs ON the box as `es`;
# admin/install.sh copies the admin/ folder over and calls it.
#
#   setup-box.sh           apply everything (idempotent: unchanged things are left alone)
#   setup-box.sh --check   report what would change, change nothing
#
# Assumes Ubuntu 22.04 Desktop with the user `es`. Builds EmulationStation via
# RetroPie-Setup if it isn't installed yet.
set -euo pipefail

BOX="$(cd "$(dirname "$0")" && pwd)"
ADMIN="$(dirname "$BOX")"
STAMP="$(date +%Y%m%d-%H%M%S)"
CHECK=0
[[ "${1:-}" == "--check" ]] && CHECK=1

ES_BIN=/opt/retropie/supplementary/emulationstation/emulationstation
RPS="$HOME/RetroPie-Setup"
ES_CFG=/opt/retropie/configs/all/emulationstation
ES_SYSTEMS=/etc/emulationstation/es_systems.cfg
MERGE="python3 $BOX/merge-config.py"

CHANGES=0
REBOOT_REASONS=()
ES_NEEDS_RESTART=0
UDEV_CHANGED=0
FONTS_CHANGED=0
SYSTEMD_CHANGED=0
BUTTON_CHANGED=0
DEPLOY_CHANGED=0

say()     { printf '%s\n' "$*"; }
status()  { printf '  %-10s %s\n' "$1" "$2"; }
changed() { CHANGES=$((CHANGES + 1)); status "$([[ $CHECK == 1 ]] && echo WOULD || echo CHANGED)" "$1"; }
ok()      { status "ok" "$1"; }
section() { printf '\n== %s ==\n' "$1"; }

if [[ "$(id -un)" != "es" ]]; then
    say "setup-box.sh must run as the user 'es' (it is running as $(id -un))." >&2
    exit 1
fi
if ! grep -q 'VERSION_ID="22.04"' /etc/os-release; then
    say "WARNING: this box isn't Ubuntu 22.04; setup has only been tested there."
fi
if [[ $CHECK == 0 ]]; then
    # Ask for the password up front on a fresh box (before the sudoers drop-in exists).
    sudo -n true 2>/dev/null || sudo true
fi

# ---------------------------------------------------------------------------
section "apt packages"
missing=()
while read -r pkg; do
    [[ -z "$pkg" || "$pkg" == \#* ]] && continue
    dpkg-query -W -f='${Status}' "$pkg" 2>/dev/null | grep -q "install ok installed" || missing+=("$pkg")
done < "$BOX/packages.txt"
if [[ ${#missing[@]} -eq 0 ]]; then
    ok "all packages in packages.txt are installed"
else
    changed "install: ${missing[*]}"
    if [[ $CHECK == 0 ]]; then
        sudo apt-get update
        sudo DEBIAN_FRONTEND=noninteractive apt-get install -y "${missing[@]}"
    fi
fi

# ---------------------------------------------------------------------------
section "user groups"
for grp in dialout plugdev; do
    if id -nG es | tr ' ' '\n' | grep -qx "$grp"; then
        ok "es is in $grp"
    else
        changed "add es to $grp"
        REBOOT_REASONS+=("group membership")
        [[ $CHECK == 0 ]] && sudo usermod -aG "$grp" es
    fi
done

# ---------------------------------------------------------------------------
section "EmulationStation"
if [[ -x "$ES_BIN" ]]; then
    ok "EmulationStation is installed"
else
    changed "build EmulationStation from source with RetroPie-Setup (takes a while)"
    if [[ $CHECK == 0 ]]; then
        [[ -d "$RPS" ]] || git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git "$RPS"
        sudo "$RPS/retropie_packages.sh" emulationstation
        [[ -x "$ES_BIN" ]] || { say "EmulationStation build failed; see the output above." >&2; exit 1; }
    fi
    REBOOT_REASONS+=("EmulationStation was just installed")
fi
if [[ -d /etc/emulationstation/themes/carbon-2021 ]]; then
    ok "carbon-2021 theme is installed"
else
    changed "install the carbon-2021 theme"
    if [[ $CHECK == 0 ]]; then
        [[ -d "$RPS" ]] || git clone --depth=1 https://github.com/RetroPie/RetroPie-Setup.git "$RPS"
        sudo "$RPS/retropie_packages.sh" esthemes install_theme carbon-2021 RetroPie
    fi
fi

# ---------------------------------------------------------------------------
section "directories"
for d in "$HOME/RetroPie/roms/cmu_graphics" "$HOME/stuff/frozen"; do
    if [[ -d "$d" ]]; then ok "$d"; else changed "create $d"; [[ $CHECK == 0 ]] && mkdir -p "$d"; fi
done

# ---------------------------------------------------------------------------
section "launcher and arcade-admin"
deploy() {   # deploy SRC DEST MODE   (sets DEPLOY_CHANGED=1 if DEST changed)
    local src="$1" dest="$2" mode="$3"
    DEPLOY_CHANGED=0
    if [[ -f "$dest" ]] && cmp -s "$src" "$dest"; then
        ok "$dest"
        return
    fi
    changed "$dest"
    DEPLOY_CHANGED=1
    if [[ $CHECK == 0 ]]; then
        [[ -f "$dest" ]] && cp -p "$dest" "$dest.bak-$STAMP"
        install -D -m "$mode" "$src" "$dest"
    fi
}
deploy "$ADMIN/112.sh" "$HOME/stuff/112.sh" 755
deploy "$ADMIN/arcade-admin" "$HOME/stuff/arcade-admin" 755
deploy "$ADMIN/arcade-button" "$HOME/stuff/arcade-button" 755
BUTTON_CHANGED=$DEPLOY_CHANGED
if [[ "$(readlink /usr/local/bin/arcade-admin 2>/dev/null)" == "$HOME/stuff/arcade-admin" ]]; then
    ok "/usr/local/bin/arcade-admin -> ~/stuff/arcade-admin"
else
    changed "link /usr/local/bin/arcade-admin"
    [[ $CHECK == 0 ]] && sudo ln -sf "$HOME/stuff/arcade-admin" /usr/local/bin/arcade-admin
fi

# ---------------------------------------------------------------------------
section "config files"
# Everything under box/files/ is installed at the same path on the box.
# Ownership: es for /home/es and /opt/retropie/configs, root elsewhere.
# Mode: 0440 in sudoers.d, 0755 if executable in the repo, else 0644.
es_running() { [[ -n "$(es_pid)" ]]; }
es_pid() {
    local p
    for p in /proc/[0-9]*; do
        [[ "$(readlink "$p/exe" 2>/dev/null)" == "$ES_BIN" ]] && { basename "$p"; return; }
    done
    return 0
}
ES_WAS_STOPPED=0

# ES rewrites its own config files, so it must be closed while they change.
# es_systems.cfg is only read at startup, so it just needs a restart afterwards.
es_files_differ=0
while IFS= read -r -d '' src; do
    dest="/${src#"$BOX/files/"}"
    [[ "$dest" == "$ES_CFG/"* ]] && ! cmp -s "$src" "$dest" 2>/dev/null && es_files_differ=1
done < <(find "$BOX/files" -type f -print0)
if [[ $CHECK == 0 && $es_files_differ == 1 ]] && es_running; then
    say "  (closing EmulationStation while its config files are replaced)"
    arcade-admin stop-es >/dev/null 2>&1 || "$ADMIN/arcade-admin" stop-es
    ES_WAS_STOPPED=1
fi

while IFS= read -r -d '' src; do
    rel="${src#"$BOX/files/"}"
    dest="/$rel"
    case "$dest" in
        /home/es/*|/opt/retropie/configs/*) owner=es ;;
        *) owner=root ;;
    esac
    if [[ "$dest" == /etc/sudoers.d/* ]]; then mode=0440
    elif [[ -x "$src" ]]; then mode=0755
    else mode=0644; fi

    if sudo test -f "$dest" && sudo cmp -s "$src" "$dest"; then
        ok "$dest"
        continue
    fi
    changed "$dest"
    case "$dest" in
        "$ES_CFG"/*) ES_NEEDS_RESTART=1 ;;
        /etc/udev/*) UDEV_CHANGED=1 ;;
        /home/es/.fonts/*) FONTS_CHANGED=1 ;;
        /etc/systemd/*) SYSTEMD_CHANGED=1 ;;
    esac
    [[ $CHECK == 1 ]] && continue
    if [[ "$dest" == /etc/sudoers.d/* ]] && ! sudo visudo -cqf "$src"; then
        say "  refusing to install $dest: visudo says it's invalid" >&2
        continue
    fi
    sudo test -f "$dest" && sudo cp -p "$dest" "$dest.bak-$STAMP"
    sudo install -D -o "$owner" -g "$owner" -m "$mode" "$src" "$dest"
done < <(find "$BOX/files" -type f -print0 | sort -z)

# ---------------------------------------------------------------------------
section "system config merges"
merge() {   # merge DESCRIPTION ARGS...
    local desc="$1"; shift
    local rc=0
    if [[ $CHECK == 1 ]]; then
        sudo $MERGE --check "$@" || rc=$?
    else
        sudo $MERGE "$@" || rc=$?
    fi
    case $rc in
        0) ok "$desc" ;;
        1) changed "$desc"; return 1 ;;
        *) say "  merge-config.py failed for: $desc" >&2; exit 1 ;;
    esac
}
merge "$ES_SYSTEMS: '112' system entry" es-system "$BOX/es_system_112.xml" || ES_NEEDS_RESTART=1
merge "/etc/gdm3/custom.conf: auto-login as es" gdm-autologin es || REBOOT_REASONS+=("GDM auto-login")
merge "AccountsService: es logs into the openbox session" session es openbox || REBOOT_REASONS+=("login session")

# ---------------------------------------------------------------------------
section "reset button service"
# arcade-button listens to the RP2040 reset button (admin/pico/) and restarts ES.
UNIT=arcade-button.service
[[ $CHECK == 0 && $SYSTEMD_CHANGED == 1 ]] && sudo systemctl daemon-reload
if systemctl is-enabled -q "$UNIT" 2>/dev/null && systemctl is-active -q "$UNIT"; then
    if [[ $BUTTON_CHANGED == 1 || $SYSTEMD_CHANGED == 1 ]]; then
        if [[ $CHECK == 0 ]]; then
            sudo systemctl restart "$UNIT"
            status "done" "restarted $UNIT"
        else
            status "WOULD" "restart $UNIT"
        fi
    else
        ok "$UNIT is enabled and running"
    fi
else
    changed "enable and start $UNIT"
    [[ $CHECK == 0 ]] && sudo systemctl enable --now "$UNIT"
fi

# ---------------------------------------------------------------------------
section "finishing up"
if [[ $CHECK == 0 ]]; then
    if [[ $UDEV_CHANGED == 1 ]]; then
        sudo udevadm control --reload-rules && sudo udevadm trigger
        status "done" "reloaded udev rules"
    fi
    if [[ $FONTS_CHANGED == 1 ]]; then
        fc-cache -f >/dev/null
        status "done" "refreshed the font cache"
    fi
    if [[ $ES_WAS_STOPPED == 1 ]]; then
        arcade-admin start-es
    elif [[ $ES_NEEDS_RESTART == 1 ]] && es_running; then
        arcade-admin restart-es
    fi
fi

say ""
if [[ $CHANGES == 0 ]]; then
    say "Everything already matches the repo."
elif [[ $CHECK == 1 ]]; then
    say "$CHANGES change(s) needed. Run without --check to apply them."
else
    say "Applied $CHANGES change(s). Backups of replaced files end in .bak-$STAMP"
fi
if [[ ${#REBOOT_REASONS[@]} -gt 0 && $CHECK == 0 ]]; then
    say "Reboot the box to finish (${REBOOT_REASONS[*]}):  sudo reboot"
fi
