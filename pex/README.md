This directory contains code to build deps.pex and source.pex from user code.

The code is iself packaged as builder.pex. The Pipfile specifies dependencies
for the builder. ./build-builder.sh will build builder.pex locally. To run 
builder.pex in Github, the builder must be built from Github actions.
A builder.pex pre-built in Github actions using ubuntu-latest is checked in
at /generated/gha.

Examples:

`PROJECT_DIR` is the project root folder that contains setup.py/requirements.txt. 
`OUT_DIR` is any directory where the built files are written.

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
