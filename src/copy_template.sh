#!/bin/bash -

cp /Dockerfile.template ${INPUT_TARGET_DIRECTORY}/Dockerfile
cat $(python /expand_env_vars.py) >> ${INPUT_TARGET_DIRECTORY}/Dockerfile
