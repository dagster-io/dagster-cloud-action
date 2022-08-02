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

# Determine if we should use branch deployment behavior (no depl specified)
# or if we should use a specific deployment
if [ -z $INPUT_DEPLOYMENT ]; then
    # Extract git metadata
    TIMESTAMP=$(git log -1 --format='%cd' --date=unix)
    MESSAGE=$(git log -1 --format='%s')
    export EMAIL=$(git log -1 --format='%ae')
    export NAME=$(git log -1 --format='%an')

    STATUS_CAPS=`echo $INPUT_PR_STATUS | tr '[a-z]' '[A-Z]'`

    # Assemble github URLs
    PR_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/pull/${INPUT_PR}"
    BRANCH_URL="${GITHUB_SERVER_URL}/${GITHUB_REPOSITORY}/tree/${GITHUB_HEAD_REF}"

    AVATAR_URL=$(python /fetch_github_avatar.py)

    # Create or update branch deployment
    if [ -z $AVATAR_URL ]; then
        export DEPLOYMENT_NAME=$(dagster-cloud branch-deployment create-or-update \
            --url "${DAGSTER_CLOUD_URL}" \
            --api-token "$DAGSTER_CLOUD_API_TOKEN" \
            --git-repo-name "$GITHUB_REPOSITORY" \
            --branch-name "$GITHUB_HEAD_REF" \
            --branch-url "$BRANCH_URL" \
            --pull-request-url "$PR_URL" \
            --pull-request-id "$INPUT_PR" \
            --pull-request-status "$STATUS_CAPS" \
            --commit-hash "$GITHUB_SHA" \
            --timestamp "$TIMESTAMP" \
            --commit-message "$MESSAGE" \
            --author-name "$NAME" \
            --author-email "$EMAIL")
    else
        export DEPLOYMENT_NAME=$(dagster-cloud branch-deployment create-or-update \
            --url "${DAGSTER_CLOUD_URL}" \
            --api-token "$DAGSTER_CLOUD_API_TOKEN" \
            --git-repo-name "$GITHUB_REPOSITORY" \
            --branch-name "$GITHUB_HEAD_REF" \
            --branch-url "$BRANCH_URL" \
            --pull-request-url "$PR_URL" \
            --pull-request-id "$INPUT_PR" \
            --pull-request-status "$STATUS_CAPS" \
            --commit-hash "$GITHUB_SHA" \
            --timestamp "$TIMESTAMP" \
            --commit-message "$MESSAGE" \
            --author-name "$NAME" \
            --author-email "$EMAIL" \
            --author-avatar-url "$AVATAR_URL")
    fi
else
    export DEPLOYMENT_NAME=$INPUT_DEPLOYMENT
fi


if [ -z $DEPLOYMENT_NAME ]; then
    echo "Failed to update branch deployment"
    exit 1
fi

echo "Deploying location ${INPUT_LOCATION_NAME} to deployment ${DEPLOYMENT_NAME}..."

echo "::set-output name=deployment::${DEPLOYMENT_NAME}"

dagster-cloud workspace add-location \
    --url "${DAGSTER_CLOUD_URL}/${DEPLOYMENT_NAME}" \
    --api-token "$DAGSTER_CLOUD_API_TOKEN" \
    --location-file "${INPUT_LOCATION_FILE}" \
    --location-name "${INPUT_LOCATION_NAME}" \
    --image "${INPUT_REGISTRY}:${INPUT_IMAGE_TAG}" \
    --location-load-timeout 600 \
    --agent-heartbeat-timeout 90
