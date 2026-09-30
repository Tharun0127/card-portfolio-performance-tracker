#!/usr/bin/env bash
# Rebuild everything from raw data on macOS or Linux:  ./run_all.sh
# Creates the virtual environment on first use, installs the pinned requirements,
# then runs the whole pipeline and the tests.
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x ".venv/bin/python" ]; then
    echo "Creating virtual environment with Python 3.11"
    python3.11 -m venv .venv
fi

.venv/bin/python -m pip install --quiet --disable-pip-version-check -r requirements.txt
.venv/bin/python run_all.py
