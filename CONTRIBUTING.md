## Pushing image to GitHub Container Registry

To push a new copy of the Action Dockerfile to GitHub Container Registry, you will first need to [authenticate to GHCR with a PAT](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry).

Then, build, tag, and push your image: 

```sh
cd src
docker build . -t ghcr.io/dagster-io/dagster-cloud-action:my-version
docker push ghcr.io/dagster-io/dagster-cloud-action:my-version
```
