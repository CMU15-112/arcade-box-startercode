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
# uv builds an environment with these packages the first time and reuses it from
# its cache (~/.cache/uv) after that. --isolated keeps the system's apt Python
# packages out. uv's settings for the box are in ~/.config/uv/uv.toml.
echo "Running ${1}..."
export CI=False
/usr/local/bin/uv run --no-project --isolated --python /usr/bin/python3 "${DEPS[@]}" python main.py
echo "Back from the run..."
