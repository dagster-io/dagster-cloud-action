import os
import subprocess
import tempfile


def test_pex_deploy(repo_root, builder_pex_path):
    dagster_project1 = (
        repo_root / "tests/test-repos/dagster_project1/dagster_cloud.yaml"
    )
    with tempfile.TemporaryDirectory() as build_output_dir:
        proc = subprocess.run(
            [
                builder_pex_path,
                "-m",
                "builder.deploy",
                str(dagster_project1),
                build_output_dir,
            ],
            capture_output=True,
        )
        if proc.returncode:
            raise ValueError(
                "Failed to run builder.pex:"
                + (proc.stdout + proc.stderr).decode("utf-8")
            )

        # one source-HASH.pex and one deps-HASH.pex file are expected
        pex_files = {
            filename.split("-", 1)[0]: filename
            for filename in os.listdir(build_output_dir)
            if filename.endswith(".pex")
        }
        assert {"source", "deps"} == set(pex_files)

        # we are able to run a job defined in the built pex
        proc = subprocess.run(
            [
                "./" + pex_files["source"],
                *("-m dagster job execute -m dagster_project1  -j job_1".split()),
            ],
            env={**os.environ, "PEX_PATH": pex_files["deps"]},
            cwd=build_output_dir,
            capture_output=True,
        )
        output = (proc.stdout + proc.stderr).decode("utf-8")
        if proc.returncode:
            raise ValueError("Failed to launch a job run from the pex files:" + output)

        assert "asset_1" in output
        assert "RUN_SUCCESS" in output
