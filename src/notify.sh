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

PR_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/pull/${INPUT_PR}"
export GITHUB_RUN_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/actions/runs/${GITHUB_RUN_ID}"

COMMENTS_URL="${PR_URL}/comments"

# Generate cloud URL, which might be directly supplied as env var or input, or generate from org ID
if [ -z $DAGSTER_CLOUD_URL ]; then
  export DAGSTER_CLOUD_URL="https://dagster.cloud/${INPUT_ORGANIZATION_ID}"
fi

export INPUT_LOCATION_NAME=$INPUT_LOCATION_NAME
python /debug.py
python /create_or_update_comment.py