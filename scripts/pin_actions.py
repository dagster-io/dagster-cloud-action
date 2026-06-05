#!/usr/bin/env python3
"""Pin third-party GitHub Action references to commit SHAs.

Walks YAML files in the repo, finds `uses: owner/repo@tag` references,
resolves each tag to a SHA via the GitHub API, and replaces with
`uses: owner/repo@SHA # tag`.

Skips local path references (./), self-references (dagster-io/dagster-cloud-action),
and references already pinned to a SHA. Re-running is a no-op.

Usage:
    python scripts/pin_actions.py [--repo-dir DIR] [--dry-run]
    python scripts/pin_actions.py --check [--repo-dir DIR]

--check does not modify anything: it parses every YAML file (rather than
regex-scanning it) and exits non-zero if any third-party `uses:` reference is
not pinned to a full commit SHA. Used as a verification gate after pinning.

Authentication uses GITHUB_TOKEN from the environment if set (recommended in CI
to avoid rate limits); falls back to unauthenticated requests.
"""

import argparse
import os
import re
import sys
from pathlib import Path

import requests
import yaml

SELF_REPO = "dagster-io/dagster-cloud-action"

# Matches: uses: owner/repo@ref  or  uses: owner/repo/path@ref
# Captures: (1) prefix "uses: ", (2) full action path, (3) owner/repo, (4) optional /subpath, (5) ref
ACTION_USES_RE = re.compile(
    r"(uses:\s+)"  # group 1: "uses:" + whitespace
    r"(([a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+)"  # group 2 start + group 3: owner/repo
    r"(/[^\s@]*)?)"  # group 4: optional /subpath; closes group 2
    r"@([^\s#]+)"  # group 5: ref (everything after @ until whitespace or #)
)

SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def resolve_ref_to_sha(owner_repo: str, ref: str, github_token: str | None) -> str:
    """Resolve a GitHub action ref (tag/branch) to its commit SHA."""
    headers = {"Accept": "application/vnd.github+json"}
    if github_token:
        headers["Authorization"] = f"Bearer {github_token}"
    response = requests.get(
        f"https://api.github.com/repos/{owner_repo}/commits/{ref}",
        headers=headers,
    )
    response.raise_for_status()
    return response.json()["sha"]


def find_yaml_files(repo_dir: str) -> list:
    # Note: pathlib.rglob (unlike glob.glob) descends into hidden directories,
    # which matters for .github/workflows/.
    root = Path(repo_dir)
    return sorted(
        str(p)
        for p in set(root.rglob("*.yml")) | set(root.rglob("*.yaml"))
        if ".git" not in p.relative_to(root).parts  # skip the git object dir itself
    )


def collect_refs_to_resolve(yaml_files: list) -> dict:
    """Collect unique (owner/repo, ref) pairs that need pinning."""
    refs_to_resolve = {}
    for filepath in yaml_files:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()
        for match in ACTION_USES_RE.finditer(content):
            owner_repo = match.group(3)
            ref = match.group(5)
            if owner_repo == SELF_REPO:
                continue
            if SHA_RE.match(ref):
                continue
            refs_to_resolve.setdefault((owner_repo, ref), "")
    return refs_to_resolve


def pin_third_party_actions_to_shas(
    repo_dir: str, github_token: str | None, dry_run: bool = False
) -> int:
    """Pin third-party action refs in repo_dir. Returns the number of files changed."""
    yaml_files = find_yaml_files(repo_dir)
    refs_to_resolve = collect_refs_to_resolve(yaml_files)

    for owner_repo, ref in refs_to_resolve:
        sha = resolve_ref_to_sha(owner_repo, ref, github_token)
        refs_to_resolve[(owner_repo, ref)] = sha
        print(f"Resolved {owner_repo}@{ref} -> {sha}")

    changed = 0
    for filepath in yaml_files:
        with open(filepath, encoding="utf-8") as f:
            content = f.read()

        new_content = content
        for (owner_repo, ref), sha in refs_to_resolve.items():
            # Replace: owner/repo@ref and owner/repo/path@ref
            # With: owner/repo@SHA # ref
            new_content = re.sub(
                rf"(uses:\s+{re.escape(owner_repo)}(?:/[^\s@]*)?)@{re.escape(ref)}",
                rf"\1@{sha} # {ref}",
                new_content,
            )

        if new_content != content:
            changed += 1
            if dry_run:
                print(f"Would pin action refs in {filepath}")
            else:
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"Pinned action refs in {filepath}")

    return changed


class _LenientLoader(yaml.SafeLoader):
    """SafeLoader that tolerates unknown tags (e.g. GitLab's !reference)."""


_LenientLoader.add_multi_constructor("", lambda loader, suffix, node: None)


def _iter_uses_values(node):
    """Yield every value of a `uses` key anywhere in a parsed YAML tree.

    Walking the whole tree (rather than assuming workflow/composite-action
    schemas) covers steps, reusable-workflow jobs, and composite actions alike.
    """
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "uses" and isinstance(value, str):
                yield value
            else:
                yield from _iter_uses_values(value)
    elif isinstance(node, list):
        for item in node:
            yield from _iter_uses_values(item)


def check_all_actions_pinned(repo_dir: str) -> int:
    """Verify every third-party `uses:` ref is SHA-pinned. Returns number of failures.

    Parses YAML properly, so quoted refs, anchors, and odd formatting that a
    regex scan could miss are all covered. Local paths (./) and
    dagster-cloud-action self-references are allowed; docker:// refs without a
    digest are reported as warnings (they cannot be SHA-pinned by this script).
    """
    failures = 0
    for filepath in find_yaml_files(repo_dir):
        with open(filepath, encoding="utf-8") as f:
            try:
                documents = list(yaml.load_all(f, Loader=_LenientLoader))
            except yaml.YAMLError as err:
                print(f"FAIL {filepath}: could not parse YAML: {err}")
                failures += 1
                continue

        for document in documents:
            for uses in _iter_uses_values(document):
                if uses.startswith("./"):
                    continue
                if uses.startswith("docker://"):
                    if "@sha256:" not in uses:
                        print(f"WARN {filepath}: docker ref without digest: {uses}")
                    continue
                path_part, _, ref = uses.partition("@")
                owner_repo = "/".join(path_part.split("/")[:2])
                if owner_repo == SELF_REPO:
                    continue
                if not SHA_RE.match(ref):
                    print(f"FAIL {filepath}: unpinned third-party ref: {uses}")
                    failures += 1
    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--repo-dir",
        default=os.path.join(os.path.dirname(__file__), ".."),
        help="Repository root to scan (default: this repo)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Resolve and report, but do not modify files",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Verify (via YAML parsing) that all third-party refs are SHA-pinned",
    )
    args = parser.parse_args()

    if args.check:
        failures = check_all_actions_pinned(os.path.abspath(args.repo_dir))
        if failures:
            print(f"Check failed: {failures} unpinned third-party reference(s)")
            return 1
        print("Check passed: all third-party action refs are pinned to SHAs")
        return 0

    github_token = os.environ.get("GITHUB_TOKEN")
    if not github_token:
        print("Warning: GITHUB_TOKEN not set; using unauthenticated API requests", file=sys.stderr)

    changed = pin_third_party_actions_to_shas(
        os.path.abspath(args.repo_dir), github_token, dry_run=args.dry_run
    )
    print(f"{'Would change' if args.dry_run else 'Changed'} {changed} file(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
