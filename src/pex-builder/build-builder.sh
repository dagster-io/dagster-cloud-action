#!/bin/bash

# Build the builder.pex from Pexfile.lock and src/
# Writes src/pex-builder/build/builder.pex
# Can be run locally or on GHA

set -o xtrace   # debug printing

# change to script dir
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
echo "Running in $SCRIPT_DIR"

BUILDER_PEX_PATH="${1:-build}/builder.pex"
echo "Going to build $BUILDER_PEX_PATH"

# create a venv to have a reproducible environment and not clobber the current python environment
python3.8 -m venv build/venv
source build/venv/activate

export PIPENV_IGNORE_VIRTUALENVS=1
pip install pipenv pex

# Build this python project. This will create the build/lib directory.
python setup.py build

# Generate a requirements.txt from Pipfile.lock
# Put it in build/lib so it also gets copied into the builder.pex for reference
pipenv requirements --exclude-markers > build/lib/requirements.txt

# Generate a multi platform builder.pex (linux and macos)
# Require running builder.pex under 3.8, in case multiple pythons are present on PATH
pex -r build/lib/requirements.txt -D build/lib -o $BUILDER_PEX_PATH -v --include-tools \
    --python=python3.8 \
    --platform=manylinux2014_x86_64-cp-38-cp38 \
    --platform=macosx_12_0_x86_64-cp-38-cp38

