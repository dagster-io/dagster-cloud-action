#!/bin/bash -

# Generate cloud URL, which might be directly supplied as env var or input, or generate from org ID
if [ -z $DAGSTER_CLOUD_URL ]; then
    if [ -z $INPUT_DAGSTER_CLOUD_URL ]; then
        export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
    else
        export DAGSTER_CLOUD_URL="${INPUT_DAGSTER_CLOUD_URL}"
    fi
fi

# Check for wait flag - handle various true values
wait_flag=""
interval_flag=""
case "$(echo "${INPUT_WAIT}" | tr '[:upper:]' '[:lower:]')" in
    "true"|"1"|"yes"|"on")
        wait_flag="--wait"
        # Only add interval flag if wait is enabled and interval is provided
        if [ -n "${INPUT_INTERVAL}" ]; then
            interval_flag="--interval ${INPUT_INTERVAL}"
        fi
        ;;
    *)
        # Validate that interval is not used without wait
        if [ -n "${INPUT_INTERVAL}" ]; then
            echo "ERROR: interval parameter can only be used when wait is true"
            exit 1
        fi
        ;;
esac

# Run the command and capture all output
COMMAND_OUTPUT=$(
    dagster-cloud job launch \
    --url "${DAGSTER_CLOUD_URL}" \
    --deployment "${INPUT_DEPLOYMENT}" \
    --api-token "$DAGSTER_CLOUD_API_TOKEN" \
    --location "${INPUT_LOCATION_NAME}" \
    --repository "${INPUT_REPOSITORY_NAME}" \
    --job "${INPUT_JOB_NAME}" \
    --tags "${INPUT_TAGS_JSON}" \
    --config-json "${INPUT_CONFIG_JSON}" \
    ${wait_flag} ${interval_flag} 2>&1
)

# Extract run ID from the output
# Look for patterns like "Run <run-id> is in progress" or "Run <run-id> finished"
RUN_ID=""
if [[ "$COMMAND_OUTPUT" =~ Run\ ([a-f0-9-]+) ]]; then
    RUN_ID="${BASH_REMATCH[1]}"
else
    # Try to get the first line if it looks like a run ID (for non-wait mode)
    FIRST_LINE=$(echo "$COMMAND_OUTPUT" | head -n1 | tr -d '\n\r')
    if [[ "$FIRST_LINE" =~ ^[a-zA-Z0-9-]+$ ]]; then
        RUN_ID="$FIRST_LINE"
    fi
fi

if [ -z "$RUN_ID" ]; then
    echo "Failed to launch run or extract run ID"
    echo "Command output was: $COMMAND_OUTPUT"
    exit 1
else
    echo "Successfully launched run: ${RUN_ID}"
    echo "run_id=${RUN_ID}" >> $GITHUB_OUTPUT
fi
