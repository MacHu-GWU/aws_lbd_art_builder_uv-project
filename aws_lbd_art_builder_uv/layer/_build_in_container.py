# -*- coding: utf-8 -*-

"""
Container-based Lambda layer build script for uv dependency management.

**Execution Flow**

1. Verify execution inside Docker container (``/var/task``)
2. Install ``uv`` CLI inside the container
3. Install ``aws_lbd_art_builder_uv`` library inside the container
4. Use the ``UvLambdaLayerLocalBuilder`` class to execute the build logic.

**EXECUTION SAFETY**

THIS SCRIPT MUST BE EXECUTED IN THE CONTAINER, NOT ON THE HOST MACHINE.

The script validates its execution environment by checking that it's running from
``/var/task``, which is where the Docker container mounts the host project directory.
"""

import sys
import subprocess
from pathlib import Path
from datetime import datetime


def main():
    # --------------------------------------------------------------------------
    # 1. Verify container execution environment
    # --------------------------------------------------------------------------
    print("--- Verify the current runtime ...")
    dir_here = Path(__file__).absolute().parent
    print(f"Current directory is {dir_here}")
    if str(dir_here) != "/var/task":
        raise EnvironmentError(
            "This script has to be executed in the container, not in the host machine"
        )
    else:
        print("Current directory is /var/task, we are in the container OK.")

    # --------------------------------------------------------------------------
    # 2. Install uv within the container
    # --------------------------------------------------------------------------
    print("--- install uv ...")
    args = "curl -LsSf https://astral.sh/uv/install.sh | sh"
    st = datetime.now()
    subprocess.run(args, shell=True, check=True)
    elapsed = (datetime.now() - st).total_seconds()
    print(f"install uv elapsed: {elapsed:.2f} seconds")

    # --------------------------------------------------------------------------
    # 3. Install aws_lbd_art_builder_uv within the container
    # --------------------------------------------------------------------------
    dir_bin = Path(sys.executable).parent
    path_bin_pip = dir_bin / "pip"
    path_bin_uv = Path("/root/.local/bin/uv")

    print("--- Pip install aws_lbd_art_builder_uv ...")
    st = datetime.now()
    args = [f"{path_bin_pip}", "install", "aws_lbd_art_builder_uv>=0.1.1,<1.0.0"]
    subprocess.run(args, check=True)
    elapsed = (datetime.now() - st).total_seconds()
    print(f"pip install aws_lbd_art_builder_uv elapsed: {elapsed:.2f} seconds")

    # --------------------------------------------------------------------------
    # 4. Use the local builder logic inside the container
    # --------------------------------------------------------------------------
    from aws_lbd_art_builder_uv.layer.api import (
        Credentials,
        UvLambdaLayerLocalBuilder,
    )

    path_credentials = (
        dir_here / "build" / "lambda" / "private-repository-credentials.json"
    )

    if path_credentials.exists():
        credentials = Credentials.load(path=path_credentials)
        print(f"Loaded credentials for private repository: {credentials.index_name}")
    else:
        credentials = None
        print("No private repository credentials found, using public PyPI only")

    print("--- Starting uv-based layer build inside container ...")
    builder = UvLambdaLayerLocalBuilder(
        path_bin_uv=path_bin_uv,
        path_pyproject_toml=dir_here / "pyproject.toml",
        credentials=credentials,
        skip_prompt=True,
    )
    builder.run()
    print("Container-based layer build completed successfully!")


if __name__ == "__main__":
    main()
