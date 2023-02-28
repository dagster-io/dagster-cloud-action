#!/bin/bash

# Build dagster-cloud.pex
# Requires `pex` in the current environment (pip install pex)

if [ -z "$DAGSTER_CLOUD_INTERNAL_BRANCH" ]
then
    export DAGSTER_CLOUD_SOURCE_PACKAGE="dagster-cloud"
    export DAGSTER_CLOUD_CLI_SOURCE_PACKAGE="dagster-cloud-cli"
else
    export DAGSTER_CLOUD_SOURCE_PACKAGE="git+https://github.com/dagster-io/internal.git@${DAGSTER_CLOUD_INTERNAL_BRANCH}#egg=dagster-cloud&subdirectory=dagster-cloud/python_modules/dagster-cloud"
    export DAGSTER_CLOUD_CLI_SOURCE_PACKAGE="git+https://github.com/dagster-io/internal.git@${DAGSTER_CLOUD_INTERNAL_BRANCH}#egg=dagster-cloud-cli&subdirectory=dagster-cloud/python_modules/dagster-cloud-cli"
fi

echo "Building dagster-cloud.pex from "
echo " - $DAGSTER_CLOUD_SOURCE_PACKAGE"
echo " - $DAGSTER_CLOUD_CLI_SOURCE_PACKAGE"
echo ""

set -x

# Flags used:
# --platform specifies for a standard linux environment which works in GitHub
# --pip-version and --resolver-version recommended by the pex team, uses the latest dependency
#   resolution logic
# --venv prepend unpacks the pex into a venv before execution, nice to have for debugging
pex $DAGSTER_CLOUD_SOURCE_PACKAGE $DAGSTER_CLOUD_CLI_SOURCE_PACKAGE PyGithub \
    -o dagster-cloud.pex \
    --platform=manylinux2014_x86_64-cp-38-cp38 \
    --platform=macosx_12_0_x86_64-cp-38-cp38 \
    --pip-version=23.0 \
    --resolver-version=pip-2020-resolver \
    --venv prepend
