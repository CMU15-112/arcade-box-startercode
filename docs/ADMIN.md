# Arcade Box: Admin Guide

How to add, update, and remove student games on the arcade box. Students should read the main [README](../README.md) instead.

## `arcade-admin`

Day-to-day management goes through `arcade-admin`. It's a single Python script that runs on the box, and you use it over SSH:

```bash
ssh -t arcade arcade-admin          # interactive menu
ssh arcade arcade-admin list        # or run a single command
```

| Command | What it does |
|---|---|
| `list` | Lists every game with its display name, semester, enabled/disabled state, repo access (`https`, `alias:github-<id>`, or `ssh-default`), branch, frozen status, venv status, and play count. |
| `add URL [--name N] [--semester S] [--display "Pretty"] [--key-id ID] [--no-launch]` | Adds a game. See [Adding a game](#adding-a-game). |
| `semester GAME [S]` | Sets the semester the game is listed under, such as `"Fall 2026"`, `F26`, `S27` or `M27` (summer). See [Semesters](#semesters). |
| `sync-menu [--check]` | Rebuilds the per-semester menu entries from the games' tags. The other commands do this on their own; `install.sh` runs it too. |
| `launch GAME` | Test-launches the game on the arcade screen, the same way EmulationStation does. ES is closed during the launch and restarted afterwards. |
| `freeze GAME...` / `freeze --all` | Pins the game's currently installed packages and its code: a frozen game no longer pulls from GitHub. See [Frozen dependencies](#frozen-dependencies). |
| `unfreeze GAME` | Deletes the game's lock file, so it pulls on every launch again. |
| `display-name GAME "Name"` | Sets the name shown in the menu without renaming the folder. |
| `rename GAME NEWNAME` | Renames the folder, carries over the lock file and play count, and rebuilds the venv. |
| `disable GAME` / `enable GAME` | Hides a game from the menu, or shows it again. The files are kept in `~/RetroPie/roms/cmu_graphics-disabled/`. |
| `remove GAME` | Deletes the game and its lock file, and archives its deploy key to `~/.ssh/dead/` if no other game uses it. |
| `restart-es [--force]` | Restarts EmulationStation so its menu picks up changes. If a game is running, it refuses unless you pass `--force` (`-f`). `--force` kills the game (its `112.sh` launcher and everything it started) first, which is useful when a game has hung and has no working quit button. It also brings ES back if ES isn't running. |

`GAME` can be any unique prefix of the folder name, and matching ignores case.

A few things to know about how the tool behaves:

- **Confirmations.** Destructive steps ask before they act. `--yes` (`-y`) answers yes to every question, for scripting. `remove` asks you to type the game's name.
- **The arcade screen.** Some commands briefly close EmulationStation on the arcade screen: anything that changes the menu (adding, removing, renaming, enabling or disabling a game, or changing its semester or display name) and test launches. The tool asks first, refuses while a game is being played, and relaunches ES afterwards.
- **Backups.** Before any write, `~/.ssh/config`, `es_systems.cfg` and `gamelist.xml` are backed up next to the original as `*.bak-<timestamp>`.
- **SSH only.** The tool isn't reachable from the EmulationStation menu.

There are also `stop-es [--force]` and `start-es` commands. `install.sh` uses them.

A hung game can be cleared over SSH with `arcade-admin restart-es --force`. In the menu, choosing "Restart EmulationStation" while a game is running asks whether to kill the game. The cabinet's reset button does the same thing; see the next section.

## The reset button

The external button is wired to GP15 of a Raspberry Pi Pico (RP2040) running CircuitPython. The Pico is plugged into the box by USB.

| What you do | What happens |
|---|---|
| Press the button | The Pico asks the box to restart EmulationStation. The box runs `arcade-admin --yes restart-es --force`, which kills any running game. The Pico's LED blinks once the box has answered. Presses within 10 seconds of a restart are ignored. |
| The box doesn't answer within 3 seconds | The Pico falls back to a hard reboot. It types Alt+SysRq+R,E,I,S,U,B, which the kernel handles even when userspace is wedged. |
| Hold the button for 5 seconds | Always does the hard reboot. |

This is how the pieces connect:

- **On the Pico.** [`admin/pico/boot.py`](../admin/pico/boot.py) adds a second USB serial port, the *data* port, next to the CircuitPython REPL console. [`admin/pico/code.py`](../admin/pico/code.py) writes `RESTART-ES` to the data port and waits for `ACK`.
- **On the box.** `arcade-button.service` runs [`~/stuff/arcade-button`](../admin/arcade-button) as `es`. It finds the Pico's data port, which is the higher-numbered of its two `ttyACM` devices, answers `ACK` straight away, and then runs the restart. If `arcade-admin` fails, it reboots the box. `install.sh` installs and enables the service.
- **Logs.** Run `journalctl -u arcade-button`.
- **Testing without the button.** Run `arcade-button --port /dev/pts/N --dry-run` against a pseudo-terminal.

**To update the Pico's firmware,** copy `boot.py` and `code.py` onto its `CIRCUITPY` drive. It needs `adafruit_hid` in `lib/`, which is already there. Then unplug the Pico and plug it back in; changes to `boot.py` only take effect after a hard reset. Until `boot.py` is in place, the Pico has no data port. The service then logs that it is waiting, and every press falls back to the hard reboot.

`kernel.sysrq` must stay `1`, the Ubuntu default on this box, for the fallback to work.

## Box configuration and `install.sh`

Everything that makes the box an arcade box, as opposed to a stock Ubuntu machine, is kept in this repo under [`admin/`](../admin/). Run `admin/install.sh` from your own machine to apply it:

```bash
admin/install.sh --check     # report what differs from the repo; change nothing
admin/install.sh             # apply (default SSH host: arcade; pass another as the last argument)
```

The script copies `admin/` to `~/stuff/arcade-setup/` on the box and runs [`box/setup-box.sh`](../admin/box/setup-box.sh) there. That script is idempotent: anything that already matches is left alone, so on the current box a rerun changes nothing. Before replacing any file, it saves a `.bak-<timestamp>` copy next to the original. It works through these steps:

| Step | Source in the repo | What it does on the box |
|---|---|---|
| Packages | [`box/packages.txt`](../admin/box/packages.txt) | Installs any missing apt packages: git, the venv and pycairo build dependencies, openbox, dialog, fonts, and so on. |
| Groups | `setup-box.sh` | Makes sure `es` is in `dialout` and `plugdev`. |
| EmulationStation | `setup-box.sh` | If ES isn't installed, clones RetroPie-Setup and builds EmulationStation and the carbon-2021 theme from source. This takes a while. |
| Launcher and tools | [`112.sh`](../admin/112.sh), [`arcade-admin`](../admin/arcade-admin), [`arcade-button`](../admin/arcade-button) | Installs all three into `~/stuff/` and links `/usr/local/bin/arcade-admin`. |
| Config files | [`box/files/`](../admin/box/files/) | Installs each file at the same path on the box. See the list below this table. ES is closed while its own config files are replaced. |
| Semester menu entries | `arcade-admin sync-menu` | Makes the student-game systems at the top of `/etc/emulationstation/es_systems.cfg` match the games' semesters. The rest of the file is left alone. See [Semesters](#semesters). |
| Auto-login | [`box/merge-config.py`](../admin/box/merge-config.py) | Sets `AutomaticLogin=es` in `/etc/gdm3/custom.conf`, and sets `es`'s session to openbox through AccountsService. |
| Reset button | `setup-box.sh` | Enables and starts `arcade-button.service`, and restarts it when the script or the unit changes. |

These are the files under `box/files/`:

- `opt/retropie/configs/all/emulationstation/es_settings.cfg`: the carbon-2021 theme, **Kiosk UI mode**, a 5-minute dim screensaver, and saving gamelists on exit.
- `opt/retropie/configs/all/emulationstation/es_input.cfg`: the joystick mapping for the cabinet's DragonRise encoder.
- `home/es/.config/openbox/autostart`: sets the resolution to 800x600 and starts ES in a maximized `gnome-terminal`.
- `home/es/.fonts/LuckiestGuy.ttf`: a font one of the games uses.
- `etc/udev/rules.d/99-input.rules`: input-device permissions.
- `etc/systemd/system/arcade-button.service`: the reset-button listener (see [The reset button](#the-reset-button)).
- `etc/sudoers.d/arcade-es`: passwordless sudo for `es`. The tools need it. It's checked with `visudo` before it's installed.

**To change the box's configuration,** edit the files in `admin/box/` and run `install.sh`. If you change something on the box directly, for example through ES's own settings menu, copy the file back into `admin/box/files/` so the repo stays the source of truth. Running `install.sh --check` shows any drift.

### Rebuilding the box from scratch

1. Install Ubuntu 22.04 Desktop, and create the user `es` during installation.
2. On the box, run `sudo apt install openssh-server`.
3. On your machine, point the `arcade` SSH host at the box and set up key login.
4. Run `admin/install.sh`. It asks for `es`'s sudo password once, builds EmulationStation, and applies everything above.
5. Reboot. The box should come up in EmulationStation. There are no student-game entries until a game is added.
6. Re-add the games with `arcade-admin add`.

**What isn't restored:**

- **The games and their deploy keys.** Lock files, display names, semesters, and the private keys in `~/.ssh` all live only on the box. A rebuild means re-adding each game, and private repos need their owners to add a new deploy key. If you want to avoid that, back up `~/.ssh` and `~/stuff/frozen/` somewhere private before you wipe the box.
- **RetroArch and the libretro cores.** The old install had about 20, but none of them had any ROMs.
- **The Raspberry Pi Pico's build tooling.** This is `~/src/pico-sdk`, `~/src/picotool`, `~/reset_pico.py`, and `/etc/udev/rules.d/99-picotool.rules`. The button firmware itself lives on the Pico and is version-controlled in `admin/pico/`; reinstalling the box doesn't touch it.
- **Network settings,** such as Wi-Fi.
- **X's default screen blanking,** which blanks the screen after 10 minutes. Being the stock default, it comes back by itself.

## Adding a game

### Before you start: what the student's repo needs

Ask for the GitHub URL and confirm the repo has the following. `add` checks for each of these and warns you if one is missing:

- `main.py` at the top level. The launcher only ever runs `python3 main.py`.
- A `requirements.txt` that lists at least `cmu-graphics`.
- A way to quit from the joystick that calls `sys.exit(0)`. The convention is the P1 button, which is button `'5'`. Without this, the only way out is the hard-reset button.
- **No copy of `cmu_graphics` committed in the repo.** A committed `cmu_graphics/` folder or `cmu_graphics.py` shadows the library that pip installs, and the game usually breaks. The chase-car game hit this problem.

### Running `add`

```bash
ssh -t arcade arcade-admin add https://github.com/owner/repo --name Cool-Game
```

Leave out the URL and options to be prompted for them. Folder names may only use letters, digits, `-` and `_`, because `112.sh` runs `cd $1` without quotes. The semester defaults to the current one, based on today's date: August to December is Fall, January to May is Spring, and June and July are Summer.

- **Public repos** are cloned over HTTPS, with no key needed.
- **Private repos** get their own deploy key. The tool does the following:
  1. Generates `~/.ssh/id_ed25519.<key-id>` and adds a `Host github-<key-id>` block. The default key id is the repo owner; pass the student's Andrew ID with `--key-id`.
  2. Prints the public key, with instructions. The student, or a repo or org admin, adds it under **GitHub → repo → Settings → Deploy keys**, leaving "Allow write access" **unchecked**.
  3. Waits until the key works, then clones.

  If you'd rather not wait, press `q` (or run non-interactively, which exits with code 3). Running the same `add` command later reuses the key. GitHub allows each deploy key on only one repo, so a key id that another game already uses is refused.

After cloning, `add` builds the venv and offers a test launch on the arcade screen. Press P1 to quit the game. If the game works, `add` offers to freeze it (which also stops it pulling updates), then asks for an optional display name, and finally restarts ES so the game appears in the menu under its semester.

## Semesters

Every game is tagged with the semester it's from. The main screen of the box has one entry per semester, newest first, and each entry lists that semester's enabled games. Games without a tag are listed under **Other**, at the end.

```bash
arcade-admin semester Cool-Game "Spring 2027"     # or S27; M27 is Summer 2027
```

The tag is stored in the game's own `.git/config` (`git config arcade.semester`), so it moves with the folder when the game is renamed, disabled or enabled. It never changes the working tree, and students can't change it.

ES can only list a folder of games, so `arcade-admin` builds the menu from the tags:

- `~/RetroPie/roms/cmu_graphics-semesters/<semester>/<Name>.git` is a symlink to each enabled game in `~/RetroPie/roms/cmu_graphics/`. The games themselves don't move, so their venvs keep working.
- `/etc/emulationstation/es_systems.cfg` gets one `<system>` per semester, at the top of the file, newest first. `arcade-admin` treats every system whose command is `/home/es/stuff/112.sh %ROM%` as one of its own, and replaces those systems whenever it rebuilds the menu.
- A game's display name and play count live in its semester's gamelist, `gamelists/<semester>/gamelist.xml`. When a game changes semester, its entry moves with it.

Every command that changes a game rebuilds the menu on its own. If you edit things by hand, run `arcade-admin sync-menu` afterwards.

## Updating a game

An unfrozen game runs `git pull` on every launch, so its students only have to push. A **frozen** game (one with a lock file) skips the pull and keeps running the code it had when it was frozen. To bring in a student's new code for a frozen game:

```bash
git -C ~/RetroPie/roms/cmu_graphics/Cool-Game.git pull
arcade-admin launch Cool-Game                           # make sure it still works
arcade-admin freeze Cool-Game                           # re-freeze if requirements.txt changed
```

Or run `arcade-admin unfreeze Cool-Game` to go back to pulling on every launch.

You only need to step in when one of these happens:

- **The pull fails** (unfrozen games only). The usual causes are that the deploy key was removed or the repo was renamed or deleted. The game still launches, but it runs the last code it pulled. Use `ssh -T git@github-<id>` to diagnose, or run the [health check](#health-check).
- **The pull refuses to run because of local changes.** Run `git -C <Game>.git status` to see them, then `git checkout -- .` or `git reset --hard origin/<branch>` to discard them.
- **The student force-pushed or rewrote history.** Run `git fetch && git reset --hard origin/<branch>`.
- **The dependencies are stuck or broken.** Run `rm -rf <Game>.git/retropie-venv`. The next launch rebuilds it with the frozen versions.
- **The student changed `requirements.txt`.** If they added a new package, it gets installed at its latest version, and the frozen packages stay where they are. If they deliberately changed the version of a package that's already frozen, pip reports a conflict, skips the install, and the game runs with the old versions. To accept the change, follow the steps in [Frozen dependencies](#frozen-dependencies).
- **`joystick.py` needs updating.** Have the student copy the new `joystick.py` into their repo and push it. If you edit the file on the box, the next `git pull` will conflict.

## Frozen dependencies

`pip install -r requirements.txt` doesn't upgrade packages that are already installed. That means the real risk isn't an ordinary launch. The risk is a venv that gets rebuilt, or a newly added game, pulling whatever is newest on PyPI. Most student `requirements.txt` files just say `cmu-graphics` with no version.

The installed games currently use cmu-graphics versions from 1.1.23 to 1.1.44, each with its own Pillow, pygame and pycairo. cmu-graphics 3.x is out, but it needs Python 3.11 or newer. The box runs 3.10, so today a fresh venv gets 1.1.44. That changes the moment Python on the box is upgraded.

The lock files in `~/stuff/frozen/<Name>.git.txt` close this gap. Each one is the output of `pip freeze` from a venv that's known to work.

- Each lock file sits outside the repo, so `git pull` never conflicts with it, and students can't change it.
- A lock file also freezes the code: `112.sh` skips `git pull` for a game that has one, so a student push can't break a working game. See [Updating a game](#updating-a-game).
- On every launch, `112.sh` runs `pip install -r <lock>`. That's a fast no-op if the venv already matches, and if the venv is missing or damaged, the same command reinstalls the exact versions. The launcher then installs `requirements.txt` with `-c <lock>`, so the lock file acts as a constraint.
- It also covers packages that were installed in the venv by hand, outside `requirements.txt`. For example, Professor-Invaders has no `requirements.txt`, so it depends entirely on its lock file.

Here's how to deliberately accept newer versions for a game:

```bash
cd ~/RetroPie/roms/cmu_graphics/Cool-Game.git
retropie-venv/bin/pip install -r requirements.txt       # no -c: let the new versions in
arcade-admin launch Cool-Game                           # make sure it still works
arcade-admin freeze Cool-Game                           # record the new known-good set
```

## How the box is wired together

The box runs Ubuntu 22.04 (Python 3.10) with RetroPie/EmulationStation. Everything runs as the user `es`, which has passwordless `sudo`. You can reach it with `ssh arcade`. On the local network it also answers as `emulationstation.local`.

At boot, GDM logs `es` in automatically and runs `~/.config/openbox/autostart`. That script sets the resolution to 800x600 and starts `emulationstation` in a maximized `gnome-terminal`. The `emulationstation` wrapper relaunches ES if `/tmp/es-restart` exists when ES exits; otherwise the terminal closes. `arcade-admin` restarts ES by stopping the real binary (`/opt/retropie/supplementary/emulationstation/emulationstation`) and starting a new terminal on display `:0`.

EmulationStation reads its systems from `/etc/emulationstation/es_systems.cfg`. The first entries are the student games, one per semester (see [Semesters](#semesters)):

```xml
<system>
  <name>Fall 2026</name>
  <fullname>15-112 Fall 2026</fullname>
  <path>/home/es/RetroPie/roms/cmu_graphics-semesters/fall-2026</path>
  <extension>.git</extension>
  <command>/home/es/stuff/112.sh %ROM%</command>
  <theme>112</theme>
</system>
```

The carbon-2021 theme has no `112` artwork, so the main screen shows each system's `<name>` as text.

**Every directory in `~/RetroPie/roms/cmu_graphics/` whose name ends in `.git` is a game.** The menu shows the directory name without `.git`, unless gamelist.xml gives it a display name. When someone picks a game, EmulationStation runs [`112.sh`](../admin/112.sh) with the path of the game's symlink in its semester folder. The script:

1. `cd`s into the game directory and, unless the game is frozen (has a lock file), runs `git pull`. It first sets `core.fsync` so a hard reset is less likely to corrupt the repo.
2. Creates `retropie-venv/` inside the game directory if it doesn't exist yet, then activates it.
3. Installs the lock file if the game has one, then `requirements.txt`, using the lock file as a constraint if there is one.
4. Sets `CI=False` and runs `python3 main.py`.

Two details shape how `arcade-admin` works:

- **A venv hard-codes its absolute path.** After a game folder is moved, `source activate` silently falls back to the system Python, which doesn't have the game's packages. So `rename` rebuilds the venv from a lock file. `disable` and `enable` move the folder back to exactly the same path, so they don't need a rebuild.
- **EmulationStation rewrites gamelist.xml when it exits.** Edits made while ES is running are lost, which is why `arcade-admin` stops ES before editing that file.

### The relevant paths

| Path | What it is | Live? |
|---|---|---|
| `/home/es/RetroPie/roms/cmu_graphics/` | One `<Name>.git` clone per game | **Yes** |
| `/home/es/RetroPie/roms/cmu_graphics-disabled/` | Disabled games. ES doesn't scan it. | **Yes** |
| `/home/es/RetroPie/roms/cmu_graphics-semesters/<semester>/` | Symlinks to the enabled games, one folder per semester. ES scans these. Rebuilt by `arcade-admin`. | **Yes** |
| `/home/es/stuff/112.sh` | The launcher. Source: [`admin/112.sh`](../admin/112.sh). `112.sh.bak-2026-11-22` is the version from before freezing was added. | **Yes** |
| `/home/es/stuff/arcade-admin` (+ `/usr/local/bin/arcade-admin` symlink) | The management tool. Source: [`admin/arcade-admin`](../admin/arcade-admin). | Tool |
| `/home/es/stuff/arcade-button`, `/etc/systemd/system/arcade-button.service` | The reset-button listener. Source: [`admin/arcade-button`](../admin/arcade-button). | **Yes** |
| `/home/es/stuff/frozen/<Name>.git.txt` | The lock file for each game | **Yes** |
| `/etc/emulationstation/es_systems.cfg` | Defines one system per semester (shown above) | **Yes** |
| `/home/es/.ssh/config`, `/home/es/.ssh/id_rsa.*`, `id_ed25519.*` | One `Host github-<id>` alias plus one deploy key per private repo. The default `id_rsa` is the deploy key for `rriley/arcade-box-test`. | **Yes** |
| `/opt/retropie/configs/all/emulationstation/gamelists/<semester>/gamelist.xml` | Display names, play counts, and favorites | Yes |
| `/opt/retropie/configs/all/emulationstation/gamelists/112/` | Gamelist from before semesters. `arcade-admin` moved its entries into the semester gamelists. | No, legacy |
| `/opt/retropie/configs/all/emulationstation/gamelists/112graphics/` | Gamelist from the 2023 prototype system | No, legacy |
| `/opt/retropie/configs/112/emulators.cfg` | `runcommand` emulator config. It isn't used, because the system entry calls `112.sh` directly. | No |
| `/home/es/stuff/es_systems.cfg`, `/home/es/stuff/emulators.cfg` | Original copies from the `pi`-user era (paths point to `/home/pi`) | No, reference only |
| `/home/es/stuff/98-argh.rules` | udev rule for the joystick encoder (vendor `0079`, product `0006`) | Reference copy |
| `/home/es/.ssh/dead/` | Keys for retired games | No |

## Doing it by hand

If `arcade-admin` isn't available, these are the steps it automates.

**Add a public repo:** `git clone https://github.com/<owner>/<repo> ~/RetroPie/roms/cmu_graphics/Cool-Game.git`

**Set its semester:** `git -C ~/RetroPie/roms/cmu_graphics/Cool-Game.git config arcade.semester "Fall 2026"`. Then add the semester's `<system>` to `es_systems.cfg` (as shown above) and symlink the game into its folder.

**Add a private repo:**

```bash
ssh-keygen -t ed25519 -N "" -f ~/.ssh/id_ed25519.<id> -C "arcade-box <id>"
cat ~/.ssh/id_ed25519.<id>.pub                  # student adds this as a read-only deploy key
cat >> ~/.ssh/config <<EOF

Host github-<id>
	Hostname github.com
	User git
	IdentityFile /home/es/.ssh/id_ed25519.<id>
EOF
ssh -T git@github-<id>                          # "Hi <owner>/<repo>! ..."
git clone git@github-<id>:<owner>/<repo>.git ~/RetroPie/roms/cmu_graphics/Cool-Game.git
```

Use the alias, not `github.com`. A clone from `git@github.com:...` uses the default key and fails for a private repo. To fix a clone that used the wrong URL, run `git -C Cool-Game.git remote set-url origin git@github-<id>:<owner>/<repo>.git`.

**Test launch:** close ES first, then run `DISPLAY=:0 ~/stuff/112.sh ~/RetroPie/roms/cmu_graphics/Cool-Game.git`. Closing ES matters because otherwise it keeps reading the joysticks behind the game.

**Freeze:** `Cool-Game.git/retropie-venv/bin/pip freeze > ~/stuff/frozen/Cool-Game.git.txt`

**Remove:**
1. Delete the folder and its lock file.
2. Delete the `Host` block from `~/.ssh/config`.
3. Move the key pair to `~/.ssh/dead/`.
4. Optionally, remove the `<game>` entry from gamelist.xml while ES is stopped. A stale entry is harmless.

**Restart ES:** ES runs in Kiosk mode, so its Quit menu isn't available from the arcade controls. Over SSH, `sudo reboot` always works. Don't just kill `emulationstation`: the terminal it runs in closes, and ES won't come back until the next login. Alternatively, start ES again yourself with `DISPLAY=:0 XAUTHORITY=/run/user/1000/gdm/Xauthority DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/1000/bus setsid gnome-terminal --maximize -- emulationstation`.

## Health check

This one-liner checks whether every installed game can still reach its remote:

```bash
cd ~/RetroPie/roms/cmu_graphics && for d in *.git; do timeout 20 git -C "$d" ls-remote -q origin HEAD >/dev/null 2>&1 && echo "OK    $d" || echo "FAIL  $d"; done
```
