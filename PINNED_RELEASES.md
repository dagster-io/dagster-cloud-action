# Pinned releases

Pinned releases are variants of regular `dagster-cloud-action` releases in which
every **third-party** GitHub Action reference is pinned to a full commit SHA
instead of a mutable tag:

```yaml
# regular release (v1.13.8)
- uses: actions/checkout@v4

# pinned release (v1.13.8-pinned)
- uses: actions/checkout@34e114876b0b11c390a56381ad16ebd13914f8d5 # v4
```

A tag like `actions/checkout@v4` can be re-pointed at any time by whoever
controls that repository; a commit SHA cannot. Pinning closes off the
supply-chain risk of a compromised or hijacked third-party action being pulled
into your deploys.

A pinned release is built from an existing release tag (e.g. `v1.13.8`) and
published as `<base_tag>-pinned` (e.g. `v1.13.8-pinned`). The base tag is never
modified, and the pinned variant reuses the base release's binaries — no
rebuild happens.

## Using a pinned release

### 1. Pick a pinned release and resolve its commit SHA

```bash
# list available pinned tags
git ls-remote --tags https://github.com/dagster-io/dagster-cloud-action 'refs/tags/*-pinned'

# resolve a pinned tag to its commit SHA
gh api repos/dagster-io/dagster-cloud-action/commits/v1.13.8-pinned --jq .sha
```

Note: use the command above (or the commit shown on the release page), not
`git ls-remote`'s tag object SHA — annotated tags have their own SHA distinct
from the commit they point to, and `uses:` needs the **commit** SHA.

### 2. Update your workflow files

In your repository's `.github/workflows/*.yml`, replace each
`dagster-io/dagster-cloud-action` version tag with the commit SHA, keeping the
tag as a comment for readability:

```yaml
# before
- uses: dagster-io/dagster-cloud-action/actions/serverless_prod_deploy@v1.13.8

# after
- uses: dagster-io/dagster-cloud-action/actions/serverless_prod_deploy@83e0bb0323b0a0d136b815d049261bddcbd8963d # v1.13.8-pinned
```

All `actions/...` subpaths use the same SHA — it identifies the whole
repository tree at that release. With `sed`:

```bash
SHA=$(gh api repos/dagster-io/dagster-cloud-action/commits/v1.13.8-pinned --jq .sha)
sed -i '' -E \
  "s|(dagster-io/dagster-cloud-action[^@[:space:]]*)@v[0-9][^[:space:]]*|\1@${SHA} # v1.13.8-pinned|" \
  .github/workflows/*.yml
```

(On Linux use `sed -i -E ...` without the `''`.)

While you're at it, consider pinning the *other* third-party actions in your
workflows the same way (`actions/checkout`, etc.) —
[`scripts/pin_actions.py`](scripts/pin_actions.py) shows the pattern, and tools
like [zizmor](https://github.com/woodruffw/zizmor) or
[ratchet](https://github.com/sethvargo/ratchet) can do it for arbitrary repos.

### 3. Verify

Trigger a branch deploy (or any workflow run) and confirm it succeeds. The run
logs show each action resolved at the pinned SHA.

## What is and isn't pinned

| Layer | Pinned? |
| --- | --- |
| Your `uses: dagster-io/dagster-cloud-action/...@<SHA>` reference | ✅ immutable commit SHA |
| Third-party actions inside the pinned release | ✅ immutable commit SHAs |
| `dagster-cloud` PEX binaries | ✅ committed files in the pinned tree |
| `ghcr.io/dagster-io/dagster-cloud-action:<version>` Docker image | ⚠️ referenced by version tag, not digest |

The Docker image tag is the one remaining mutable reference; pinning images to
`@sha256:` digests is a possible future extension of the pinning script.

## Creating a pinned release

Maintainers can create a pinned variant of any existing release tag:

- **GitHub UI / CLI** (once the `Create Pinned Release` workflow is on `main`):

  ```bash
  gh workflow run create_pinned_release.yml -f base_tag=v1.13.8
  ```

  Optional `-f new_tag=...` overrides the default `<base_tag>-pinned` name.

- **Locally**:

  ```bash
  scripts/create_pinned_release.sh v1.13.8
  ```

Both paths run the same sequence: check out the base tag, pin third-party
refs to SHAs (`scripts/pin_actions.py`), rewrite
`dagster-io/dagster-cloud-action` self-references to the new tag, run a
YAML-parse verification gate (`pin_actions.py --check`), then commit and push
only the new tag.
