import os
import subprocess
import tempfile
from contextlib import contextmanager
from typing import List


@contextmanager
def run_dagster_cloud_serverless_cmd(dagster_cloud_pex_path, args: List[str]):
    with tempfile.TemporaryDirectory() as build_output_dir:
        proc = subprocess.run(
            [
                dagster_cloud_pex_path,
                "-m",
                "dagster_cloud_cli.entrypoint",
                "serverless",
                *args,
                build_output_dir,
            ],
            capture_output=True,
            check=False,
        )
        if proc.returncode:
            raise ValueError(
                "Failed to run dagster-cloud.pex:" + (proc.stdout + proc.stderr).decode("utf-8")
            )

        all_files = os.listdir(build_output_dir)
        pex_files = {
            filename for filename in all_files if filename.endswith(".pex") and filename != ".pex"
        }
        yield (build_output_dir, list(pex_files), list(set(all_files) - pex_files))


def test_pex_build_only(repo_root, dagster_cloud_pex_path):
    dagster_project1 = repo_root / "tests/test-repos/dagster_project1"
    with run_dagster_cloud_serverless_cmd(
        dagster_cloud_pex_path,
        [
            "build-python-executable",
            str(dagster_project1),
            "--api-token=fake",
            "--url=fake",
            "--python-version=3.11",
        ],
    ) as (
        build_output_dir,
        pex_files,
        other_files,
    ):
        # one source-HASH.pex and one deps-HASH.pex file are expected
        assert 2 == len(pex_files)
        pex_file_by_alias = {filename.split("-", 1)[0]: filename for filename in pex_files}

        assert {"source", "deps"} == set(pex_file_by_alias)


def test_dagster_cloud_runnable(dagster_cloud_pex_path):
    output = subprocess.check_output(
        [dagster_cloud_pex_path, "-c", "print('hello')"], encoding="utf-8"
    )
    assert "hello" in output
