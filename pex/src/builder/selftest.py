# Simple environment test script

import os
from typing import List
from . import util

if __name__ == "__main__":
    print("hello from selftest.py")

    proc = util.run_pex_command(["--version"])
    print("Pex version:", proc.stdout.decode("utf-8"))

    proc = util.run_dagster_cloud_cli_command(["--version"])
    print(proc.stdout.decode("utf-8"))

    proc = util.run_dagster_command(["--version"])
    print(proc.stdout.decode("utf-8"))

    print("All OK.")
