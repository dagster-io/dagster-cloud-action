# Updating Action Dockerfile

If any of the shell scripts are altered in a change to the GitHub Action, the Dockerfile which they are contained in must be rebuilt, and references to the Dockerfile must be updated.

## Pushing image to GitHub Container Registry

To push a new copy of the Action Dockerfile to GitHub Container Registry, you will first need to [authenticate to GHCR with a PAT](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry).

Then, test, build, tag, and push your image: 

```sh
pytest tests
cd src
docker build . -t ghcr.io/dagster-io/dagster-cloud-action:my-version
docker push ghcr.io/dagster-io/dagster-cloud-action:my-version
```

## Updating references to Dockerfile

Once pushed, you will also need to find and replace the references to the previous action tag in `/actions/utils/**.yml` files:

```
  image: "docker://ghcr.io/dagster-io/dagster-cloud-action:my-version"
```

# Moving version tag

Most users point at a dot version tag for the GitHub Action, e.g. `@v0.1`. If you are releasing a fix or non-breaking feature, you may want to move this tag so existing users get access to your changes. 

To update the tag, on the main branch, run e.g.
```
git tag -fa v0.1 
git tag -fa pex-v0.1
git push --tags -f
```

Note: both `v0.1` and `pex-v0.1` tags should be kept in sync.
