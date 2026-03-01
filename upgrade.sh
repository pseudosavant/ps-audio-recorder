#!/bin/bash

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[upgrade] Pulling latest changes..."
git pull --ff-only

echo "[upgrade] Running setup in upgrade mode..."
if [[ "$EUID" -eq 0 ]]; then
    ./setup.sh --upgrade "$@"
else
    sudo ./setup.sh --upgrade "$@"
fi

echo "[upgrade] Complete."
