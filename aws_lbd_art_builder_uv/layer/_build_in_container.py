# -*- coding: utf-8 -*-

"""
Container-side Lambda layer build script (pure stdlib, Python 3.11+).

This script runs **inside** the Docker container launched by
:class:`~aws_lbd_art_builder_uv.layer.container_builder.UvLambdaLayerContainerBuilder`.
No third-party packages are needed — only ``uv`` (installed at runtime).

**Why pure stdlib?** This script is copied into a bare AWS SAM Docker image
that has nothing pre-installed except Python itself.  If we imported any
third-party library here, we would have to install it inside the container
first, adding complexity and build time.  Keeping this script stdlib-only
means the only external tool we need to fetch is ``uv``.

The host mounts ``{project_root}/build/lambda/layer/`` → ``/var/task/``.
Layout inside the container::

    /var/task/                                    ← mount point
    ├── build_lambda_layer_in_container.py        ← this script (renamed copy)
    ├── private-repository-credentials.json       ← optional credentials
    └── repo/
        ├── pyproject.toml
        ├── uv.lock
        └── .venv/                                ← created by uv sync

The host-side step 4 moves ``repo/.venv/lib/pythonX.Y/site-packages/``
into ``artifacts/python/`` after the container exits.

See ``docs/source/99-Maintainer-Guide/03-Build-Lambda-Layer-using-UV-in-Container``
for the full architecture guide.
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime


# --- Logging helpers (match the host-side BaseLogger format) ------------------
def _log_sub_header(title: str):  # pragma: no cover
    print("")
    print("+----- " + title)
    print("|")


def _log(msg: str):  # pragma: no cover
    print("|  " + msg)


def parse_args():  # pragma: no cover
    parser = argparse.ArgumentParser(
        description="Build Lambda layer using uv inside a Docker container.",
    )
    parser.add_argument(
        "--dir-task",
        default="/var/task",
        help="The mount point inside the container. Default: /var/task",
    )
    return parser.parse_args()


def main():  # pragma: no cover
    args = parse_args()
    dir_task = Path(args.dir_task)

    # --- Derived paths ---------------------------------------------------------
    dir_repo = dir_task / "repo"
    path_credentials = dir_task / "private-repository-credentials.json"

    # --------------------------------------------------------------------------
    # Step 1 — Verify container execution environment
    # --------------------------------------------------------------------------
    _log_sub_header("Container Step 1 - Verify Environment")
    _log(f"dir_task = {dir_task}")
    _log(f"dir_repo = {dir_repo}")
    if not dir_repo.exists():
        raise EnvironmentError(
            f"{dir_repo} does not exist. "
            f"This script expects the host to mount build/lambda/layer/ to {dir_task}."
        )
    _log("Verification OK.")

    # --------------------------------------------------------------------------
    # Step 2 — Install uv
    #
    # Why install uv at runtime via curl instead of pre-baking it into the
    # Docker image?  Because we use the official AWS SAM base image directly
    # (e.g. public.ecr.aws/sam/build-python3.12) to guarantee binary
    # compatibility with the real Lambda runtime.  Building a custom image
    # that bundles uv would add a maintenance burden (rebuild on every SAM
    # image update) and defeat the purpose of using the official image.
    # The curl install takes only a few seconds and always gets the latest uv.
    # --------------------------------------------------------------------------
    _log_sub_header("Container Step 2 - Install uv")
    st = datetime.now()
    subprocess.run(
        "curl -LsSf https://astral.sh/uv/install.sh | sh",
        shell=True,
        check=True,
    )
    elapsed = (datetime.now() - st).total_seconds()
    _log(f"install uv elapsed: {elapsed:.2f} seconds")

    path_bin_uv = Path("/root/.local/bin/uv")

    # --------------------------------------------------------------------------
    # Step 3 — Setup private repository credentials (optional)
    #
    # Credentials are set up inside the container (not passed via docker env
    # vars) because sensitive tokens should not appear in ``docker run``
    # command lines, which are visible in process listings.  Instead, the
    # host dumps a JSON file into the bind-mounted directory, and this
    # script reads it.
    # --------------------------------------------------------------------------
    _log_sub_header("Container Step 3 - Setup Credentials")
    if path_credentials.exists():
        with open(path_credentials, "r") as f:
            cred = json.load(f)
        index_name = cred["index_name"]
        username = cred["username"]
        password = cred["password"]
        # uv expects env vars in the form UV_INDEX_{NAME}_USERNAME where
        # {NAME} is the index name uppercased with hyphens replaced by
        # underscores.  This is the uv convention for per-index auth.
        # See: https://docs.astral.sh/uv/configuration/indexes/
        upper_name = index_name.upper().replace("-", "_")
        key_user = f"UV_INDEX_{upper_name}_USERNAME"
        key_pass = f"UV_INDEX_{upper_name}_PASSWORD"
        os.environ[key_user] = username
        os.environ[key_pass] = password
        _log(f"Loaded credentials for private repository: {index_name}")
        _log(f"Set environment variable {key_user}")
        _log(f"Set environment variable {key_pass}")
    else:
        _log("No private repository credentials found, using public PyPI only.")

    # --------------------------------------------------------------------------
    # Step 4 — Run uv sync
    # --------------------------------------------------------------------------
    _log_sub_header("Container Step 4 - Run 'uv sync'")
    st = datetime.now()
    # Flag rationale:
    #   --frozen        : use the exact versions from uv.lock without
    #                     re-resolving, ensuring reproducible builds.
    #   --no-dev        : exclude dev dependencies (pytest, sphinx, etc.)
    #                     that have no place in a Lambda layer.
    #   --no-install-project : skip installing the project package itself;
    #                     the Lambda layer only needs the *dependencies*.
    #                     The project code is deployed separately as the
    #                     Lambda function handler.
    #   --link-mode=copy : copy files instead of symlinking. Lambda layers
    #                     are zipped and uploaded — symlinks would break
    #                     because the link targets don't exist in the
    #                     Lambda execution environment.
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
    _log(f"uv sync elapsed: {elapsed:.2f} seconds")

    major, minor = sys.version_info[:2]
    dir_site_packages = (
        dir_repo / ".venv" / "lib" / f"python{major}.{minor}" / "site-packages"
    )
    _log(f"Dependencies installed at: {dir_site_packages}")
    _log("Container-side build completed successfully!")


if __name__ == "__main__":  # pragma: no cover
    main()
