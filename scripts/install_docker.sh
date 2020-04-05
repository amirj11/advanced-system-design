#!/bin/bash

PROJECT_NAME=cortex

set -e # shell will exit on error in one of the following commands
cd "$(dirname "${BASH_SOURCE[0]}")/.." # enter the parent directory of the current script

function main {
    pip3 install -U pip # upgrading pip
    pip3 install -r /scripts/requirements.txt
}

main "$@"
