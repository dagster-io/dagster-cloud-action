# Steps to release

## Step 1. Log into docker ghcr.io

See [authenticate to GHCR with a PAT](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-container-registry#authenticating-to-the-container-registry).
Your PAT will need `delete:packages`, `write:packages`, and`repo` permissions.

If you have a PAT handy you can just do:

```
% echo $YOUR_GITHUB_PAT | docker login ghcr.io -u $YOUR_GITHUB_USERNAME --password-stdin
```

You will also need to be an owner in the dagster-io organization in order to push packages.

## Step 2. Determine the new point version and create a release branch,

```
% git checkout main
% git fetch origin --tags --force
% git tag
pex-v0.1
pex-v0.1.14
prha
v0.1
v0.1.10
v0.1.11
v0.1.12
v0.1.13
v0.1.14
v0.1.15
v0.1.16
v0.1.17
v0.1.18
v0.1.19
v0.1.20
v0.1.21
```

The point version is the next unused `v0.1.*` version, eg `v0.1.22` above. Create a release branch

```
% git checkout -b release-0.1.22
```

## Step 3. Build and deploy a new docker-cloud-action image, a new dagster.cloud.pex and update code references to docker

A script does this work:

```
# Note no 'v' prefix
# This accepts `NEW_VERSION OLD_VERSION` so it can update code references from the old to the new version.
% python scripts/release.py create-rc 0.1.22 0.1.21

```

Note that `OLD_VERSION` may not be the latest tag printed in step 2. You can find the `OLD_VERSION` by looking
at the version for `dagster-cloud-action` used in https://github.com/dagster-io/dagster-cloud-action/blob/main/actions/utils/copy_template/action.yml or by looking at the release date for v0.1 and finding the dot version with the same date on the [tags page](https://github.com/dagster-io/dagster-cloud-action/tags)

Running the script leaves uncommited changes in the working directory.

# Commit and tag the new version

```
View changes made by the release script
% git diff

# Commit
% git add . && git commit -m "Rebuild"

# Tag: using '-a' lets us add an annotation message, typically we use the version "v0.1.22"
% git tag -a v0.1.22
```

# Step 5. Push and Test

```
# push the release branch
% git push --set-upstream origin release-0.1.22
# push the tag
% git push origin v0.1.22
# to test, change the reference in a github workflow yaml file `@v0.1 -> @v0.1.22` and `@pex-v0.1 -> @v0.1.22`
# see also dagster-cloud-action-test
```

# Step 6. Promote
Most users point at a dot version tag for the GitHub Action, e.g. `@v0.1` and `@pex-v0.1`.
If you are releasing a fix or non-breaking feature, you want to move this tag so existing users get access to your changes.

```
# use '-f' to force move the tag, since these tags already exist
git tag -f v0.1 v0.1.22
git tag -f pex-v0.1 v0.1.22

# needs a force push to move remote tags
git push -f origin v0.1
git push -f origin pex-v0.1
```

Note: both `v0.1` and `pex-v0.1` tags should be kept in sync.

# Step 7. Merge the release branch into main

Create a PR, get approval, merge.

# Step 8. (optional) Revert

To revert, just tag the previous point version with the live tag and re push

```
git tag -f v0.1 v0.1.21
git tag -f pex-v0.1 v0.1.21
git push -f origin v0.1
git push -f origin pex-v0.1
```
