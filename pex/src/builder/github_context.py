import json
import logging
import os
import pprint
import subprocess
import time
from typing import Dict

# Loads event details from within a gihub action


class GithubEvent:
    def __init__(self, project_dir: str):
        self.github_server_url = os.getenv("GITHUB_SERVER_URL")
        self.github_sha = os.getenv("GITHUB_SHA")
        event_path = os.getenv("GITHUB_EVENT_PATH")
        if not event_path:
            raise ValueError("GITHUB_EVENT_PATH not set")

        # json details: https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads
        self.event = event = json.load(open(event_path))

        # get some commonly used fields
        # not all events have "action", eg https://docs.github.com/en/developers/webhooks-and-events/webhooks/webhook-events-and-payloads#push
        self.action = event.get("action")
        self.github_sha = self.event["after"]
        self.repo_name = event["repository"]["full_name"]

        if "pull_request" in self.event:
            pull_request = self.event["pull_request"]
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


def github_event(project_dir) -> GithubEvent:
    return GithubEvent(project_dir)


if __name__ == "__main__":
    import sys

    pprint.pprint(get_git_commit_metadata(sys.argv[1], ".'"))
