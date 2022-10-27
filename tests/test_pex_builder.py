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


@mock.patch("builder.deps.build_deps_from_requirements")
@mock.patch("builder.source.build_source_pex")
def test_builder_deploy_with_upload(
    build_source_pex_mock,
    build_deps_from_requirements_mock,
    builder_module,
    repo_root,
    pex_registry_fixture,
):
    from builder import deploy

    dagster_project1_yaml = (
        repo_root / "tests/test-repos/dagster_project1/dagster_cloud.yaml"
    )

    def build_deps_from_requirements(requirements, output_directory):
        filepath = os.path.join(output_directory, deps_pex_content + ".pex")
        with open(filepath, "w") as pex_file:
            pex_file.write(deps_pex_content)
        return filepath

    build_deps_from_requirements_mock.side_effect = build_deps_from_requirements

    def build_source_pex(code_directory, output_directory, python_version):
        filepath = os.path.join(output_directory, source_pex_content + ".pex")
        with open(filepath, "w") as pex_file:
            pex_file.write(source_pex_content)
        return filepath

    build_source_pex_mock.side_effect = build_source_pex

    with tempfile.TemporaryDirectory() as temp_dir:
        # 1st deploy
        deps_pex_content = "deps-pex-a"
        source_pex_content = "source-pex-a"
        location_builds = deploy.deploy_main(
            str(dagster_project1_yaml),
            temp_dir,
            upload_pex=True,
            deps_cache_tag=None,
            update_code_location=False,
            python_version="3.8",
        )
        # deps-HASH.pex, source-HASH.pex and requirements-HASH.txt
        assert len(pex_registry_fixture) == 3
        assert pex_registry_fixture["deps-pex-a.pex"] == b"deps-pex-a"
        assert len(location_builds) == 1
        assert location_builds[0].pex_tag == "files=deps-pex-a.pex:source-pex-a.pex"

        # 2nd deploy - deps.pex is rebuilt since we dont have a cache tag
        deps_pex_content = "deps-pex-b"
        build_deps_from_requirements_mock.reset()
        deploy.deploy_main(
            str(dagster_project1_yaml),
            temp_dir,
            upload_pex=True,
            deps_cache_tag=None,
            update_code_location=False,
            python_version="3.8",
        )
        build_deps_from_requirements_mock.assert_called()
        assert pex_registry_fixture["deps-pex-b.pex"] == b"deps-pex-b"

        # 3rd deploy with cache tag - deps.pex is rebuilt for new cache tag
        deps_pex_content = "deps-pex-c"
        build_deps_from_requirements_mock.reset()
        deploy.deploy_main(
            str(dagster_project1_yaml),
            temp_dir,
            upload_pex=True,
            deps_cache_tag="tag1",
            update_code_location=False,
            python_version="3.8",
        )
        assert pex_registry_fixture["deps-pex-c.pex"] == b"deps-pex-c"

        # 4th deploy with same cache tag - deps.pex is not rebuilt but reused
        deps_pex_content = "deps-pex-d"
        location_builds = deploy.deploy_main(
            str(dagster_project1_yaml),
            temp_dir,
            upload_pex=True,
            deps_cache_tag="tag1",
            update_code_location=False,
            python_version="3.8",
        )
        assert "deps-pex-d.pex" not in pex_registry_fixture
        assert location_builds[0].pex_tag == "files=deps-pex-c.pex:source-pex-a.pex"
