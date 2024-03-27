FROM --platform=linux/amd64 python:3.11-slim

# Install deps
RUN apt update && apt install git -y
RUN pip install pex

COPY generated/gha/dagster-cloud.pex /dagster-cloud.pex
RUN pex-tools dagster-cloud.pex venv /venv-dagster-cloud
ENV PATH="/venv-dagster-cloud/bin:$PATH"

# Copy all src scripts

# for setting the org-specific registry info
COPY src/registry_info.sh /registry_info.sh

# for copying the template info into the target source directories
COPY src/copy_template.sh /copy_template.sh
COPY src/Dockerfile.template /Dockerfile.template
COPY src/expand_env_vars.py /expand_env_vars.py

# Copy over various Python utilities
COPY src/create_or_update_comment.py /create_or_update_comment.py
COPY src/expand_json_env.py /expand_json_env.py
COPY src/fetch_github_avatar.py /fetch_github_avatar.py
COPY src/parse_workspace.py parse_workspace.py


COPY src/notify.sh /notify.sh
COPY src/deploy.sh /deploy.sh
COPY src/run.sh /run.sh
COPY src/get_branch_deployment.sh /get_branch_deployment.sh

# Gitlab scripts
COPY src/gitlab_action gitlab_action

# Use the venv python as the command
CMD venv-dagster-cloud/bin/python3
