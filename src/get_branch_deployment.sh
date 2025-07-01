#!/bin/bash -

if [ -z $DAGSTER_CLOUD_URL ]; then
    if [ -z $INPUT_DAGSTER_CLOUD_URL ]; then
        export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
    else
        export DAGSTER_CLOUD_URL="${INPUT_DAGSTER_CLOUD_URL}"
    fi
fi

if [ -z $INPUT_SOURCE_DIRECTORY ]; then
    export INPUT_SOURCE_DIRECTORY=$(pwd)
fi

git config --global --add safe.directory $(realpath $INPUT_SOURCE_DIRECTORY)

if [ -z $INPUT_BASE_DEPLOYMENT_NAME ]; then
    BRANCH_DEPLOYMENT_NAME=$(dagster-cloud ci branch-deployment $INPUT_SOURCE_DIRECTORY)
else
    BRANCH_DEPLOYMENT_NAME=$(dagster-cloud ci branch-deployment $INPUT_SOURCE_DIRECTORY --base-deployment-name $INPUT_BASE_DEPLOYMENT_NAME)
fi

echo "deployment=${BRANCH_DEPLOYMENT_NAME}" >> $GITHUB_OUTPUT
