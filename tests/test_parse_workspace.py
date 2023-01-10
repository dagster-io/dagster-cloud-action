import yaml
import json
import os


def test_parse_workspace(repo_root, exec_context, tmp_path):
    dagster_cloud_file = tmp_path / "dagster_cloud.yaml"
    workspace = {
        "locations": [
            {
                "location_name": "foo",
                "code_source": {
                    "python_file": "repo.py",
                },
                "build": {
                    "directory": ".",
                    "registry": "some-registry",
                },
            }
        ]
    }
    dagster_cloud_file.write_text(yaml.dump(workspace))

    command = f"python {repo_root}/src/parse_workspace.py {dagster_cloud_file}"
    exec_context.run_local_command(command)

    # build_info
    expected = [
        {
            "name": "foo",
            "directory": ".",
            "build_folder": ".",
            "registry": "some-registry",
            "location_file": str(dagster_cloud_file),
        }
    ]
    assert f"build_info={json.dumps(expected)}" in exec_context.get_stdout()

    # secrets_set
    assert "secrets_set=false" in exec_context.get_stdout()

    exec_context.reset()
    exec_context.set_env({"DAGSTER_CLOUD_API_TOKEN": "true"})
    exec_context.run_local_command(command)
    assert "secrets_set=true" in exec_context.get_stdout()
