# Builds a docker image containing builder.pex
# Can be invoked to build a linux pex on any other platform

# Build docker image:
# $ docker build . -f Dockerfile.builder  --platform=linux/amd64
#
# Run docker image to build the source-HASH.pex and deps-HASH.pex files:
# $ docker run -it -v PATH_TO_SOURCE:/input_code -v PATH_TO_OUTPUT_DIR:/output_pex DOCKER_IMAGE_TAG
#          /builder/pex -m builder.deploy /input_code/dagster_cloud.yaml /output_pex
# 

FROM python:3.8.12-slim

COPY build-builder.sh /build-builder.sh
COPY Pipfile /Pipfile
COPY Pipfile.lock /Pipfile.lock

COPY src /src
RUN ./build-builder.sh

# unzip the pex for faster startup
RUN PEX_TOOLS=1 /build/builder.pex venv --compile /builder

CMD [ "/builder/pex" ]
