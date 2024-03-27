#!/bin/bash -

if [ -z $CUSTOM_BASE_IMAGE_ALLOWED ] || [ -z $INPUT_BASE_IMAGE ]; then
    if [ ! -z $INPUT_BASE_IMAGE ]; then
        echo "Custom base images are not enabled for this organization, defaulting to python:3.11-slim."
    fi
    echo "FROM python:3.11-slim" > ${INPUT_TARGET_DIRECTORY}/Dockerfile
else
    echo "FROM ${INPUT_BASE_IMAGE}" > ${INPUT_TARGET_DIRECTORY}/Dockerfile
fi


cat $(python /expand_env_vars.py) >> ${INPUT_TARGET_DIRECTORY}/Dockerfile
cat /Dockerfile.template >> ${INPUT_TARGET_DIRECTORY}/Dockerfile
