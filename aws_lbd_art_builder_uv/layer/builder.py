# -*- coding: utf-8 -*-

"""
UV-based Lambda layer builder implementation.

This module provides Lambda layer creation using UV's ultra-fast dependency
management, supporting both local and containerized builds.

- :class:`UvLambdaLayerLocalBuilder`: Local uv-based builds
- :class:`UvLambdaLayerContainerBuilder`: Containerized uv-based builds
"""

import subprocess
import dataclasses
from pathlib import Path

from aws_lbd_art_builder_core.vendor.better_pathlib import temp_cwd
from aws_lbd_art_builder_core.layer.api import BaseLambdaLayerLocalBuilder
from aws_lbd_art_builder_core.layer.api import BaseLambdaLayerContainerBuilder
from aws_lbd_art_builder_core.layer.api import move_to_dir_python

from ..paths import path_enum


@dataclasses.dataclass(frozen=True)
class UvLambdaLayerLocalBuilder(BaseLambdaLayerLocalBuilder):
    """
    Build a Lambda layer using uv on the local machine.

    Uses ``uv sync --frozen`` with lock files for reproducible builds,
    environment variable authentication, development dependency exclusion,
    and copy-based linking for Lambda compatibility.

    .. seealso::

        :class:`~aws_lbd_art_builder_core.layer.builder.BaseLambdaLayerLocalBuilder`
    """

    path_bin_uv: Path = dataclasses.field(default=None)

    def step_1_1_print_info(self):
        super().step_1_1_print_info()
        self.log(f"path_bin_uv = {self.path_bin_uv}")

    def step_2_prepare_environment(self):
        super().step_2_prepare_environment()
        self.step_2_2_prepare_uv_stuff()

    def step_2_2_prepare_uv_stuff(self):
        """
        Copy UV project files (pyproject.toml and uv.lock) to build directory.
        """
        self.log("--- Step 2.2 - Prepare UV stuff")
        self.path_layout.copy_pyproject_toml(printer=self.log)
        self.path_layout.copy_file(
            p_src=self.path_layout.dir_project_root / "uv.lock",
            p_dst=self.path_layout.dir_repo / "uv.lock",
            printer=self.log,
        )

    def step_3_execute_build(self):
        super().step_3_execute_build()
        self.step_3_1_uv_login()
        self.step_3_2_run_uv_sync()

    def step_3_1_uv_login(self):
        """
        Configure UV authentication via environment variables.
        """
        self.log("--- Step 3.1 - Setting up UV credentials")
        if self.credentials is not None:
            key_user, key_pass = self.credentials.uv_login()
            self.log(f"Set environment variable {key_user}")
            self.log(f"Set environment variable {key_pass}")
        else:
            self.log("No UV credentials provided, skipping UV login step")

    def step_3_2_run_uv_sync(self):
        """
        Execute ``uv sync --frozen --no-dev --no-install-project --link-mode=copy``.
        """
        self.log("--- Step 3.2 - Run 'uv sync'")
        path_bin_uv = str(self.path_bin_uv) if self.path_bin_uv else "uv"
        dir_repo = self.path_layout.dir_repo
        with temp_cwd(dir_repo):
            args = [
                path_bin_uv,
                "sync",
                "--frozen",
                "--no-dev",
                "--no-install-project",
                "--link-mode=copy",
            ]
            subprocess.run(args, cwd=dir_repo, check=True)

    def step_4_finalize_artifacts(self):
        super().step_4_finalize_artifacts()
        self.log("--- Step 4.1 - Move site-packages to python/")
        move_to_dir_python(
            dir_site_packages=self.path_layout.dir_build_lambda_layer_repo_venv_site_packages,
            dir_python=self.path_layout.dir_python,
        )


@dataclasses.dataclass(frozen=True)
class UvLambdaLayerContainerBuilder(BaseLambdaLayerContainerBuilder):
    """
    Build a Lambda layer using uv inside a Docker container.

    Uses official AWS SAM Docker images to ensure Lambda runtime compatibility
    for packages with C extensions.

    :param lib_install_spec: The pip install specifier for ``aws_lbd_art_builder_uv``.
        Defaults to PyPI release. For development testing, use a git URL like::

            "aws_lbd_art_builder_uv @ git+https://github.com/MacHu-GWU/aws_lbd_art_builder_uv-project.git@main"

    .. seealso::

        :class:`~aws_lbd_art_builder_core.layer.builder.BaseLambdaLayerContainerBuilder`
    """

    path_script: Path = dataclasses.field(
        default=path_enum.path_build_in_container_script,
    )
    lib_install_spec: str = dataclasses.field(
        default="aws_lbd_art_builder_uv>=0.1.1,<1.0.0",
    )

    @property
    def docker_run_args(self) -> list[str]:
        args = super().docker_run_args
        args.extend([
            "--lib-install-spec",
            self.lib_install_spec,
        ])
        return args

    def step_1_preflight_check(self):
        super().step_1_preflight_check()
        path_uv_lock = self.path_layout.dir_project_root / "uv.lock"
        if path_uv_lock.exists() is False:
            raise FileNotFoundError(
                f"UV lock file not found: {path_uv_lock}, "
                f"cannot proceed with uv-based build. "
                f"Please run 'uv lock' to generate the lock file."
            )
