from setuptools import find_packages, setup

if __name__ == "__main__":
    setup(
        name="dagster_project1",
        packages=find_packages(),
        install_requires=["dagster", "dagster-cloud"],
    )
