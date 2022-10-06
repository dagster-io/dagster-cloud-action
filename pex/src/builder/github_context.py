import json
import os
import time

# Loads event details from within a gihub action


class GithubEvent:
    def __init__(self):
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
        self.repo_name = event["repository"]["full_name"]

        if "pull_request" in self.event:
            pull_request = self.event["pull_request"]
            self.branch_name = pull_request["head"]["ref"]
            # GITHUB_SHA is set to a merge commit, not the actual commit that triggered the action
            # we can read head sha for the actual commit
            self.github_sha = pull_request["head"]["sha"]
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

        # TODO: read some info from git
        self.timestamp = time.time()
        # self.commit_msg =
        # self.author_name =
        # self.author_email =


def github_event() -> GithubEvent:
    return GithubEvent()
