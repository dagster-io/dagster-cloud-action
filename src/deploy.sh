#!/bin/bash -

# Load JSON-encoded location info into env vars
# This produces the env vars
# INPUT_NAME, INPUT_LOCATION_FILE, INPUT_REGISTRY
source $(python /expand_json_env.py)

# This maps CI provider (Github, Gitlab) env vars onto a
# standardized set of env vars:
# AVATAR_URL BRANCH_NAME BRANCH_URL CI_RUN_NUMBER COMMIT_HASH COMMIT_URL GIT_REPO PR_ID PR_STATUS PR_URL
if [ ! -z $GITHUB_ACTIONS ]; then
  AVATAR_URL=$(python /fetch_github_avatar.py)
  BRANCH_NAME="$GITHUB_HEAD_REF"
  BRANCH_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${GITHUB_HEAD_REF}"
  CI_RUN_NUMBER="$GITHUB_RUN_NUMBER"
  COMMIT_HASH="$GITHUB_SHA"
  COMMIT_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${GITHUB_SHA}"
  GIT_REPO="$GITHUB_REPOSITORY"
  PR_ID="$INPUT_PR"
  PR_STATUS=`echo $INPUT_PR_STATUS | tr '[a-z]' '[A-Z]'`
  PR_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/pull/${INPUT_PR}"
elif [ ! -z $GITLAB_CI ]; then
  #AVATAR_URL="TODO"
  BRANCH_NAME="$CI_COMMIT_BRANCH"
  BRANCH_URL="${CI_PROJECT_URL}/-/tree/${CI_COMMIT_BRANCH}"
  # CI_RUN_NUMBER="$GITHUB_RUN_NUMBER"
  COMMIT_HASH="$CI_COMMIT_SHORT_SHA"
  COMMIT_URL="${CI_PROJECT_URL}/-/commit/${CI_COMMIT_SHORT_SHA}"
  GIT_REPO="$CI_PROJECT_NAME"
  PR_ID="$CI_MERGE_REQUEST_ID"
  # PR_STATUS="TODO"
  PR_URL="${CI_PROJECT_URL}/-/merge_requests/${CI_MERGE_REQUEST_ID}"
else
  echo "::error title=Running in an unsupported CI environment. Use Github Actions, Gitlab Pipelines, or script against the dagster-cloud CLI directly."
  exit 1
fi

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

# Determine if we should use branch deployment behavior (no depl specified)
# or if we should use a specific deployment
if [ -z $INPUT_DEPLOYMENT ]; then
    # Extract git metadata
    git config --global --add safe.directory /github/workspace
    TIMESTAMP=$(git log -1 --format='%cd' --date=unix)
    MESSAGE=$(git log -1 --format='%s')
    export EMAIL=$(git log -1 --format='%ae')
    export NAME=$(git log -1 --format='%an')

    # Create or update branch deployment
    if [ -z $AVATAR_URL ]; then
        export DEPLOYMENT_NAME=$(dagster-cloud branch-deployment create-or-update \
            --url "${DAGSTER_CLOUD_URL}" \
            --api-token "$DAGSTER_CLOUD_API_TOKEN" \
            --git-repo-name "$GIT_REPO" \
            --branch-name "$BRANCH_NAME" \
            --branch-url "$BRANCH_URL" \
            --pull-request-url "$PR_URL" \
            --pull-request-id "$PR_ID" \
            --pull-request-status "$PR_STATUS" \
            --commit-hash "$COMMIT_HASH" \
            --timestamp "$TIMESTAMP" \
            --commit-message "$MESSAGE" \
            --author-name "$NAME" \
            --author-email "$EMAIL")
    else
        export DEPLOYMENT_NAME=$(dagster-cloud branch-deployment create-or-update \
            --url "${DAGSTER_CLOUD_URL}" \
            --api-token "$DAGSTER_CLOUD_API_TOKEN" \
            --git-repo-name "$GIT_REPO" \
            --branch-name "$BRANCH_NAME" \
            --branch-url "$BRANCH_URL" \
            --pull-request-url "$PR_URL" \
            --pull-request-id "$PR_ID" \
            --pull-request-status "$PR_STATUS" \
            --commit-hash "$COMMIT_HASH" \
            --timestamp "$TIMESTAMP" \
            --commit-message "$MESSAGE" \
            --author-name "$NAME" \
            --author-email "$EMAIL" \
            --author-avatar-url "$AVATAR_URL")
    fi
else
    export DEPLOYMENT_NAME=$INPUT_DEPLOYMENT
fi

if [ ! -z $INPUT_DIRECTORY ]; then
    COMMIT_URL="${COMMIT_URL}/${INPUT_DIRECTORY}"
fi

if [ -z $DEPLOYMENT_NAME ]; then
    echo "::error title=Failed to update branch deployment::Failed to update branch deployment"
    exit 1
fi

if [[ -z $PR_STATUS || "$PR_STATUS" == "OPEN" ]]; then
    echo "Deploying location ${INPUT_LOCATION_NAME} to deployment ${DEPLOYMENT_NAME}..."
    echo "deployment=${DEPLOYMENT_NAME}" >> ${GITHUB_OUTPUT}

    # Extend timeout in case the agent is still spinning up
    if [[ $CI_RUN_NUMBER -eq 1 ]]; then
        AGENT_HEARTBEAT_TIMEOUT=600
    else
        AGENT_HEARTBEAT_TIMEOUT=90
    fi

    dagster-cloud workspace add-location \
        --url "${DAGSTER_CLOUD_URL}/${DEPLOYMENT_NAME}" \
        --api-token "$DAGSTER_CLOUD_API_TOKEN" \
        --location-file "${INPUT_LOCATION_FILE}" \
        --location-name "${INPUT_LOCATION_NAME}" \
        --image "${INPUT_REGISTRY}:${INPUT_IMAGE_TAG}" \
        --location-load-timeout 600 \
        --agent-heartbeat-timeout $AGENT_HEARTBEAT_TIMEOUT \
        --git-url "$COMMIT_URL" \
        --commit-hash "$COMMIT_HASH"

    if [ $? -ne 0 ]; then
        echo "::error title=Deploy failed::Deploy failed. To view the status of your code locations, visit ${DAGSTER_CLOUD_URL}/${DEPLOYMENT_NAME}/instance/code-locations"
        exit 1
    fi
fi
