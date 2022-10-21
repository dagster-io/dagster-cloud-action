import os
import shutil
import subprocess
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import List
from unittest import mock

import pytest
import requests


@contextmanager
def run_builder(builder_pex_path, builder_args: List[str]):
    with tempfile.TemporaryDirectory() as build_output_dir:
        proc = subprocess.run(
            [
                builder_pex_path,
                *builder_args,
                build_output_dir,
            ],
            capture_output=True,
        )
        if proc.returncode:
            raise ValueError(
                "Failed to run builder.pex:"
                + (proc.stdout + proc.stderr).decode("utf-8")
            )

        all_files = os.listdir(build_output_dir)
        pex_files = {filename for filename in all_files if filename.endswith(".pex")}
        yield (build_output_dir, list(pex_files), list(set(all_files) - pex_files))


def test_pex_deploy_build_only(repo_root, builder_pex_path):
    dagster_project1_yaml = (
        repo_root / "tests/test-repos/dagster_project1/dagster_cloud.yaml"
    )
    with run_builder(
        builder_pex_path, ["-m", "builder.deploy", str(dagster_project1_yaml)]
    ) as (build_output_dir, pex_files, other_files):
        # one source-HASH.pex and one deps-HASH.pex file are expected
        assert 2 == len(pex_files)
        pex_file_by_alias = {
            filename.split("-", 1)[0]: filename for filename in pex_files
        }

        assert {"source", "deps"} == set(pex_file_by_alias)

        # we are able to run a job defined in the built pex
        output = subprocess.check_output(
            [
                "./" + pex_file_by_alias["source"],
                *("-m dagster job execute -m dagster_project1  -j job_1".split()),
            ],
            env={**os.environ, "PEX_PATH": pex_file_by_alias["deps"]},
            cwd=build_output_dir,
            stderr=subprocess.STDOUT,
            encoding="utf-8",
        )

        assert "asset_1" in output
        assert "RUN_SUCCESS" in output


def test_pex_deps_build(repo_root, builder_pex_path):
    dagster_project1 = repo_root / "tests/test-repos/dagster_project1/"
    with tempfile.TemporaryDirectory() as tempdir:
        # copy the test repo so we can modify it
        tempdir_path = Path(tempdir)
        shutil.copytree(
            repo_root / "tests/test-repos/dagster_project1",
            tempdir_path / "dagster_project1",
        )

        import_pandas_code = tempdir_path / "imports_pandas.py"
        import_pandas_code.write_text('import pandas\nprint("OK")\n')

        # build with original deps
        with run_builder(
            builder_pex_path,
            ["-m", "builder.deps", str(tempdir_path / "dagster_project1")],
        ) as (build_output_dir, pex_files, other_files):
            # one deps-HASH.pex is expected
            assert 1 == len(pex_files)
            deps_file = pex_files[0]

            output = subprocess.check_output(
                ["./" + deps_file, "-m", "dagster", "--version"],
                cwd=build_output_dir,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
            )
            assert "version" in output

            # try to import nonexistent dependency
            with pytest.raises(subprocess.CalledProcessError) as exc:
                subprocess.check_output(
                    ["./" + deps_file, str(import_pandas_code)],
                    cwd=build_output_dir,
                    stderr=subprocess.STDOUT,
                    encoding="utf-8",
                )
            assert "No module named 'pandas'" in exc.value.output

        # rebuild with new deps
        (tempdir_path / "dagster_project1/requirements.txt").write_text("pandas\n")
        with run_builder(
            builder_pex_path,
            ["-m", "builder.deps", str(tempdir_path / "dagster_project1")],
        ) as (build_output_dir, pex_files, other_files):

            deps_file = pex_files[0]
            output = subprocess.check_output(
                ["./" + deps_file, str(import_pandas_code)],
                cwd=build_output_dir,
                stderr=subprocess.STDOUT,
                encoding="utf-8",
            )
            assert "OK" in output


def test_builder_deploy_with_upload(builder_module, repo_root):
    from builder import deploy

    s3_objects = {}

    def s3_urls_for_get(filenames):
        return [
            (filename if filename in s3_objects else None) for filename in filenames
        ]

    def s3_urls_for_put(filenames):
        return filenames

    def requests_get(url):
        response = requests.Response()
        if url in s3_objects:
            response._content = s3_objects[url]
            response.status_code = 200
        else:
            response.status_code = 404
        return response

    def requests_put(url, data):
        s3_objects[url] = data.read() if hasattr(data, "read") else data
        response = requests.Response()
        response.status_code = 200
        return response

    dagster_project1_yaml = (
        repo_root / "tests/test-repos/dagster_project1/dagster_cloud.yaml"
    )
    with mock.patch(
        "builder.pex_registry.get_s3_urls_for_get", s3_urls_for_get
    ) as _, mock.patch(
        "builder.pex_registry.get_s3_urls_for_put", s3_urls_for_put
    ) as _, mock.patch(
        "requests.get", requests_get
    ) as _, mock.patch(
        "requests.put", requests_put
    ) as _, tempfile.TemporaryDirectory() as build_output_dir:
        deploy.deploy_main(
            str(dagster_project1_yaml),
            build_output_dir,
            upload_pex=True,
            update_code_location=False,
            python_version="3.8",
        )
        # deps-HASH.pex, source-HASH.pex and requirements-HASH.txt
        assert len(s3_objects) == 3
        deps_pex_key = [key for key in s3_objects if key.startswith("deps-")][0]
        requirements_key = [
            key for key in s3_objects if key.startswith("requirements-")
        ][0]

        # if we rebuild, the deps.pex should not be rebuilt or published
        with mock.patch("builder.deps.build_deps_pex") as build_deps_pex_mock:
            s3_objects[deps_pex_key] = "current value"
            deploy.deploy_main(
                str(dagster_project1_yaml),
                build_output_dir,
                upload_pex=True,
                update_code_location=False,
                python_version="3.8",
            )
            build_deps_pex_mock.assert_not_called()
            assert s3_objects[deps_pex_key] == "current value"

        # if the requirements-HASH is missing and we rebuild, the deps should get rebuilt
        del s3_objects[requirements_key]
        deploy.deploy_main(
            str(dagster_project1_yaml),
            build_output_dir,
            upload_pex=True,
            update_code_location=False,
            python_version="3.8",
        )
        assert s3_objects[deps_pex_key] != "current value"
