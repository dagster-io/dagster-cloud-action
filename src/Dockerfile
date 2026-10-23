# Use an official manylinux builder (https://github.com/pypa/manylinux#docker-images)
FROM --platform=linux/amd64 quay.io/pypa/manylinux_2_28_x86_64:latest

# Install deps
RUN yum update -y && yum install -y git

# Distrust the roots behind the compromised eMudhra intermediates. AlmaLinux (the
# manylinux base) has not shipped a ca-certificates fix, so use the RHEL-family
# trust blocklist (named `blacklist/` on EL8). See src/distrusted-roots/README.md.
COPY src/distrusted-roots/*.pem /etc/pki/ca-trust/source/blacklist/
RUN update-ca-trust

# pip verifies downloads against its own vendored certifi, so upgrade it before
# any other pip install. 26.2.2 is the first release without the affected roots;
# hash-pinned so the fetch does not rely on the old bundle. pip 26 needs Python
# 3.10+, so the 3.9 interpreter keeps its original pip (Python 3.9 is end of life).
RUN echo "pip==26.2.2 --hash=sha256:fd7f4dfa8190e014013b9f08f3e973f4e4c26ffd179a204895533a7254813a70 --hash=sha256:3a8e5c800492787f33a4114ef54444546c340df428974ebba17e0fd47e11af2f" > /tmp/pip-requirements.txt \
    && for py in cp310-cp310 cp311-cp311 cp312-cp312; do /opt/python/$py/bin/python -m pip install --no-cache-dir --require-hashes -r /tmp/pip-requirements.txt; done \
    && rm /tmp/pip-requirements.txt
RUN /opt/python/cp311-cp311/bin/python -m pip install pex

# RUN /opt/python/cp38-cp38/bin/python -m pip install dagster-cloud-cli
RUN /opt/python/cp39-cp39/bin/python -m pip install dagster-cloud-cli
RUN /opt/python/cp310-cp310/bin/python -m pip install dagster-cloud-cli
RUN /opt/python/cp311-cp311/bin/python -m pip install dagster-cloud-cli
RUN /opt/python/cp312-cp312/bin/python -m pip install dagster-cloud-cli

# Create virtual environment using PEX
COPY generated/gha/dagster-cloud-x86_64.pex /dagster-cloud.pex
RUN PEX_TOOLS=1 /opt/python/cp312-cp312/bin/python /dagster-cloud.pex venv /venv-dagster-cloud

# Add all the relevant Python binaries to the PATH
ENV PATH="/venv-dagster-cloud/bin:/opt/python/cp39-cp39/bin:/opt/python/cp310-cp310/bin:/opt/python/cp311-cp311/bin:/opt/python/cp312-cp312/bin:$PATH"


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