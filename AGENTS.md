# AGENTS.md

This repo is the starter code for 15-112 students' arcade games (`main.py`, `joystick.py`, `Key-Map.md`) and the admin tooling for the physical **arcade box** that runs their term projects. Everything under `admin/` and `docs/` is about the box. Full admin docs are in [docs/ADMIN.md](docs/ADMIN.md); keep that file in sync with any change to the tooling.

## The box

- RetroPie/EmulationStation (ES) on Ubuntu 22.04, Python 3.10, user `es` with NOPASSWD sudo. Reach it with `ssh arcade` (the SSH config already has the user and keys). Auto-login goes into an openbox session, which runs ES in a maximized `gnome-terminal` (`~/.config/openbox/autostart`). `~/.config/openbox/rc.xml` (in `box/files/`) maximizes every window with no title bar.
- Each game is a git clone at `~/RetroPie/roms/cmu_graphics/<Name>.git`, launched by `~/stuff/112.sh %ROM%`. Each game has a semester tag (`git config arcade.semester "Fall 2026"` in its own repo). ES shows one system per semester, newest first, plus "Other" for untagged games. `arcade-admin sync-menu` builds these from the tags: it writes the systems at the top of `/etc/emulationstation/es_systems.cfg` (every system whose command is `112.sh` counts as its own), creates symlink folders in `~/RetroPie/roms/cmu_graphics-semesters/<semester>/`, and moves gamelist entries to `gamelists/<semester>/`. Every command that changes a game calls it. Lock files are `~/stuff/frozen/<Name>.git.txt` (pip requirements format, exact versions); `112.sh` runs a frozen game with its lock instead of `requirements.txt`, so working games keep working when packages update, and skips `git pull` for it.
- The `/home/es/...` paths, `/opt/retropie/...` paths and the `es` username are hard-coded throughout.
- `cmu-graphics` 3.x needs Python 3.11 or newer, so games on the system Python 3.10 get 1.1.44. Don't promise otherwise.
- Games run with `uv run --no-project --isolated --python <python> --with-requirements <lock or requirements.txt> python main.py` (`--with cmu-graphics` if a game has neither). There are no per-game venvs: uv keeps each environment in `~/.cache/uv`, so never prune or clean that cache casually (`arcade-admin prepare --all` rebuilds everything, with network). `--isolated` is required: without it the system's apt packages (PIL, cairo, sdl2) leak in. `arcade-admin`'s `deps_args()`/`uv_run()` must stay in step with `112.sh`. `<python>` is the game's `arcade.python` git config (set with `arcade-admin python GAME 3.14`; uv-managed Pythons, installed only by `uv python install`), else `/usr/bin/python3`. uv is `/usr/local/bin/uv`, pinned by `UV_VERSION` in `setup-box.sh`; `~/.config/uv/uv.toml` sets `python-downloads = "manual"` and `python-preference = "system"`. No `uv.lock`, `uv sync` or `uv pip install` into venvs.
- cmu-graphics 3 crashes on X11 when its window fills the screen (`Must set size of surface before calling present()`), so `112.sh` runs games on Python 3.11+ inside cage on Wayland (`WLR_BACKENDS=x11 cage -d -- ...`), nested in the X session. `/etc/apport/blacklist.d/cage` hides cage's occasional abort on shutdown.

## Repo layout (`admin/`)

| Path | Deployed to | What it is |
|---|---|---|
| `112.sh` | `~/stuff/112.sh` | The launcher: pull (unless frozen), then `uv run` `main.py` with the lock file or `requirements.txt`. |
| `arcade-admin` | `~/stuff/arcade-admin`, symlinked at `/usr/local/bin/arcade-admin` | SSH-only game manager (menu + subcommands). Single-file, stdlib-only Python 3. |
| `arcade-button` | `~/stuff/arcade-button` | Daemon for the reset button; run by `arcade-button.service`. Needs `python3-serial`. |
| `pico/boot.py`, `pico/code.py` | Copied by hand to the Pico's CIRCUITPY drive | Firmware for the RP2040 reset button. Not deployed by `install.sh`. |
| `box/` | via `install.sh` | Everything else that makes the box an arcade box: `packages.txt`, `files/` (installed at the same path on the box), `merge-config.py`, `setup-box.sh`. The ES systems for games come from `arcade-admin sync-menu`, not from a file. |
| `install.sh` | runs locally | Copies `admin/` to the box and runs `box/setup-box.sh`. Idempotent. |

Deploy and verify with `admin/install.sh --check` (report only) and `admin/install.sh`. After the box's own settings change, copy the file back into `admin/box/files/` so the repo stays the source of truth.

## Rules and constraints

- **`arcade-admin` is SSH-only.** The user does not want it reachable from the ES menu. Don't add it to `es_systems.cfg`, to `~/RetroPie/roms/`, or to anything named `*.git`.
- **ES is in Kiosk UI mode,** so there is no Quit menu. ES saves gamelists on exit, so edit `gamelist.xml` only while ES is stopped (`es_paused()` in `arcade-admin` does this).
- To kill ES, match the real binary `/opt/retropie/supplementary/emulationstation/emulationstation` by `/proc/*/exe`. Never `pkill -x emulationstation`, which also matches the wrapper script. The wrapper relaunches ES only if `/tmp/es-restart` exists.
- **Never run commands that kill processes by loose pattern over SSH.** An early `--force` matched any command line containing the `112.sh` path and killed the SSH session running the test. Match `LAUNCHER in argv[:2]` and exclude the tool's own ancestors (`_ancestors()`).
- Relaunching ES from SSH needs the X environment: `DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus XDG_RUNTIME_DIR=/run/user/1000`, run under `setsid`.
- The `es` user matches `%sudo`, so `sudo -v` asks for a password. Use `sudo -n true 2>/dev/null || sudo true`.
- `~/.local/bin` isn't on PATH for `ssh host cmd`; that's why tools are linked into `/usr/local/bin`.
- Private game repos use a per-repo deploy key and a `Host github-<id>` alias in `~/.ssh/config`. Public repos use HTTPS. Don't touch existing `id_rsa.*` keys or Host blocks.
- Back up before overwriting; the tools write `.bak-<timestamp>` files. Leave every game's working tree alone.
- Game names must match `^[A-Za-z0-9_-]+$`: `112.sh` does `cd $1` unquoted, so spaces break it (the "bee-game (demo)" folder is an existing victim).

## Testing

There's no test suite. Verify on the box:

1. `admin/install.sh --check`, then `admin/install.sh`. A second run must change nothing.
2. For game lifecycle changes, use a throwaway game such as `ZZ-Test` (add, semester, display-name, rename, disable/enable, remove), then confirm `~/.ssh/config`, `~/stuff/frozen/*`, `es_systems.cfg`, `~/RetroPie/roms/cmu_graphics-semesters/` and the gamelists match the baseline. `arcade-admin sync-menu --check` should report no changes.
3. Screenshot the arcade screen with `DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority import -window root -resize 400x300 /tmp/x.png`.
4. Reset button without hardware: run `arcade-button --port /dev/pts/N --dry-run`, or point it at a pty from a fake Pico (done with `systemd-run` as user `es`, as in the real service).
5. Check that no game is running (`pgrep -af stuff/112.sh`) before testing anything that restarts ES, since it closes the game on the arcade screen.

## Reset button

The Pico (`239a:80f4`, CircuitPython) sends `RESTART-ES` on its second USB serial port; `arcade-button` answers `ACK` and runs `arcade-admin --yes restart-es --force`. If no `ACK` arrives in 3 seconds, or the button is held for 5 seconds, the Pico types Alt+SysRq+REISUB. Logs: `journalctl -u arcade-button`.

- `boot.py` changes only take effect after the Pico is unplugged and replugged.
- In `code.py`, keep `DRY_RUN = False` and `HEARTBEAT = 0` in committed code. `DRY_RUN = True` is for testing on a laptop, where the real REISUB would reboot it.
- CircuitPython quirks: use `time.sleep`, not `sleep`; avoid `!r` in f-strings.
- If the CIRCUITPY drive mounts read-only with I/O errors, the FAT is corrupt (usually a copy cut short). Back up, run `storage.erase_filesystem()` in the REPL, copy `boot.py` and `code.py` back, reinstall `adafruit_hid` (`circup install adafruit_hid`), and `sync` before unplugging.

## Handout

`docs/instructions_on_arcade_box.tex` is the printed sign for the cabinet (landscape A4, one page). Build with `pdflatex docs/instructions_on_arcade_box.tex` from `docs/`. Keep it to one page and update rule 2 if the reset behavior changes.

## Known issues

- cmu-graphics 3.0.2's X11 crash with screen-sized windows is upstream's bug (CMU CS Academy); cage is a workaround. Joystick input inside cage hasn't been play-tested yet.
- Arcade-Box-Starter-Code and cmu_rush can't pull (deploy keys rejected).
- Professor-Invaders has local changes to its score files.
- `rename` leaves the old `<path>` entry in the semester gamelist, so the display name doesn't follow the game.
- The fresh-box path in `setup-box.sh` (building ES from source) has not been tested.

## Git

Work is on the `admin-tooling` branch (not merged or pushed). Make small, logical commits. Don't commit secrets or SSH keys.
