#!/bin/bash

PROJECT_NAME=cortex

set -e # shell will exit on error in one of the following commands
cd "$(dirname "${BASH_SOURCE[0]}")/.." # enter the parent directory of the current script

function main {
    python3.8 -m venv .env --prompt "["$PROJECT_NAME"] "
    find .env -name site-packages -exec bash -c 'echo "../../../../" > {}/self.pth' \;
    pip install -U pip # upgrading pip
    pip install -r requirements.txt
}

main "$@"
