# -*- coding: utf-8 -*-

"""
Container-based Lambda layer build script for uv dependency management.

This script runs inside a Docker container and uses **only Python standard library**
(3.11+). No third-party packages are needed — just ``uv`` (installed at runtime).

The host mounts ``{project_root}/build/lambda/`` to ``/var/task/``. The directory
layout inside the container looks like::

    /var/task/                                    ← mount point
    ├── _build_in_container.py                    ← this script
    ├── private-repository-credentials.json       ← optional credentials
    └── layer/
        ├── repo/
        │   ├── pyproject.toml                    ← copied by host step_2
        │   └── uv.lock                           ← copied by host step_2
        └── artifacts/
            └── python/                           ← output directory

**Usage**::

    # Default: no private repository
    python _build_in_container.py

    # With credentials (already dumped by host)
    python _build_in_container.py

**EXECUTION SAFETY**

THIS SCRIPT MUST BE EXECUTED IN THE CONTAINER, NOT ON THE HOST MACHINE.
"""

import os
import sys
import json
import shutil
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build Lambda layer using uv inside a Docker container.",
    )
    parser.add_argument(
        "--dir-task",
        default="/var/task",
        help="The mount point inside the container. Default: /var/task",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    dir_task = Path(args.dir_task)

    # --- Derived paths ---------------------------------------------------------
    dir_layer = dir_task / "layer"
    dir_repo = dir_layer / "repo"
    dir_python = dir_layer / "artifacts" / "python"
    path_credentials = dir_task / "private-repository-credentials.json"

    # --------------------------------------------------------------------------
    # 1. Verify container execution environment
    # --------------------------------------------------------------------------
    print("--- Verify the current runtime ...")
    print(f"dir_task = {dir_task}")
    print(f"dir_repo = {dir_repo}")
    if not dir_repo.exists():
        raise EnvironmentError(
            f"{dir_repo} does not exist. "
            f"This script expects the host to mount build/lambda/ to {dir_task}."
        )
    print("Runtime verification OK.")

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
    # 3. Setup private repository credentials (if any)
    # --------------------------------------------------------------------------
    print("--- Setup credentials ...")
    if path_credentials.exists():
        with open(path_credentials, "r") as f:
            cred = json.load(f)
        index_name = cred["index_name"]
        username = cred["username"]
        password = cred["password"]
        upper_name = index_name.upper().replace("-", "_")
        key_user = f"UV_INDEX_{upper_name}_USERNAME"
        key_pass = f"UV_INDEX_{upper_name}_PASSWORD"
        os.environ[key_user] = username
        os.environ[key_pass] = password
        print(f"Loaded credentials for private repository: {index_name}")
        print(f"Set environment variable {key_user}")
        print(f"Set environment variable {key_pass}")
    else:
        print("No private repository credentials found, using public PyPI only.")

    # --------------------------------------------------------------------------
    # 4. Run uv sync in the repo directory
    # --------------------------------------------------------------------------
    print("--- Run 'uv sync' ...")
    st = datetime.now()
    subprocess.run(
        [
            str(path_bin_uv),
            "sync",
            "--frozen",
            "--no-dev",
            "--no-install-project",
            "--link-mode=copy",
        ],
        cwd=str(dir_repo),
        check=True,
    )
    elapsed = (datetime.now() - st).total_seconds()
    print(f"uv sync elapsed: {elapsed:.2f} seconds")

    # --------------------------------------------------------------------------
    # 5. Move site-packages to artifacts/python/
    # --------------------------------------------------------------------------
    print("--- Move site-packages to artifacts/python/ ...")
    major, minor = sys.version_info[:2]
    dir_site_packages = (
        dir_repo / ".venv" / "lib" / f"python{major}.{minor}" / "site-packages"
    )
    if not dir_site_packages.exists():
        raise FileNotFoundError(
            f"site-packages directory not found: {dir_site_packages}"
        )
    print(f"dir_site_packages = {dir_site_packages}")
    print(f"dir_python = {dir_python}")
    # Ensure the target parent exists, then move
    dir_python.parent.mkdir(parents=True, exist_ok=True)
    if dir_python.exists():
        shutil.rmtree(dir_python)
    shutil.move(str(dir_site_packages), str(dir_python))

    print("Container-based layer build completed successfully!")


if __name__ == "__main__":
    main()
