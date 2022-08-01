#!/bin/bash -

if [ -z $DAGSTER_CLOUD_URL ]; then
    if [ -z $INPUT_DAGSTER_CLOUD_URL ]; then
        export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
    else
        export DAGSTER_CLOUD_URL="${INPUT_DAGSTER_CLOUD_URL}"
    fi
fi

REGISTRY_INFO=$(dagster-cloud serverless registry-info \
    --url "${DAGSTER_CLOUD_URL}/${INPUT_DEPLOYMENT}" \
    --api-token "$DAGSTER_CLOUD_API_TOKEN")

echo $REGISTRY_INFO > registry_info.env
source registry_info.env
echo "::add-mask::$AWS_SECRET_ACCESS_KEY"
echo "REGISTRY_URL=${REGISTRY_URL}" >> $GITHUB_ENV
echo "AWS_ACCESS_KEY_ID=${AWS_ACCESS_KEY_ID}" >> $GITHUB_ENV
echo "AWS_SECRET_ACCESS_KEY=${AWS_SECRET_ACCESS_KEY}" >> $GITHUB_ENV
echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}" >> $GITHUB_ENV