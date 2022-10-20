from setuptools import setup, find_packages

if __name__ == "__main__":
    setup(
        name="dagster_project1", packages=find_packages(), install_requires=["dagster"]
    )
