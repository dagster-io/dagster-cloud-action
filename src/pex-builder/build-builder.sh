#!/bin/bash

# Build the builder.pex from Pexfile.lock and ./builder/
# Writes src/pex-builder/build/builder.pex
# Can be run locally or on GHA

# Bundles the latest `dagster-cloud` version from PyPI by default.
# To use the internal version of `dagster-cloud`, first export
# PEX_BUILDER_SRC_DIR=/path/to/dagster_cloud_cli/core/pex_builder

set -o xtrace   # debug printing
set -e

# change to script dir
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
echo "Running in $SCRIPT_DIR"

BUILDER_PEX_PATH="${1:-build}/builder.pex"
echo "Going to build $BUILDER_PEX_PATH"

# create a venv to have a reproducible environment and not clobber the current python environment
VENV_ROOT=build/venv
python3.8 -m venv $VENV_ROOT

source $VENV_ROOT/bin/activate

export PIPENV_IGNORE_VIRTUALENVS=1
$VENV_ROOT/bin/pip install pipenv "pex<=2.1.111"

# Build this python project. This will create the build/lib directory.
$VENV_ROOT/bin/python3.8 setup.py build

# Generate a requirements.txt from Pipfile.lock
# Put it in build/lib so it also gets copied into the builder.pex for reference
$VENV_ROOT/bin/pipenv requirements --exclude-markers > build/lib/requirements.txt

# Generate a multi platform builder.pex (linux and macos)
# Require running builder.pex under 3.8, in case multiple pythons are present on PATH
# Use a PEX_ROOT to completely isolate this build from others that may be on this machine
export PEX_ROOT=build/.pex
$VENV_ROOT/bin/pex -r build/lib/requirements.txt -D build/lib -o $BUILDER_PEX_PATH -v --include-tools \
    --python=python3.8 \
    --platform=manylinux2014_x86_64-cp-38-cp38 \
    --platform=macosx_12_0_x86_64-cp-38-cp38

