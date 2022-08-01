#!/bin/bash -

# Load JSON-encoded location info into env vars
# This produces the env vars
# INPUT_NAME, INPUT_LOCATION_FILE, INPUT_REGISTRY
source $(python /expand_json_env.py)

# The env var we get out of the `location` input is just `INPUT_NAME`
# the env var we get out of the `location_name` input is `INPUT_LOCATION_NAME`
# this just ensures we use whichever one is set
if [ -z $INPUT_LOCATION_NAME ]; then
    INPUT_LOCATION_NAME="${INPUT_NAME}"
fi

# Source registry from env var instead, if user specifies it that way
if [ -z $INPUT_REGISTRY ]; then
    INPUT_REGISTRY="${!INPUT_REGISTRY_ENV}"
fi

# Generate cloud URL, which might be directly supplied as env var or input, or generate from org ID
if [ -z $DAGSTER_CLOUD_URL ]; then
    if [ -z $INPUT_DAGSTER_CLOUD_URL ]; then
        export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
    else
        export DAGSTER_CLOUD_URL="${INPUT_DAGSTER_CLOUD_URL}"
    fi
fi

RUN_ID=$(
    dagster-cloud job launch \
    --url "${DAGSTER_CLOUD_URL}/${INPUT_DEPLOYMENT}" \
    --api-token "$DAGSTER_CLOUD_API_TOKEN" \
    --location "${INPUT_LOCATION_NAME}" \
    --repository "${INPUT_REPOSITORY}" \
    --job "${INPUT_JOB}" \
    --tags "${INPUT_TAGS_JSON}" \
    --config-json "${INPUT_CONFIG_JSON}"
)

echo "::set-output name=run_id::${RUN_ID}"
