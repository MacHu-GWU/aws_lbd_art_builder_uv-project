# -*- coding: utf-8 -*-

"""
UV-based containerized Lambda layer builder.

:class:`UvLambdaLayerContainerBuilder` orchestrates a Docker-based build
that runs ``uv sync`` inside an official AWS SAM image.

See ``docs/source/99-Maintainer-Guide/03-Build-Lambda-Layer-using-UV-in-Container``
for the full architecture guide.
"""

import subprocess
import dataclasses
from pathlib import Path

import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core

from ..paths import path_enum


@dataclasses.dataclass(frozen=True)
class UvLambdaLayerContainerBuilder(
    aws_lbd_art_builder_core.layer_api.BaseLambdaLayerContainerBuilder,
):  # pragma: no cover
    """
    Build a Lambda layer using uv inside a Docker container.

    **Mount scheme**: ``{project_root}/build/lambda/layer/`` → ``/var/task/``

    The container script (``_build_in_container.py``) is pure stdlib — no
    third-party packages are installed inside the container except ``uv``.
    """

    # fmt: off
    path_script: Path = dataclasses.field(default=path_enum.path_build_in_container_script)
    # credentials is optional because most projects only need public PyPI.
    # When private repositories are needed, the caller passes a Credentials
    # object that gets serialized to JSON and read inside the container.
    credentials: aws_lbd_art_builder_core.layer_api.Credentials | None = dataclasses.field(default=None)
    skip_prompt: bool = dataclasses.field(default=False)
    # fmt: on

    def run(self):
        self.step_1_preflight_check()
        self.step_2_prepare_environment()
        self.step_3_execute_build()
        self.step_4_finalize_artifacts()

    # --- Step 1 ---------------------------------------------------------------
    def step_1_preflight_check(self):
        self.log_header("Step 1 - Preflight Check")
        self.step_1_1_print_info()
        self.step_1_2_check()

    def step_1_1_print_info(self):
        # fmt: off
        self.log_sub_header("Step 1.1 - Print Build Info")
        self.log_detail(f"path_pyproject_toml = {self.path_pyproject_toml}")
        self.log_detail(f"py_ver_major        = {self.py_ver_major}")
        self.log_detail(f"py_ver_minor        = {self.py_ver_minor}")
        self.log_detail(f"is_arm              = {self.is_arm}")
        self.log_detail(f"path_script         = {self.path_script}")
        self.log_detail(f"dir_repo            = {self.path_layout.dir_repo}")
        self.log_detail(f"dir_build_layer     = {self.path_layout.dir_build_lambda_layer}")
        # fmt: on

    def step_1_2_check(self):
        """
        Check that ``uv.lock`` exists before starting the build.

        Container builds are slow and resource-heavy (pulling Docker images,
        spinning up a container).  Failing early on a missing lock file
        saves minutes of wasted time.  The local builder skips this check
        because local builds are fast enough that discovering the missing
        lock file at ``uv sync`` time is acceptable.
        """
        self.log_sub_header("Step 1.2 - Check")
        path_uv_lock = self.path_layout.dir_project_root / "uv.lock"
        self.log_detail(f"Check if '{path_uv_lock}' exists ...")
        if path_uv_lock.exists():
            self.log_detail("Exists!")
        else:
            raise FileNotFoundError(
                f"UV lock file not found: {path_uv_lock}, "
                f"cannot proceed with uv-based build. "
                f"Please run 'uv lock' to generate the lock file."
            )

    # --- Step 2 ---------------------------------------------------------------
    def step_2_prepare_environment(self):
        self.log_header("Step 2 - Prepare Environment")
        self.step_2_1_setup_build_dir()
        self.step_2_2_copy_build_script()
        self.step_2_3_setup_private_repository_credential()
        self.step_2_4_prepare_uv_stuff()

    def step_2_1_setup_build_dir(self):
        """
        Delete ``build/lambda/layer/`` and recreate the directory structure.
        """
        self.log_sub_header("Step 2.1 - Setup Build Directory")
        dir = self.path_layout.dir_build_lambda_layer
        self.log_detail(f"Clean existing build directory: {dir}")
        self.path_layout.clean(skip_prompt=self.skip_prompt)
        self.path_layout.mkdirs()

    def step_2_2_copy_build_script(self):
        """
        Copy ``_build_in_container.py`` →
        ``build/lambda/layer/build_lambda_layer_in_container.py``.
        """
        self.log_sub_header("Step 2.2 - Copy Build Script")
        p_dst = self.path_layout.path_build_lambda_layer_in_container_script_in_local
        self.path_layout.copy_file(
            p_src=self.path_script,
            p_dst=p_dst,
            printer=self.log_detail,
        )

    def step_2_3_setup_private_repository_credential(self):
        """
        Dump credentials JSON to ``build/lambda/layer/private-repository-credentials.json``
        for the container script to read.
        """
        self.log_sub_header("Step 2.3 - Setup Private Repository Credential")
        if not isinstance(
            self.credentials, aws_lbd_art_builder_core.layer_api.Credentials
        ):
            self.log_detail("No private repository credentials provided, skip.")
            return
        p = (
            self.path_layout.dir_build_lambda_layer
            / "private-repository-credentials.json"
        )
        self.log_detail(f"Dump private repository credentials to {p}")
        self.credentials.dump(path=p)

    def step_2_4_prepare_uv_stuff(self):
        """
        Copy ``pyproject.toml`` and ``uv.lock`` to ``build/lambda/layer/repo/``.
        """
        self.log_sub_header("Step 2.4 - Prepare UV stuff")
        self.path_layout.copy_pyproject_toml(printer=self.log_detail)
        self.path_layout.copy_file(
            p_src=self.path_layout.dir_project_root / "uv.lock",
            p_dst=self.path_layout.dir_repo / "uv.lock",
            printer=self.log_detail,
        )

    # --- Step 3 ---------------------------------------------------------------
    def step_3_execute_build(self):
        self.log_header("Step 3 - Execute Build")
        self.step_3_1_docker_run()

    def step_3_1_docker_run(self):
        self.log_sub_header("Step 3.1 - Docker Run")
        subprocess.run(self.docker_run_args, check=True)

    # --- Step 4 ---------------------------------------------------------------
    def step_4_finalize_artifacts(self):
        """
        Move ``repo/.venv/lib/pythonX.Y/site-packages/`` →
        ``artifacts/python/`` on the host.
        """
        self.log_header("Step 4 - Finalize Artifacts")
        self.step_4_1_move_site_packages_to_python()

    def step_4_1_move_site_packages_to_python(self):
        self.log_sub_header("Step 4.1 - Move site-packages to python/")
        dir_source = self.path_layout.dir_build_lambda_layer_repo_venv_site_packages
        dir_target = self.path_layout.dir_python
        self.log_detail(f"Move '{dir_source}' to '{dir_target}'")
        aws_lbd_art_builder_core.layer_api.move_to_dir_python(
            dir_site_packages=dir_source,
            dir_python=dir_target,
        )
