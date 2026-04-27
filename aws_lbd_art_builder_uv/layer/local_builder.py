# -*- coding: utf-8 -*-

"""
UV-based local Lambda layer builder.

:class:`UvLambdaLayerLocalBuilder` runs ``uv sync`` directly on the host
machine to install dependencies into a Lambda-compatible layer structure.

See ``docs/source/99-Maintainer-Guide/03-Build-Lambda-Layer-using-UV-in-Container``
for the containerized variant's architecture guide.
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

    Runs ``uv sync --frozen --no-dev --no-install-project --link-mode=copy``
    on the host, then moves ``site-packages/`` into ``artifacts/python/``.

    The local builder does not require ``py_ver_major`` / ``py_ver_minor``
    because it always uses the host's current Python — there is no way to
    target a different Python version without a container.  The container
    builder requires them to select the correct AWS SAM base image.

    .. note::

       Local builds produce host-native binaries.  For packages with C
       extensions, use :class:`UvLambdaLayerContainerBuilder` instead.
    """

    # fmt: off
    path_pyproject_toml: Path = dataclasses.field(default=REQ)
    credentials: aws_lbd_art_builder_core.layer_api.Credentials | None = dataclasses.field(default=None)
    skip_prompt: bool = dataclasses.field(default=False)
    # path_bin_uv defaults to None, which means "use whatever 'uv' is on
    # PATH".  This covers the common case where uv is globally installed.
    # An explicit path is only needed when uv lives in a non-standard
    # location (e.g. a CI environment with a custom tool cache).
    path_bin_uv: Path | None = dataclasses.field(default=None)
    # fmt: on

    @cached_property
    def path_layout(self) -> aws_lbd_art_builder_core.layer_api.LayerPathLayout:
        return aws_lbd_art_builder_core.layer_api.LayerPathLayout(
            path_pyproject_toml=self.path_pyproject_toml,
        )

    def run(self):
        self.log_header("Start local Lambda layer build workflow")
        self.step_1_preflight_check()
        self.step_2_prepare_environment()
        self.step_3_execute_build()
        self.step_4_finalize_artifacts()

    # --- Step 1 ---------------------------------------------------------------
    def step_1_preflight_check(self):
        self.log_header("Step 1 - Preflight Check")
        self.step_1_1_print_info()

    def step_1_1_print_info(self):
        # fmt: off
        self.log_sub_header("Step 1.1 - Print Build Info")
        self.log_detail(f"path_pyproject_toml = {self.path_pyproject_toml}")
        self.log_detail(f"dir_repo            = {self.path_layout.dir_repo}")
        self.log_detail(f"dir_build_layer     = {self.path_layout.dir_build_lambda_layer}")
        self.log_detail(f"path_bin_uv         = {self.path_bin_uv}")
        # fmt: on

    # --- Step 2 ---------------------------------------------------------------
    def step_2_prepare_environment(self):
        self.log_header("Step 2 - Prepare Environment")
        self.step_2_1_setup_build_dir()
        self.step_2_2_prepare_uv_stuff()

    def step_2_1_setup_build_dir(self):
        """
        Delete ``build/lambda/layer/`` and recreate the directory structure.
        """
        self.log_sub_header("Step 2.1 - Setup Build Directory")
        dir = self.path_layout.dir_build_lambda_layer
        self.log_detail(f"Clean existing build directory: {dir}")
        self.path_layout.clean(skip_prompt=self.skip_prompt)
        self.path_layout.mkdirs()

    def step_2_2_prepare_uv_stuff(self):
        """
        Copy ``pyproject.toml`` and ``uv.lock`` to ``build/lambda/layer/repo/``.
        """
        self.log_sub_header("Step 2.2 - Prepare UV stuff")
        self.path_layout.copy_pyproject_toml(printer=self.log_detail)
        self.path_layout.copy_file(
            p_src=self.path_layout.dir_project_root / "uv.lock",
            p_dst=self.path_layout.dir_repo / "uv.lock",
            printer=self.log_detail,
        )

    # --- Step 3 ---------------------------------------------------------------
    def step_3_execute_build(self):
        """
        Credentials are set up here in Step 3 (right before ``uv sync``)
        rather than in Step 2, because ``uv_login()`` sets process-level
        environment variables.  Doing it in Step 2 would pollute the env
        during directory setup, and if Step 2 failed, the env vars would
        be left dangling.  Keeping credential setup adjacent to the command
        that needs them minimizes the window of exposure.

        (In the container builder, credentials are written to a JSON file
        in Step 2 because the container is a separate process — writing a
        file is a prepare action, not an execute action.)
        """
        self.log_header("Step 3 - Execute Build")
        self.step_3_1_uv_login()
        self.step_3_2_run_uv_sync()

    def step_3_1_uv_login(self):
        """
        Set ``UV_INDEX_{NAME}_USERNAME/PASSWORD`` env vars for private repos.
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

    # --- Step 4 ---------------------------------------------------------------
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
