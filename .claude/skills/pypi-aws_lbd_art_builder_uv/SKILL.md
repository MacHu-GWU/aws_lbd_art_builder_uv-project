---
name: pypi-aws_lbd_art_builder_uv
description: Python library aws_lbd_art_builder_uv, the uv builder of the aws_lbd_art_builder family. Build an AWS Lambda layer from a project's pyproject.toml and uv.lock by running uv sync on the host or inside an AWS SAM Docker image (for C extensions), choose extras and dependency groups, validate the result, then zip, upload and publish it with the re-exported aws_lbd_art_builder_core helpers. Public symbols include layer_api, UvLambdaLayerLocalBuilder, UvLambdaLayerContainerBuilder, UvSyncOptions, validate_artifacts, STRUCTURAL_ARGS, Credentials, LayerPathLayout, create_layer_zip_file, upload_layer_zip_to_s3, LambdaLayerVersionPublisher, LayerDeployment. Generated for aws_lbd_art_builder_uv version 1.0.0. Higher 1.x versions should generally be compatible, lower versions may still work but correctness is not guaranteed.
---

# aws_lbd_art_builder_uv

Builds the dependency folder of a Lambda layer with uv. A builder copies `pyproject.toml` and `uv.lock` to `{root}/build/lambda/layer/repo/`, runs `uv sync --no-install-project --link-mode=copy` plus the flags from `UvSyncOptions`, and moves the venv's `site-packages/` to `{root}/build/lambda/layer/artifacts/python/`. The project itself is never installed; the layer holds dependencies only. Zip, upload and publish come from `aws_lbd_art_builder_core` 1.x, re-exported here. AWS calls need the extras `upload` / `publish` (boto3, s3pathlib 3.x); pass plain boto3 clients, not a `BotoSesManager`.

## Import

```python
from aws_lbd_art_builder_uv.api import layer_api
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv     # then aws_lbd_art_builder_uv.layer_api.X
```

Every symbol is reached through `layer_api`.

## Public API

Classes are frozen dataclasses: pass fields by keyword; `*` marks a required field. Builders also take `verbose: bool = True` and `printer = print`.

### Builders (both expose `.path_layout: LayerPathLayout` and `.run()`)

- `UvLambdaLayerLocalBuilder(path_pyproject_toml*, credentials: Credentials | None = None, skip_prompt=False, path_bin_uv: Path | None = None, uv_sync_options: UvSyncOptions = UvSyncOptions())`: runs uv on the host with the host's Python. `path_bin_uv=None` means `uv` on `PATH`. Produces host-native binaries: fine for pure-Python dependencies, wrong for C extensions built on macOS.
  - `.run()` = `.step_1_preflight_check()`, `.step_2_prepare_environment()`, `.step_3_execute_build()`, `.step_4_finalize_artifacts()`.
- `UvLambdaLayerContainerBuilder(path_pyproject_toml*, py_ver_major: int*, py_ver_minor: int*, is_arm: bool*, credentials=None, skip_prompt=False, uv_sync_options=UvSyncOptions())`: runs uv inside `public.ecr.aws/sam/build-python{X.Y}:latest-{x86_64|arm64}`. Needs Docker. Raises `FileNotFoundError` early if `uv.lock` is missing.
  - Same four `step_*` methods and `.run()`; also `.image_uri`, `.platform`, `.container_name`, `.script_args`, `.docker_run_args`.
- `skip_prompt=False` asks on stdin before wiping `build/lambda/layer/`; pass `True` in scripts and CI.
- **Gotcha:** step 4 locates `site-packages` from `{root}/.venv/bin/python --version` (the project's own venv, not the build venv). The project needs a `.venv` whose `X.Y` matches the build Python (`py_ver_*` for containers), else `FileNotFoundError`. Create one with `uv venv --python 3.12`.

### Choosing what goes into the layer

- `UvSyncOptions(extras: list[str] = [], all_extras=False, no_extras: list[str] = [], groups: list[str] = [], no_groups: list[str] = [], all_groups=False, no_default_groups=False, no_dev=True, frozen=True, extra_args: list[str] = [])`: `uv sync` flags. Default renders `["--frozen", "--no-dev"]`, i.e. `[project] dependencies` only.
  - `.to_args() -> list[str]`: the rendered flags, without `STRUCTURAL_ARGS`.
  - Raises `ValueError` at construction for `extras` + `all_extras`, `no_extras` without `all_extras`, or an `extra_args` entry that is structural (`--no-install-project`, `--link-mode`) or already a field (`--extra`, `--frozen`, ...).
  - `UvSyncOptions.managed_args: dict[str, str]`: flag → owning field name.
- `STRUCTURAL_ARGS = ["--no-install-project", "--link-mode=copy"]`: always passed by the builders, never configurable.
- `STRUCTURAL_REASONS: dict[str, str]`: why, keyed by flag name.

### Validation

- `validate_artifacts(dir_python, path_pyproject_toml, check_linux=False, extras: list[str] | None = None, all_extras=False) -> dict`: checks every direct dependency (plus the given extras') has a `.dist-info` in `dir_python`; `check_linux=True` also fails non-Linux wheels. Prints a report, raises `AssertionError` on failure, else returns `{"ok": True, "packages": [...], "errors": []}`. Raises `KeyError` for an undeclared extra.

### Re-exported from `aws_lbd_art_builder_core.layer_api`

- `Credentials(index_name, index_url, username, password)`: private index auth, built for AWS CodeArtifact (password = token). `index_name` must match a `[[tool.uv.index]]` name; uv always logs in as user `aws`.
- `LayerPathLayout(path_pyproject_toml*)`: `.dir_python`, `.path_build_lambda_layer_zip`, `.dir_build_lambda_layer`, `.dir_repo`, ...
- `LayerS3Layout(s3dir_lambda)`; `move_to_dir_python(dir_site_packages, dir_python)`; `default_ignore_package_list`.
- `create_layer_zip_file(dir_python, path_layer_zip, ignore_package_list=None, verbose=True)`: step 2; needs the `zip` binary.
- `upload_layer_zip_to_s3(s3_client, path_pyproject_toml, s3dir_lambda, path_manifest, verbose=True, printer=print)`: step 3; `path_manifest` is the `uv.lock`.
- `LambdaLayerVersionPublisher(path_pyproject_toml*, s3dir_lambda*, path_manifest*, s3_client*, layer_name*, lambda_client*, publish_layer_version_kwargs=None)`: step 4. `.run() -> LayerDeployment`; raises `ValueError` when `uv.lock` is unchanged since the last published version.
- `LayerDeployment(layer_name, layer_version: int, layer_version_arn, s3path_manifest)`.

For all four steps in one call, pass a builder to core's `aws_lbd_art_builder_core.api.layer_api.LayerDeploymentWorkflow` (not re-exported here).

## Typical use

```python
from pathlib import Path
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv

layer_api = aws_lbd_art_builder_uv.layer_api
path_pyproject_toml = Path("pyproject.toml").absolute()
builder = layer_api.UvLambdaLayerContainerBuilder(
    path_pyproject_toml=path_pyproject_toml,
    py_ver_major=3,
    py_ver_minor=12,
    is_arm=False,
    skip_prompt=True,
    uv_sync_options=layer_api.UvSyncOptions(extras=["aws"]),
)
builder.run()
layer_api.validate_artifacts(
    dir_python=builder.path_layout.dir_python,
    path_pyproject_toml=path_pyproject_toml,
    check_linux=True,
    extras=["aws"],
)
```

## More detail

For signatures, semantics, gotchas and examples (including upload and publish) see `ref/public-api.md`. The library has no CLI.
