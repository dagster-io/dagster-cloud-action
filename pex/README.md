## Build PEX files from dagster projects

This directory contains the 'builder' which builds deps.pex and source.pex from user code.

The builder is itself packaged as a pex file: `builder.pex`. A multi-platform (macos, linux) builder.pex is automatically build in Github actions using ubuntu-latest and checked in
at /generated/gha. Also available as an artifact in the runs here: https://github.com/dagster-io/dagster-cloud-action-pex/actions/workflows/build-builder.yml


Run `./build-builder.sh` to build builder.pex locally. The Pipfile specifies dependencies for the builder. 

## Examples:

`PROJECT_DIR` is the project root folder that contains `setup.py` and `dagster_cloud.yaml`
`OUT_DIR` is any directory where the built pex files are written. It is auto created if missing.

```
builder.pex -m builder.selftest
builder.pex -m builder.source <PROJECT_DIR> <OUT_DIR>  # build the source pex file
builder.pex -m builder.deps <PROJECT_DIR> <OUT_DIR>    # build the deps pex file
```

The `builder.deploy` module builds both source and deps pexes and optionally pushes them to s3 and updates the code location.

```
# Build both source and deps pex for a given yaml file:
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>   

# Build both pex files and upload to s3. 
# First run `elementl cloud run local-host-cloud` so this can use the s3 presigned URL generator API.

export DAGSTER_CLOUD_API_TOKEN=user:test:shalabh
export DAGSTER_CLOUD_URL=http://localhost:3000/test
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>  --enable-pex-registry

# Build both pex files, upload to s3 and update the dagster code location.
# NOTE: does not work locally because it reads some environment vars and files from the github action context.
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>  --enable-pex-registry --deploy
```

Embedded CLIs can also be directly invoked:

```
builder.pex -m dagster_cloud_cli.entrypoint --version
builder.pex -m dagster --version
```
