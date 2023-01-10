import os
from setuptools import setup


if __name__ == "__main__":
    PEX_BUILDER_SRC_DIR = os.getenv("PEX_BUILDER_SRC_DIR")
    if PEX_BUILDER_SRC_DIR:
        print(f"Using pex_builder from {PEX_BUILDER_SRC_DIR}")
        files = os.listdir(PEX_BUILDER_SRC_DIR)
        expected_files = {"deploy.py", "source.py", "deps.py"}
        if {"deploy.py", "source.py", "deps.py"} & set(files) != expected_files:
            raise SystemExit(
                f"Did not find expected files {expected_files} in {PEX_BUILDER_SRC_DIR}"
            )
    else:
        print(f"Using dagster-cloud-cli pex_builder from PyPI")
        PEX_BUILDER_SRC_DIR = "./builder"
    setup(
        name="dagster_pex_builder",
        packages=["builder"],
        package_dir={"builder": PEX_BUILDER_SRC_DIR},
    )
