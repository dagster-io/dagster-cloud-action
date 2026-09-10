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
    # Parse KEY=VALUE pairs without `source` or unquoted `echo`, because
    # either would re-expand any `$` in the value (e.g. Harbor robot
    # usernames are `robot$<project>+push`) and mangle the credential.
    AWS_ECR_USERNAME=""
    AWS_ECR_PASSWORD=""
    REGISTRY_URL=""
    AWS_DEFAULT_REGION=""
    CUSTOM_BASE_IMAGE_ALLOWED=""
    while IFS='=' read -r _key _value; do
        case "$_key" in
            AWS_ECR_USERNAME) AWS_ECR_USERNAME="$_value" ;;
            AWS_ECR_PASSWORD) AWS_ECR_PASSWORD="$_value" ;;
            REGISTRY_URL) REGISTRY_URL="$_value" ;;
            AWS_DEFAULT_REGION) AWS_DEFAULT_REGION="$_value" ;;
            CUSTOM_BASE_IMAGE_ALLOWED) CUSTOM_BASE_IMAGE_ALLOWED="$_value" ;;
        esac
    done <<<"$REGISTRY_INFO"
    count=$(($count + 1))
    if [ ! -z "$AWS_ECR_PASSWORD" ]; then
        echo "Loaded registry information."
        echo "::add-mask::$AWS_ECR_PASSWORD"
        echo "REGISTRY_URL=${REGISTRY_URL}" >> $GITHUB_ENV
        echo "AWS_ECR_USERNAME=${AWS_ECR_USERNAME}" >> $GITHUB_ENV
        echo "AWS_ECR_PASSWORD=${AWS_ECR_PASSWORD}" >> $GITHUB_ENV
        echo "AWS_DEFAULT_REGION=${AWS_DEFAULT_REGION}" >> $GITHUB_ENV
        if [ ! -z "$CUSTOM_BASE_IMAGE_ALLOWED" ]; then
            echo "CUSTOM_BASE_IMAGE_ALLOWED=${CUSTOM_BASE_IMAGE_ALLOWED}" >> $GITHUB_ENV
        fi
        exit 0
    elif (( count >= 6 )); then
        echo "::error::No serverless registry information found - your serverless deployment may still be activating."
        exit 1
    else
        echo "Could not load registry information  - your serverless deployment may still be activating. Retrying in 10 s"
        sleep 10
    fi
done
