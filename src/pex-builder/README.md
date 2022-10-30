## Build PEX files from dagster projects

This directory contains the 'builder' which builds deps.pex and source.pex from user code.

The builder is itself packaged as a pex file: `builder.pex`. A multi-platform (macos, linux) builder.pex is built and checked in at /generated/gha.

Run `./build-builder.sh` to build builder.pex locally. The Pipfile specifies dependencies for the builder. 

## Examples:

`PROJECT_DIR` is the project root folder that contains `setup.py` and `dagster_cloud.yaml`
`OUT_DIR` is any directory where the built pex files are written. It is auto created if missing.

```
builder.pex -m builder.selftest
builder.pex -m builder.source <PROJECT_DIR> <OUT_DIR>  # build the source pex file
builder.pex -m builder.deps <PROJECT_DIR> <OUT_DIR>    # build the deps pex file
```

The `builder.deploy` module builds both source and deps pexes and optionally uploads the pex files and updates the code location.

```
# Build both source and deps pex for a given yaml file:
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>   

# Build both pex files and upload to the pex registry.

export DAGSTER_CLOUD_API_TOKEN=...
export DAGSTER_CLOUD_URL=...
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>  --upload-pex

# Build both pex files, upload to the pex registry and update the dagster code location.
# NOTE: by default this infers code location details from the github action context. It also
# creates a branch deployment if needed.
export DAGSTER_CLOUD_API_TOKEN=...
export DAGSTER_CLOUD_URL=...
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>  --upload-pex --update-code-location


# To run outside a github action context, eg locally, provide the --code-location-details
export DAGSTER_CLOUD_API_TOKEN=...
export DAGSTER_CLOUD_URL=...
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR> --upload-pex  --update-code-location --code-location-details deployment=prod,commit_hash=local12345

# For a branch deployment, provide the deployment id (not the branch name) to the name in --code-location-details. This can be found in the URL when browsing a branch deployment.

```

By default, the `deps-HASH.pex` is not cached. To cache in the pex registry, provide any name to both `--deps-cache-tag-read` and `--deps-cache-tag-write`. A complete example using caching and local builds:

```
builder.pex -m builder.deploy <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR> --upload-pex --deps-cache-tag-read=local --deps-cache-tag-write=local --update-code-location --code-location-details deployment=prod,commit_hash=local12345
```

Embedded CLIs can be directly invoked:

```
builder.pex -m dagster_cloud_cli.entrypoint --version
builder.pex -m dagster --version
```

## Python version
 
Running `builder.pex` requires Python 3.8, however it can build pex files that target other versions:

```
# Build both pex files for python 3.9.
# Note both `python3.8` and `python3.9` must be available on the PATH. python3.9 is used to run
# the project's setup.py.
builder.pex -m builder.deploy --python-version=3.9 <PROJECT_DIR>/dagster_cloud.yaml <OUT_DIR>   
```
