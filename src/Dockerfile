# Use an official manylinux builder (https://github.com/pypa/manylinux#docker-images)

ARG TARGET_ARCH

FROM quay.io/pypa/manylinux_2_28_${TARGET_ARCH}:latest

ARG DAGSTER_VERSION

# Install deps
RUN yum update -y && yum install -y git

RUN /opt/python/cp39-cp39/bin/python -m pip install dagster==${DAGSTER_VERSION} dagster-cloud-cli
RUN /opt/python/cp310-cp310/bin/python -m pip install dagster==${DAGSTER_VERSION} dagster-cloud-cli
RUN /opt/python/cp311-cp311/bin/python -m pip install dagster==${DAGSTER_VERSION} dagster-cloud-cli
RUN /opt/python/cp312-cp312/bin/python -m pip install dagster==${DAGSTER_VERSION} dagster-cloud-cli PyGithub 'pex>=2.1.132,<3'

# Add all the relevant Python binaries to the PATH
ENV PATH="/opt/python/cp312-cp312/bin:/opt/python/cp311-cp311/bin:/opt/python/cp310-cp310/bin:/opt/python/cp39-cp39/bin:$PATH"

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

CMD /opt/python/cp312-cp312/bin/python