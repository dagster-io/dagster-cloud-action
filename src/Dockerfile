FROM python:3.8.12-slim

# Install deps
RUN apt update && apt install git -y
RUN pip install --upgrade pip
RUN pip install dagster \
                dagster-cloud-cli \
                PyGithub

# for setting the org-specific registry info
COPY registry_info.sh /registry_info.sh

# for copying the template info into the target source directories
COPY copy_template.sh /copy_template.sh
COPY Dockerfile.template /Dockerfile.template
COPY expand_env_vars.py /expand_env_vars.py

# Copy over various Python utilities
COPY create_or_update_comment.py /create_or_update_comment.py
COPY expand_json_env.py /expand_json_env.py
COPY fetch_github_avatar.py /fetch_github_avatar.py


COPY notify.sh /notify.sh
COPY deploy.sh /deploy.sh
COPY run.sh /run.sh
