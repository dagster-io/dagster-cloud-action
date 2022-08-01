from github import Github
import os

"""
Fetches a user's avatar from the Github API based on email or username
"""


def main():
    # Fetch various pieces of info from the environment
    g = Github(os.getenv("GITHUB_TOKEN"))

    repo_id = os.getenv("GITHUB_REPOSITORY")
    commit_sha = os.getenv("GITHUB_SHA")

    repo = g.get_repo(repo_id)
    commit = repo.get_commit(commit_sha)

    print(commit.author.avatar_url)


if __name__ == "__main__":
    main()
