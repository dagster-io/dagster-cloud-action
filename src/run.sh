#!/bin/bash -

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
    --url "${DAGSTER_CLOUD_URL}" \
    --deployment "${INPUT_DEPLOYMENT}" \
    --api-token "$DAGSTER_CLOUD_API_TOKEN" \
    --location "${INPUT_LOCATION_NAME}" \
    --repository "${INPUT_REPOSITORY_NAME}" \
    --job "${INPUT_JOB_NAME}" \
    --tags "${INPUT_TAGS_JSON}" \
    --config-json "${INPUT_CONFIG_JSON}"
)

if [ -z $RUN_ID ]; then
    echo "Failed to launch run"
    exit 1
else
    echo "Successfully launched run: ${RUN_ID}"
    echo "run_id=${RUN_ID}" >> $GITHUB_OUTPUT
fi
