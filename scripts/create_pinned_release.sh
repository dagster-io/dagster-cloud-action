#!/usr/bin/env bash
# Create a "-pinned" variant of an existing release tag, locally.
#
# Mirrors .github/workflows/create_pinned_release.yml: checks out the base
# tag, pins all third-party GitHub Action references to commit SHAs, rewrites
# dagster-cloud-action self-references to the new tag, verifies, then commits
# and pushes the result as a new tag. The base tag is never modified.
#
# Usage:
#   scripts/create_pinned_release.sh <base_tag> [new_tag]
#
#   base_tag  Existing release tag to pin (e.g. v1.13.8)
#   new_tag   Tag to create (default: <base_tag>-pinned)
#
# Requirements: git, uv, and either GITHUB_TOKEN set or `gh` authenticated.
# Run from a checkout that contains scripts/pin_actions.py (e.g. main once
# the workflow has landed, or the feature branch).

set -euo pipefail

# The whole script is wrapped in main() so bash parses the entire file before
# executing anything — `git checkout <base_tag>` below changes the file tree
# this script may live in, and bash otherwise reads scripts incrementally.
main() {
    local base_tag="${1:?usage: $0 <base_tag> [new_tag]}"
    local new_tag="${2:-${base_tag}-pinned}"
    local new_version="${new_tag#v}"  # release.py prepends the "v" itself

    local repo_root
    repo_root="$(git rev-parse --show-toplevel)"
    cd "$repo_root"

    # --- Preflight ----------------------------------------------------------
    if [[ -n "$(git status --porcelain)" ]]; then
        echo "ERROR: working tree not clean; commit or stash first" >&2
        exit 1
    fi
    if ! git rev-parse -q --verify "refs/tags/${base_tag}" > /dev/null; then
        echo "ERROR: base tag ${base_tag} not found (try: git fetch --tags)" >&2
        exit 1
    fi
    if git rev-parse -q --verify "refs/tags/${new_tag}" > /dev/null; then
        echo "ERROR: tag ${new_tag} already exists locally" >&2
        exit 1
    fi
    if [[ -n "$(git ls-remote --tags origin "refs/tags/${new_tag}")" ]]; then
        echo "ERROR: tag ${new_tag} already exists on origin" >&2
        exit 1
    fi
    if [[ ! -f scripts/pin_actions.py ]]; then
        echo "ERROR: scripts/pin_actions.py not in current checkout;" \
             "run from a ref that contains it" >&2
        exit 1
    fi

    if [[ -z "${GITHUB_TOKEN:-}" ]]; then
        GITHUB_TOKEN="$(gh auth token)"
        export GITHUB_TOKEN
    fi

    # Remember where we started so we can return afterwards.
    local original_ref
    original_ref="$(git symbolic-ref --short -q HEAD || git rev-parse HEAD)"

    # Base tags cut before the pin script landed don't contain it, so run a
    # copy from outside the worktree.
    local pin_script
    pin_script="$(mktemp -t pin_actions.XXXXXX.py)"
    cp scripts/pin_actions.py "$pin_script"

    echo "==> Checking out ${base_tag}"
    git checkout -q "$base_tag"

    echo "==> Pinning third-party action refs to SHAs"
    uv run -q --with requests --with PyYAML \
        python3 "$pin_script" --repo-dir "$repo_root"

    echo "==> Rewriting self-references to ${new_tag}"
    # Uses the base tag's own release.py, the same code path the release
    # pipeline runs.
    uv run -q --with typer --with rich \
        python3 scripts/release.py update-action-version-references "$new_version"

    echo "==> Verifying all third-party refs are pinned"
    uv run -q --with requests --with PyYAML \
        python3 "$pin_script" --check --repo-dir "$repo_root"

    echo "==> Committing and tagging ${new_tag}"
    git add .
    if git diff --cached --quiet; then
        echo "ERROR: no changes produced; is ${base_tag} already pinned?" >&2
        git checkout -q "$original_ref"
        exit 1
    fi
    git commit -q -m "Pinned release ${new_tag} (base: ${base_tag})"
    git tag -a "$new_tag" -m "Pinned release ${new_tag} (base: ${base_tag})"

    echo
    git show --stat HEAD | head -40
    echo
    read -r -p "Push ${new_tag} to origin? [y/N] " answer
    if [[ "$answer" == [yY]* ]]; then
        git push origin "$new_tag"
        echo "==> Pushed ${new_tag}"
    else
        echo "==> Not pushed. Push later with: git push origin ${new_tag}"
    fi

    # The commit is retained by the tag; safe to leave detached HEAD.
    git checkout -q "$original_ref"
    rm -f "$pin_script"
    echo "==> Done. Back on ${original_ref}."
}

main "$@"
