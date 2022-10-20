#!/bin/bash

# Build the builder.pex from Pexfile.lock and src/
# Can be run locally or on GHA - modifies the python environment by
# installing pipenv and pex.
# Note builder.pex requires Python 3.8, however it can build pex files that target
# other versions.

set -o xtrace   # debug printing

# change to script dir
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
echo "Running in $SCRIPT_DIR"

BUILDER_PEX_PATH="${1:-build}/builder.pex"
echo "Going to build $BUILDER_PEX_PATH"

export PIPENV_IGNORE_VIRTUALENVS=1
pip install pipenv pex
mkdir build

# Generate a requirements.txt from Pipfile.lock
# Put it in src so it also gets copied into pex for reference
pipenv requirements --exclude-markers > src/requirements.txt

# Generate a multi platform builder.pex (linux and macos)
# Require running builder.pex under 3.8, in case multiple pythons are present on PATH
pex -r src/requirements.txt -D src -o $BUILDER_PEX_PATH -v --include-tools \
    --python=python3.8 \
    --platform=manylinux2014_x86_64-cp-38-cp38 --platform=macosx_12_0_x86_64-cp-38-cp38

# Don't accidentally check into git
rm src/requirements.txt