# -*- coding: utf-8 -*-

"""
Container-based Lambda layer build script for uv dependency management.

This is a CLI script that runs inside a Docker container to build Lambda layers.
It only uses Python standard library (3.11+) imports at the top level; third-party
imports happen after installation steps.

**Usage**::

    # Production (default): install from PyPI
    python _build_in_container.py

    # Development: install from GitHub
    python _build_in_container.py \\
        --lib-install-spec "aws_lbd_art_builder_uv @ git+https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project.git@main"

**Execution Flow**

1. Verify execution inside Docker container (``/var/task``)
2. Install ``uv`` CLI inside the container
3. Install ``aws_lbd_art_builder_uv`` library using ``uv pip install --system``
4. Use the ``UvLambdaLayerLocalBuilder`` class to execute the build logic.

**EXECUTION SAFETY**

THIS SCRIPT MUST BE EXECUTED IN THE CONTAINER, NOT ON THE HOST MACHINE.
"""

import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Lambda layer using uv inside a Docker container.",
    )
    parser.add_argument(
        "--lib-install-spec",
        default="aws_lbd_art_builder_uv>=0.1.1,<1.0.0",
        help=(
            "The pip install specifier for aws_lbd_art_builder_uv. "
            "Default: 'aws_lbd_art_builder_uv>=0.1.1,<1.0.0'. "
            "For dev testing, use a git URL like: "
            "'aws_lbd_art_builder_uv @ git+https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project.git@main'"
        ),
    )
    return parser.parse_args()


def main():
    args = parse_args()

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
    print("--- Install uv ...")
    st = datetime.now()
    subprocess.run(
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
        shell=True,
        check=True,
    )
    elapsed = (datetime.now() - st).total_seconds()
    print(f"install uv elapsed: {elapsed:.2f} seconds")

    path_bin_uv = Path("/root/.local/bin/uv")

    # --------------------------------------------------------------------------
    # 3. Install aws_lbd_art_builder_uv using uv pip install
    # --------------------------------------------------------------------------
    print(f"--- Install aws_lbd_art_builder_uv: {args.lib_install_spec}")
    st = datetime.now()
    subprocess.run(
        [
            str(path_bin_uv),
            "pip",
            "install",
            args.lib_install_spec,
            "--system",
            "--python",
            sys.executable,
        ],
        check=True,
    )
    elapsed = (datetime.now() - st).total_seconds()
    print(f"install aws_lbd_art_builder_uv elapsed: {elapsed:.2f} seconds")

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
