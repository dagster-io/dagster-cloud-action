import os
import subprocess
import tempfile
from typing import List, Mapping

import pytest


def run_dagster_cloud_serverless_cmd(args: List[str], map_folders: Mapping[str, str]):
    mount_args = []
    for target_folder, source_folder in map_folders.items():
        mount_args.extend(["--mount", f"type=bind,source={source_folder},target={target_folder}"])

    cmd = [
        "docker",
        "run",
        "--platform=linux/amd64",
        *mount_args,
        "-t",
        "test-dagster-cloud-pex",
        "-m",
        "dagster_cloud_cli.entrypoint",
        "serverless",
        *args,
    ]

    subprocess.run(cmd, encoding="utf-8", capture_output=False, check=True)


@pytest.fixture
def built_test_dagster_cloud_pex_image(repo_root: str):
    src_dir = os.path.join(os.path.dirname(__file__), "..", "src")

    cmd = [
        "docker",
        "build",
        "--progress=plain",
        "-t",
        "test-dagster-cloud-pex",
        "--platform=linux/amd64",
        "-f",
        os.path.join(src_dir, "Dockerfile.test-dagster-cloud-pex"),
        repo_root,
    ]

    subprocess.run(cmd, check=True)


def test_pex_build_only(repo_root, built_test_dagster_cloud_pex_image):
    dagster_project1 = repo_root / "tests/test-repos/dagster_project1"

    with tempfile.TemporaryDirectory() as build_output_dir:
        map_folders = {"/dagster_project1": dagster_project1, "/build_output_dir": build_output_dir}

        run_dagster_cloud_serverless_cmd(
            [
                "build-python-executable",
                "/dagster_project1",
                "--api-token=fake",
                "--url=fake",
                "--python-version=3.10",
                "/build_output_dir",
            ],
            map_folders=map_folders,
        )

        all_files = os.listdir(build_output_dir)
        pex_files = {
            filename for filename in all_files if filename.endswith(".pex") and filename != ".pex"
        }

        # one source-HASH.pex and one deps-HASH.pex file are expected
        assert 2 == len(pex_files)
        pex_file_by_alias = {filename.split("-", 1)[0]: filename for filename in pex_files}

        assert {"source", "deps"} == set(pex_file_by_alias)


def test_dagster_cloud_runnable(built_test_dagster_cloud_pex_image):
    cmd = [
        "docker",
        "run",
        "--platform=linux/amd64",
        "-t",
        "test-dagster-cloud-pex",
        "-c",
        "print('hello')",
    ]
    output = subprocess.run(cmd, encoding="utf-8", capture_output=True, check=True)

    assert "hello" in output.stdout
