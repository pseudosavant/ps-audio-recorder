#!/bin/bash
cd /home/pi/ps-audio-recorder

# Create venv and install dependencies if it doesn't exist
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv --system-site-packages
    source .venv/bin/activate
    echo "Installing dependencies..."
    # Install python-kasa and its dependencies
    pip install python-kasa
fi

# Activate the virtual environment
source .venv/bin/activate

# Run the script
python main.py
