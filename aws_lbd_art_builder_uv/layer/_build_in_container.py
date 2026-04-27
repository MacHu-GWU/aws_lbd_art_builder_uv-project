# -*- coding: utf-8 -*-

"""
Container-based Lambda layer build script for uv dependency management.

This script runs inside a Docker container and uses **only Python standard library**
(3.11+). No third-party packages are needed — just ``uv`` (installed at runtime).

The host mounts ``{project_root}/build/lambda/layer/`` to ``/var/task/``.
Layout inside the container::

    /var/task/                                    ← mount point
    ├── build_lambda_layer_in_container.py        ← this script (renamed copy)
    ├── private-repository-credentials.json       ← optional credentials
    ├── repo/
    │   ├── pyproject.toml
    │   ├── uv.lock
    │   └── .venv/                                ← created by uv sync
    └── artifacts/
        └── python/

**Container-side steps**:

1. Verify ``/var/task/repo`` exists (proves we're inside the container).
2. Install ``uv`` globally via the official installer.
3. Load private repository credentials (optional).
4. Run ``uv sync --frozen --no-dev --no-install-project --link-mode=copy``.

The host-side step 4 moves ``repo/.venv/lib/pythonX.Y/site-packages/``
into ``artifacts/python/`` after the container exits.

**EXECUTION SAFETY**: This script must NOT be executed on the host machine.
"""

import os
import sys
import json
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
    dir_repo = dir_task / "repo"
    path_credentials = dir_task / "private-repository-credentials.json"

    # --------------------------------------------------------------------------
    # Step 1 — Verify container execution environment
    # --------------------------------------------------------------------------
    print("--- Step 1: Verify container environment ...")
    print(f"dir_task = {dir_task}")
    print(f"dir_repo = {dir_repo}")
    if not dir_repo.exists():
        raise EnvironmentError(
            f"{dir_repo} does not exist. "
            f"This script expects the host to mount build/lambda/layer/ to {dir_task}."
        )
    print("Verification OK.")

    # --------------------------------------------------------------------------
    # Step 2 — Install uv
    # --------------------------------------------------------------------------
    print("--- Step 2: Install uv ...")
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
    # Step 3 — Setup private repository credentials (optional)
    # --------------------------------------------------------------------------
    print("--- Step 3: Setup credentials ...")
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
    # Step 4 — Run uv sync
    # --------------------------------------------------------------------------
    print("--- Step 4: Run 'uv sync' ...")
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

    major, minor = sys.version_info[:2]
    dir_site_packages = (
        dir_repo / ".venv" / "lib" / f"python{major}.{minor}" / "site-packages"
    )
    print(f"Dependencies installed at: {dir_site_packages}")
    print("Container-side build completed successfully!")


if __name__ == "__main__":
    main()
