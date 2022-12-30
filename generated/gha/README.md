# builder.pex

The builder.pex is checked into this directory and used by the `build_deploy_python_executable`
GitHub action.

## Updating

To build and publish new version of builder.pex:

```
cd dagster-cloud-action

# make sure the code is good - note this builds a builder.pex and tests it
pytest tests

# Build a new builder.pex, written to src/pexbuilder/build/builder.pex
# Optionally use an internal version
# export PEX_BUILDER_SRC_DIR=/path/to/internal/../pex_builder
./src/pex-builder/build-builder.sh

# Copy to this directory
cp src/pex-builder/build/builder.pex generated/gha

# Commit it
git add generate/gha
git commit -m "Updated builder.pex"
```

Note the new builder.pex is at HEAD but not live since the GitHub workflow uses the `pex-v0.1` tag.
The new version can be tested by any workflow by removing the `@pex-v0.1` suffix in the workflow.

To make the new version live, upgrade HEAD to the released tag. See CONTRIBUTING.md.
