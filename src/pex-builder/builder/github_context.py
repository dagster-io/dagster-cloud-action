import json
import logging
import os
import pprint
import subprocess
from contextlib import contextmanager
from typing import Dict

from . import util

# Loads event details from within a github action


class GithubEvent:
    def __init__(self, project_dir: str):
        self.github_server_url = os.getenv("GITHUB_SERVER_URL")
        self.github_sha = os.getenv("GITHUB_SHA")
        self.github_repository = os.getenv("GITHUB_REPOSITORY")
        self.github_run_id = os.getenv("GITHUB_RUN_ID")
        self.github_run_url = f"{self.github_server_url}/{self.github_repository}/actions/runs/{self.github_run_id}"

        event_path = os.getenv("GITHUB_EVENT_PATH")
        if not event_path:
            raise ValueError("GITHUB_EVENT_PATH not set")

        # json details: https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads
        self.event = event = json.load(open(event_path))

        # get some commonly used fields
        # not all events have "action", eg https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#push
        self.action = event.get("action")
        self.repo_name = event["repository"]["full_name"]

        if "pull_request" in self.event:
            pull_request = self.event["pull_request"]
            # For PRs GITHUB_SHA is not the last commit in the branch, but head sha is
            self.github_sha = pull_request["head"]["sha"]
            self.branch_name = pull_request["head"]["ref"]
            self.branch_url = (
                f"{self.github_server_url}/{self.repo_name}/tree/{self.branch_name}"
            )
            self.pull_request_url = pull_request["html_url"]
            self.pull_request_id = pull_request["number"]
            self.pull_request_status = (
                "merged" if pull_request.get("merged") else pull_request["state"]
            )
        else:
            self.branch_name = None
            self.branch_url = None
            self.pull_request_url = None
            self.pull_request_id = None
            self.pull_request_status = None

        self.commit_url = (
            f"{self.github_server_url}/{self.repo_name}/tree/{self.github_sha}"
        )

        git_metadata = get_git_commit_metadata(self.github_sha, project_dir)
        self.timestamp = float(git_metadata["timestamp"])
        self.commit_msg = git_metadata["message"]
        self.author_name = git_metadata["name"]
        self.author_email = git_metadata["email"]


def get_git_commit_metadata(github_sha: str, project_dir: str) -> Dict[str, str]:
    commands = {
        "timestamp": f"git -C {project_dir} log -1 --format=%cd --date=unix".split(),
        "message": f"git -C {project_dir} log -1 --format=%s".split(),
        "email": f"git -C {project_dir} log -1 --format=%ae".split(),
        "name": f"git -C {project_dir} log -1 --format=%an".split(),
    }
    metadata = {}
    for key, command in commands.items():
        logging.debug("Running %r", command + [github_sha])
        proc = subprocess.run(command + [github_sha], capture_output=True)
        if proc.returncode:
            logging.error("git command failed: %s\n%s", proc.stdout, proc.stderr)
        metadata[key] = proc.stdout.decode("utf-8").strip()

    return metadata


def get_github_event(project_dir) -> GithubEvent:
    return GithubEvent(project_dir)


def update_pr_comment(
    github_event: GithubEvent, action, deployment_name, location_name
):
    "Add or update the status comment on a github PR"
    # This reuses the src/create_or_update_comment.py script.
    # We can't reuse actions/utils/notify here because we need to run this once for every location.
    # To repeat an action github provides a matrix strategy but we don't use matrix due to latency
    # concerns (it would launch a new container for every location)
    script = os.path.join(os.path.abspath(os.curdir), "src/create_or_update_comment.py")
    if not os.path.exists(script):
        raise ValueError("File not found", script)
    env = {
        name: value for name, value in os.environ.items() if not name.startswith("PEX_")
    }
    # export GITHUB_RUN_URL=
    pr_id = str(github_event.pull_request_id)

    env.update(
        {
            "INPUT_PR": pr_id,
            "INPUT_ACTION": action,
            "INPUT_DEPLOYMENT": deployment_name,
            "INPUT_LOCATION_NAME": location_name,
            "GITHUB_RUN_URL": github_event.github_run_url,
        }
    )
    proc = util.run_python_subprocess([script], env=env)
    if proc.returncode:
        logging.error("Could not update PR comment: %s\n%s", proc.stdout, proc.stderr)


@contextmanager
def log_group(title: str):
    try:
        print(f"\n::group::{title}", flush=True)
        yield
    finally:
        print("::endgroup::", flush=True)


if __name__ == "__main__":
    import sys

    pprint.pprint(get_git_commit_metadata(sys.argv[1], ".'"))
