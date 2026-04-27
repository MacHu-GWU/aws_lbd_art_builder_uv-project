# -*- coding: utf-8 -*-

import subprocess
import dataclasses
from pathlib import Path
from functools import cached_property

from func_args.api import REQ

import aws_lbd_art_builder_core.api as aws_lbd_art_builder_core

from ..paths import path_enum


@dataclasses.dataclass(frozen=True)
class UvLambdaLayerContainerBuilder(aws_lbd_art_builder_core.layer_api.BaseLogger):
    """
    Build a Lambda layer using uv inside a Docker container.

    Uses official AWS SAM Docker images to ensure Lambda runtime compatibility
    for packages with C extensions.

    The container script (``_build_in_container.py``) is pure stdlib — no
    third-party packages are installed inside the container except ``uv``.

    **Mount scheme**: ``{project_root}/build/lambda/`` → ``/var/task/``
    (not the project root, to avoid host ``.venv`` conflicts).
    """

    # fmt: off
    path_pyproject_toml: Path = dataclasses.field(default=REQ)
    py_ver_major: int = dataclasses.field(default=REQ)
    py_ver_minor: int = dataclasses.field(default=REQ)
    is_arm: bool = dataclasses.field(default=REQ)
    path_script: Path = dataclasses.field(default=path_enum.path_build_in_container_script)
    credentials: aws_lbd_art_builder_core.layer_api.Credentials | None = dataclasses.field(default=None)
    skip_prompt: bool = dataclasses.field(default=False)
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

    @property
    def image_tag(self) -> str:
        """
        Docker image tag based on target architecture.

        :return: Architecture-specific tag for AWS SAM build images
        """
        if self.is_arm:
            return "latest-arm64"
        else:
            return "latest-x86_64"

    @property
    def image_uri(self) -> str:
        """
        Full Docker image URI for AWS SAM build container.

        :return: Complete Docker image URI from AWS public ECR
        """
        return (
            f"public.ecr.aws/sam"
            f"/build-python{self.py_ver_major}.{self.py_ver_minor}"
            f":{self.image_tag}"
        )

    @property
    def platform(self) -> str:
        """
        Docker platform specification for target architecture.

        :return: Platform string for docker run --platform argument
        """
        if self.is_arm:
            return "linux/arm64"
        else:
            return "linux/amd64"

    @property
    def container_name(self) -> str:
        """
        Unique container name for the build process.

        :return: Descriptive container name for docker run --name argument
        """
        suffix = "arm64" if self.is_arm else "amd64"
        return (
            f"lambda_layer_builder"
            f"-python{self.py_ver_major}{self.py_ver_minor}"
            f"-{suffix}"
        )

    @property
    def docker_run_args(self) -> list[str]:
        """
        Override to mount ``build/lambda/`` instead of project root.

        Layout inside container::

            /var/task/                            ← build/lambda/
            ├── _build_in_container.py
            ├── private-repository-credentials.json
            └── layer/
                ├── repo/{pyproject.toml, uv.lock}
                └── artifacts/python/
        """
        return [
            "docker",
            "run",
            "--rm",
            "--name",
            self.container_name,
            "--platform",
            self.platform,
            "--mount",
            f"type=bind,source={self.path_layout.dir_build_lambda_layer},target=/var/task",
            self.image_uri,
            "python",
            "-u",
            "/var/task/repo/_build_in_container.py",
        ]

    # --- step_1_preflight_check sub-steps
    def step_1_preflight_check(self):
        """
        Perform read-only validation of build environment and project configuration.
        """
        self.log_header("Step 1 - Preflight Check")
        self.step_1_1_print_info()
        self.step_1_2_check()

    def step_1_1_print_info(self):
        """
        Display build configuration and paths.
        """
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
        self.log_sub_header("Step 1.2 - Check")
        path_uv_lock = self.path_layout.dir_project_root / "uv.lock"
        self.log_detail(f"Check if '{path_uv_lock}' exists ...")
        if path_uv_lock.exists():
            self.log_detail(f"Exists!")
        else:
            raise FileNotFoundError(
                f"UV lock file not found: {path_uv_lock}, "
                f"cannot proceed with uv-based build. "
                f"Please run 'uv lock' to generate the lock file."
            )

    # --- step_2_prepare_environment sub-steps
    def step_2_prepare_environment(self):
        """
        Set up necessary prerequisites for the build process.
        """
        self.log_header("Step 2 - Prepare Environment")
        self.step_2_1_setup_build_dir()
        self.step_2_2_copy_build_script()
        self.step_2_3_setup_private_repository_credential()
        self.step_2_4_prepare_uv_stuff()

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

    def step_2_2_copy_build_script(self):
        """
        Copy the container build script to ``build/lambda/layer/repo/_build_in_container.py``.

        Overrides the core's default which copies to ``{project_root}/``.
        We copy into ``build/lambda/`` because that's what we mount to ``/var/task``.
        """
        self.log_sub_header("Step 2.2 - Copy Build Script")
        p_dst = self.path_layout.dir_repo / "_build_in_container.py"
        self.path_layout.copy_file(
            p_src=self.path_script,
            p_dst=p_dst,
            printer=self.log_detail,
        )

    def step_2_3_setup_private_repository_credential(self):
        """
        Configure private repository authentication (optional).
        """
        self.log_sub_header("Step 2.3 - Setup Private Repository Credential")
        if isinstance(self.credentials, aws_lbd_art_builder_core.layer_api.Credentials) is False:
            self.log_detail("No private repository credentials provided, skip.")
            return
        p = self.path_layout.path_private_repository_credentials_in_local
        self.log_detail(f"Dump private repository credentials to {p}")
        self.credentials.dump(path=p)

    def step_2_4_prepare_uv_stuff(self):
        """
        Copy UV project files (pyproject.toml and uv.lock) to build directory.
        """
        self.log_sub_header("Step 2.4 - Prepare UV stuff")
        self.path_layout.copy_pyproject_toml(printer=self.log_detail)
        self.path_layout.copy_file(
            p_src=self.path_layout.dir_project_root / "uv.lock",
            p_dst=self.path_layout.dir_repo / "uv.lock",
            printer=self.log_detail,
        )

    # --- step_3_execute_build sub-steps
    def step_3_execute_build(self):
        self.log_header("Step 3 - Execute Build")
        self.step_3_1_docker_run()

    def step_3_1_docker_run(self):
        """
        Execute the Docker container build process.
        """
        self.log_sub_header("Step 3.1 - Docker Run")
        # If the python script raises an exception,
        # docker run command will also fail with a non-zero exit code
        subprocess.run(self.docker_run_args, check=True)

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
