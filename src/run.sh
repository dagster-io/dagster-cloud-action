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

echo "DEBUG: About to run command with wait_flag: '${wait_flag}'"

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
    ${wait_flag} 2>&1
)

echo "DEBUG: Command output:"
echo "$COMMAND_OUTPUT"

# Extract run ID from the output
# The run ID should be in format like "Run <run-id> is in progress" or just "<run-id>"
if [[ "$COMMAND_OUTPUT" =~ Run\ ([a-f0-9-]+) ]]; then
    RUN_ID="${BASH_REMATCH[1]}"
    echo "DEBUG: Extracted run ID from status output: ${RUN_ID}"
elif [[ "$COMMAND_OUTPUT" =~ ^[a-f0-9-]+$ ]]; then
    RUN_ID="$COMMAND_OUTPUT"
    echo "DEBUG: Using direct run ID output: ${RUN_ID}"
else
    # Try to get the first line if it looks like a run ID
    FIRST_LINE=$(echo "$COMMAND_OUTPUT" | head -n1 | tr -d '\n\r')
    if [[ "$FIRST_LINE" =~ ^[a-f0-9-]+$ ]]; then
        RUN_ID="$FIRST_LINE"
        echo "DEBUG: Using first line as run ID: ${RUN_ID}"
    else
        RUN_ID=""
        echo "DEBUG: Could not extract run ID from output"
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
