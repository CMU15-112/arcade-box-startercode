#!/bin/bash
echo "-----------------------------------------------------"
cd $1
# Known-good package versions for this game (see arcade-admin freeze)
FROZEN="/home/es/stuff/frozen/$(basename "$1").txt"
if [ -f "$FROZEN" ]
then
    # A frozen game keeps the code it was frozen with
    echo "${1} is frozen; not fetching updates."
else
    echo "Fetching the latest version of ${1}..."
    # These two should make things more resilient in the event of a reset
    git config core.fsync all
    git config core.fsyncMethod fsync
    git pull
fi
if [ ! -d "retropie-venv" ]
then
    echo "Setting up the virtual environment for the first time..."
    python3 -m venv retropie-venv
fi
echo "Activating the virtual environment..."
source retropie-venv/bin/activate
if [ -f "$FROZEN" ]
then
    echo "Installing frozen dependencies from ${FROZEN}..."
    python3 -m pip install -r "$FROZEN"
    if [ -f "requirements.txt" ]
    then
        echo "Installing/Updating Dependencies (constrained by frozen versions)..."
        python3 -m pip install -r requirements.txt -c "$FROZEN"
    fi
elif [ -f "requirements.txt" ]
then
    echo "Installing/Updating Dependencies..."
    python3 -m pip install -r requirements.txt
fi
echo "Running ${1}..."
export CI=False
python3 main.py
echo "Back from the run..."
