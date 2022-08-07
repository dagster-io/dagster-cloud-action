#!/bin/bash -

if [ -z $DAGSTER_CLOUD_URL ]; then
    if [ -z $INPUT_DAGSTER_CLOUD_URL ]; then
        export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
    else
        export DAGSTER_CLOUD_URL="${INPUT_DAGSTER_CLOUD_URL}"
    fi
fi

count=0

while (( !AWS_ECR_PASSWORD && count < 6 )); do
    echo "Fetching registry info"
    REGISTRY_INFO=$(dagster-cloud serverless registry-info \
        --url "${DAGSTER_CLOUD_URL}/${INPUT_DEPLOYMENT}" \
        --api-token "$DAGSTER_CLOUD_API_TOKEN")
    echo $REGISTRY_INFO > registry_info.env
    source registry_info.env
    count=$(($count + 1))
    if [ ! -z "$AWS_ECR_PASSWORD" ]; then
        echo "Loaded registry information."
        echo "::add-mask::$AWS_ECR_PASSWORD"
        echo "REGISTRY_URL=${REGISTRY_URL}" >> $GITHUB_ENV
        echo "AWS_ECR_USERNAME=${AWS_ECR_USERNAME}" >> $GITHUB_ENV
        echo "AWS_ECR_PASSWORD=${AWS_ECR_PASSWORD}" >> $GITHUB_ENV
        echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}" >> $GITHUB_ENV
        exit 0
    elif (( count >= 6 )); then
        echo "::error::No serverless registry information found - your serverless deployment may still be activating."
        exit 1
    else
        echo "Could not load registry information  - your serverless deployment may still be activating. Retrying in 10 s"
        sleep 10
    fi
done
