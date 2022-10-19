# Build the builder.pex from Pexfile.lock and src/
# Run in a venv locally or on GHA - modifies the python environment by
# installing pipenv and pex

set -o xtrace   # debug printing

# change to script dir
SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
cd $SCRIPT_DIR
echo "Running in $SCRIPT_DIR"

export PIPENV_IGNORE_VIRTUALENVS=1
pip install pipenv pex
mkdir build

# Generate a requirements.txt from Pipfile.lock
# Put it in src so it also gets copied into pex for reference
pipenv requirements --exclude-markers > src/requirements.txt

# Generate a multi platform builder.pex (linux and macos)
pex -r src/requirements.txt -D src -o build/builder.pex -v --include-tools \
    --python=python3.8  # require running under 3.8, in case multiple pythons are present on PATH
    --platform=manylinux2014_x86_64-cp-38-cp38 --platform=macosx_12_0_x86_64-cp-38-cp38

# Don't accidentally check into git
rm src/requirements.txt