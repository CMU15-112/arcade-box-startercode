#!/bin/bash
# Launch one game: 112.sh <game dir>. EmulationStation runs this (see es_systems.cfg).
echo "-----------------------------------------------------"
cd $1
# Known-good package versions for this game (see arcade-admin freeze)
FROZEN="/home/es/stuff/frozen/$(basename "$1").txt"
if [ -f "$FROZEN" ]
then
    # A frozen game keeps the code it was frozen with
    echo "${1} is frozen; not fetching updates."
    DEPS=(--with-requirements "$FROZEN")
else
    echo "Fetching the latest version of ${1}..."
    # These two should make things more resilient in the event of a reset
    git config core.fsync all
    git config core.fsyncMethod fsync
    git pull
    if [ -f requirements.txt ]
    then
        DEPS=(--with-requirements requirements.txt)
    else
        echo "${1} has no requirements.txt; assuming it only needs cmu-graphics."
        DEPS=(--with cmu-graphics)
    fi
fi
# The system Python unless an admin chose another version for this game
# (arcade-admin python GAME VERSION).
PYTHON="$(git config --get arcade.python || echo /usr/bin/python3)"
# uv builds an environment with these packages the first time and reuses it from
# its cache (~/.cache/uv) after that. --isolated keeps the system's apt Python
# packages out. uv's settings for the box are in ~/.config/uv/uv.toml.
RUN=(/usr/local/bin/uv run --no-project --isolated --python "$PYTHON" "${DEPS[@]}" python main.py)
echo "Running ${1}..."
export CI=False
# cmu-graphics 3 (Python 3.11+) crashes on X11 when its window fills the screen,
# so those games run on Wayland: in cage, as a window in the X session. openbox
# makes that window fill the screen with no title bar (~/.config/openbox/rc.xml).
MINOR="${PYTHON#3.}"
MINOR="${MINOR%%.*}"
if [[ "$PYTHON" == 3.* && "$MINOR" =~ ^[0-9]+$ ]] && (( MINOR >= 11 ))
then
    # -d: the game draws no title bar of its own, so it gets all 600 rows
    WLR_BACKENDS=x11 cage -d -- "${RUN[@]}"
else
    "${RUN[@]}"
fi
echo "Back from the run..."
