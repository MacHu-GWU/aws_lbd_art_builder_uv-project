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
from functools import cached_property

from func_args.api import REQ

import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core

from ..paths import path_enum


@dataclasses.dataclass(frozen=True)
class UvLambdaLayerLocalBuilder(aws_lbd_art_builder_core.layer_api.BaseLogger):
    """
    Build a Lambda layer using uv on the local machine.

    Uses ``uv sync --frozen`` with lock files for reproducible builds,
    environment variable authentication, development dependency exclusion,
    and copy-based linking for Lambda compatibility.

    **4-Step Build Workflow:**

    1. **Preflight Check** (:meth:`step_1_preflight_check`):
       Validate environment, tools, and project structure
    2. **Prepare Environment** (:meth:`step_2_prepare_environment`):
       Clean build directories and set up workspace
    3. **Execute Build** (:meth:`step_3_execute_build`):
       Run tool-specific dependency installation (override in subclass)
    4. **Finalize Artifacts** (:meth:`step_4_finalize_artifacts`):
       Transform output into Lambda-compatible structure (override in subclass)
    """

    # fmt: off
    path_pyproject_toml: Path = dataclasses.field(default=REQ)
    credentials: aws_lbd_art_builder_core.layer_api.Credentials | None = dataclasses.field(default=None)
    skip_prompt: bool = dataclasses.field(default=False)
    path_bin_uv: Path | None = dataclasses.field(default=None)
    # fmt: on

    @cached_property
    def path_layout(self) -> aws_lbd_art_builder_core.layer_api.LayerPathLayout:
        """
        :class:`~aws_lbd_art_builder_core.layer.foundation.LayerPathLayout`
        object for managing build paths.
        """
        return aws_lbd_art_builder_core.layer_api.LayerPathLayout(
            path_pyproject_toml=self.path_pyproject_toml,
        )

    def run(self):
        """
        Execute the complete local build workflow in sequence.

        Runs all four build phases in order. Override individual steps
        or call steps directly for custom workflows.
        """
        self.log_header("Start local Lambda layer build workflow")
        self.step_1_preflight_check()
        self.step_2_prepare_environment()
        self.step_3_execute_build()
        self.step_4_finalize_artifacts()

    # --- step_1_preflight_check sub-steps
    def step_1_preflight_check(self):
        """
        Perform read-only validation of build environment and project configuration.
        """
        self.log_header("Step 1 - Preflight Check")
        self.step_1_1_print_info()

    def step_1_1_print_info(self):
        """
        Display build configuration and paths.
        """
        # fmt: off
        self.log_sub_header("Step 1.1 - Print Build Info")
        self.log_detail(f"path_pyproject_toml = {self.path_pyproject_toml}")
        self.log_detail(f"dir_repo            = {self.path_layout.dir_repo}")
        self.log_detail(f"dir_build_layer     = {self.path_layout.dir_build_lambda_layer}")
        self.log_detail(f"path_bin_uv         = {self.path_bin_uv}")
        # fmt: on

    # --- step_2_prepare_environment sub-steps
    def step_2_prepare_environment(self):
        """
        Set up necessary prerequisites for the build process.
        """
        self.log_header("Step 2 - Prepare Environment")
        self.step_2_1_setup_build_dir()
        self.step_2_2_prepare_uv_stuff()

    def step_2_1_setup_build_dir(self):
        """
        Prepare the build environment by cleaning and creating directories.

        Ensures a clean slate for layer creation by removing previous artifacts
        and establishing the required directory structure.
        """
        self.log_sub_header("Step 2.1 - Setup Build Directory")
        dir = self.path_layout.dir_build_lambda_layer
        self.log_detail(f"Clean existing build directory: {dir}")
        self.path_layout.clean(skip_prompt=self.skip_prompt)
        self.path_layout.mkdirs()

    def step_2_2_prepare_uv_stuff(self):
        """
        Copy UV project files (pyproject.toml and uv.lock) to build directory.
        """
        self.log_sub_header("Step 2.2 - Prepare UV stuff")
        self.path_layout.copy_pyproject_toml(printer=self.log_detail)
        self.path_layout.copy_file(
            p_src=self.path_layout.dir_project_root / "uv.lock",
            p_dst=self.path_layout.dir_repo / "uv.lock",
            printer=self.log_detail,
        )

    # --- step_3_execute_build sub-steps
    def step_3_execute_build(self):
        self.log_header("Step 3 - Execute Build")
        self.step_3_1_uv_login()
        self.step_3_2_run_uv_sync()

    def step_3_1_uv_login(self):
        """
        Configure UV authentication via environment variables.
        """
        self.log_sub_header("Step 3.1 - Setting up UV credentials")
        if self.credentials is not None:
            key_user, key_pass = self.credentials.uv_login()
            self.log_detail(f"Set environment variable {key_user}")
            self.log_detail(f"Set environment variable {key_pass}")
        else:
            self.log_detail("No UV credentials provided, skipping UV login step")

    def step_3_2_run_uv_sync(self):
        """
        Execute ``uv sync --frozen --no-dev --no-install-project --link-mode=copy``.
        """
        self.log_sub_header("Step 3.2 - Run 'uv sync'")
        path_bin_uv = str(self.path_bin_uv) if self.path_bin_uv else "uv"
        dir_repo = self.path_layout.dir_repo
        with aws_lbd_art_builder_core.temp_cwd(dir_repo):
            args = [
                path_bin_uv,
                "sync",
                "--frozen",
                "--no-dev",
                "--no-install-project",
                "--link-mode=copy",
            ]
            cmd = " ".join(args)
            self.log_detail(f"Run: {cmd}")
            subprocess.run(args, cwd=dir_repo, check=True)

    # --- step_4_finalize_artifacts sub-steps
    def step_4_finalize_artifacts(self):
        self.log_header("Step 4 - Finalize Artifacts")
        self.step_4_1_move_site_packages_to_python()

    def step_4_1_move_site_packages_to_python(self):
        self.log_sub_header("Step 4.1 - Move site-packages to python/")
        dir_source = self.path_layout.dir_build_lambda_layer_repo_venv_site_packages
        dir_target = self.path_layout.dir_python
        self.log_detail(f"Move '{dir_source}' to '{dir_target}' ")
        aws_lbd_art_builder_core.layer_api.move_to_dir_python(
            dir_site_packages=dir_source,
            dir_python=dir_target,
        )
