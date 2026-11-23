#!/bin/bash
# Set up (or update) the arcade box from this repo. Run from your own machine:
#
#   admin/install.sh [--check] [ssh-host]      (default host: arcade)
#
# Copies admin/ to ~/stuff/arcade-setup on the box and runs box/setup-box.sh there,
# which installs packages, builds EmulationStation if it's missing, deploys
# 112.sh + arcade-admin, and applies the config in admin/box/. It is idempotent:
# on an already-configured box it changes nothing. --check only reports.
set -euo pipefail

CHECK=""
if [[ "${1:-}" == "--check" ]]; then CHECK="--check"; shift; fi
HOST="${1:-arcade}"
HERE="$(cd "$(dirname "$0")" && pwd)"

# Catch syntax errors before touching the box.
python3 -c "import ast,sys; [ast.parse(open(f).read(), f) for f in sys.argv[1:]]" \
    "$HERE/arcade-admin" "$HERE/arcade-button" "$HERE/box/merge-config.py" \
    "$HERE/pico/boot.py" "$HERE/pico/code.py"
bash -n "$HERE/112.sh"
bash -n "$HERE/box/setup-box.sh"

echo "Copying admin/ to $HOST:~/stuff/arcade-setup ..."
tar -C "$HERE" --exclude=__pycache__ -czf - . |
    ssh "$HOST" 'rm -rf ~/stuff/arcade-setup && mkdir -p ~/stuff/arcade-setup && tar -C ~/stuff/arcade-setup -xzf -'

# -t so sudo can ask for a password on a fresh box.
ssh -t "$HOST" "bash ~/stuff/arcade-setup/box/setup-box.sh $CHECK"
