#!/bin/bash -

# Generate cloud URL, which might be directly supplied as env var or input, or generate from org ID
if [ -z $DAGSTER_CLOUD_URL ]; then
    if [ -z $INPUT_DAGSTER_CLOUD_URL ]; then
        export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
    else
        export DAGSTER_CLOUD_URL="${INPUT_DAGSTER_CLOUD_URL}"
    fi
fi

# Debug: Print the wait parameter value for troubleshooting
echo "DEBUG: INPUT_WAIT value: '${INPUT_WAIT}'"
echo "DEBUG: INPUT_WAIT lowercase: '$(echo "${INPUT_WAIT}" | tr '[:upper:]' '[:lower:]')'"

# Check for wait flag - handle various true values
wait_flag=""
case "$(echo "${INPUT_WAIT}" | tr '[:upper:]' '[:lower:]')" in
    "true"|"1"|"yes"|"on")
        wait_flag="--wait"
        echo "DEBUG: Wait flag enabled"
        ;;
    *)
        echo "DEBUG: Wait flag disabled"
        ;;
esac

echo "DEBUG: wait_flag result: '${wait_flag}'"

# Check dagster-cloud CLI version and available flags
echo "DEBUG: dagster-cloud version:"
dagster-cloud --version || echo "Failed to get version"

echo "DEBUG: dagster-cloud job launch help:"
dagster-cloud job launch --help | grep -A 5 -B 5 wait || echo "No wait flag found in help"

# Build the command for debugging
DAGSTER_CMD="dagster-cloud job launch --url \"${DAGSTER_CLOUD_URL}\" --deployment \"${INPUT_DEPLOYMENT}\" --api-token \"$DAGSTER_CLOUD_API_TOKEN\" --location \"${INPUT_LOCATION_NAME}\" --repository \"${INPUT_REPOSITORY_NAME}\" --job \"${INPUT_JOB_NAME}\" --tags \"${INPUT_TAGS_JSON}\" --config-json \"${INPUT_CONFIG_JSON}\" ${wait_flag}"

echo "DEBUG: About to run command: ${DAGSTER_CMD}"

RUN_ID=$(
    dagster-cloud job launch \
    --url "${DAGSTER_CLOUD_URL}" \
    --deployment "${INPUT_DEPLOYMENT}" \
    --api-token "$DAGSTER_CLOUD_API_TOKEN" \
    --location "${INPUT_LOCATION_NAME}" \
    --repository "${INPUT_REPOSITORY_NAME}" \
    --job "${INPUT_JOB_NAME}" \
    --tags "${INPUT_TAGS_JSON}" \
    --config-json "${INPUT_CONFIG_JSON}" \
    ${wait_flag}
)

if [ -z $RUN_ID ]; then
    echo "Failed to launch run"
    exit 1
else
    echo "Successfully launched run: ${RUN_ID}"
    echo "run_id=${RUN_ID}" >> $GITHUB_OUTPUT
fi
