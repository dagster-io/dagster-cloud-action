This directory contains code to build deps.pex and source.pex from user code.

The code is iself packages as builder.pex. The Pipfile specifies dependencies
for the builder. ./build-builder.sh will build builder.pex locally. To run 
builder.pex in Github, the builder must be built from Github actions.

Examples:

```
builder.pex -m builder.selftest
builder.pex -m builder.source <PROJECT_DIR> <OUT_DIR>
builder.pex -m builder.deps <PROJECT_DIR> <OUT_DIR>
```

Embedded CLIs can also be invoked:

```
builder.pex -m dagster_cloud_cli.entrypoint --version
builder.pex -m dagster --version
```
