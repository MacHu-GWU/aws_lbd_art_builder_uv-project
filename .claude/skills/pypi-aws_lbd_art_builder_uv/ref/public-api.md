# aws_lbd_art_builder_uv 1.0.0: public API reference

Import only through `aws_lbd_art_builder_uv.api`:

```python
from aws_lbd_art_builder_uv.api import layer_api
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv     # then aws_lbd_art_builder_uv.layer_api.X
```

## Conventions that apply everywhere

- **Install.** `pip install aws_lbd_art_builder_uv` is enough to build and validate. Uploading needs the `upload` extra and publishing the `publish` extra (they pull in `aws_lbd_art_builder_core[upload]` / `[publish]`: boto3, s3pathlib 3.x, simple_aws_lambda).
- **System tools.** `uv` on `PATH` (local builds), Docker (container builds), `zip` (packaging). POSIX only.
- **Inputs.** The project root is `path_pyproject_toml.parent`; `uv.lock` must sit next to `pyproject.toml`. Pass an absolute `path_pyproject_toml`.
- **Build directory.** Everything goes under `{root}/build/lambda/layer/`, which is deleted at the start of every build. With `skip_prompt=False` (the default) the builder asks on stdin first, which hangs a non-interactive run: pass `skip_prompt=True` in scripts and CI.
- **Project `.venv` required.** Step 4 builds the `site-packages` path as `build/lambda/layer/repo/.venv/lib/python{X.Y}/site-packages`, taking `X.Y` from `{root}/.venv/bin/python --version`: the **project's** venv, not the one uv just created (a known core 1.0.0 quirk). So `{root}/.venv` must exist (else `FileNotFoundError` on `.venv/bin/python`) and its minor version must match the build Python: the host's for local builds, `py_ver_major.py_ver_minor` for container builds (else the move fails on a missing `site-packages`). In CI, run `uv venv --python 3.12 --allow-existing` in the project first.
- **Output.** `builder.path_layout.dir_python` = `{root}/build/lambda/layer/artifacts/python/`, the folder that becomes `python/` in the layer zip.
- **Dataclasses.** Builders and `UvSyncOptions` are frozen dataclasses: pass fields by keyword. Builders also take `verbose: bool = True` and `printer: Callable[[str], None] = print`.
- **AWS clients.** `s3_client` / `lambda_client` are plain boto3 clients. A `BotoSesManager` raises `TypeError`; pass `bsm.s3_client`. S3 locations are `s3pathlib.api.S3Path`, directories ending with `/`.

---

## Builders

### `UvLambdaLayerLocalBuilder`

```python
UvLambdaLayerLocalBuilder(
    path_pyproject_toml: Path,                 # required
    credentials: Credentials | None = None,    # private index, see Credentials
    skip_prompt: bool = False,
    path_bin_uv: Path | None = None,           # None → "uv" on PATH
    uv_sync_options: UvSyncOptions = UvSyncOptions(),
    verbose: bool = True,
    printer = print,
)
.path_layout -> LayerPathLayout       # cached
.run()                                # the four steps below, in order
.step_1_preflight_check()             # print build info
.step_2_prepare_environment()         # wipe build dir, copy pyproject.toml + uv.lock to build/lambda/layer/repo/
.step_3_execute_build()               # credentials → env vars, then uv sync in repo/
.step_4_finalize_artifacts()          # move repo/.venv/.../site-packages → artifacts/python/
```

Runs `uv sync --no-install-project --link-mode=copy <uv_sync_options.to_args()>` in `build/lambda/layer/repo/` with the host's Python. Fast, but the wheels match the host: on macOS, packages with C extensions (numpy, pydantic-core, cryptography, ...) get Mach-O binaries that fail on Lambda. Use the container builder for those, or try `UvSyncOptions(extra_args=["--python-platform", "x86_64-manylinux_2_28"])`.

With `credentials`, step 3 sets the env vars `UV_INDEX_{INDEX_NAME}_USERNAME` / `_PASSWORD` on the current process. They stay set after the build.

`python3.X` of the `.venv` comes from whatever Python uv picks on the host, so it should match the Lambda runtime you publish for.

```python
builder = layer_api.UvLambdaLayerLocalBuilder(
    path_pyproject_toml=dir_project / "pyproject.toml",
    skip_prompt=True,
)
builder.run()
```

### `UvLambdaLayerContainerBuilder`

```python
UvLambdaLayerContainerBuilder(
    path_pyproject_toml: Path,                 # required
    py_ver_major: int,                         # required, e.g. 3
    py_ver_minor: int,                         # required, e.g. 12
    is_arm: bool,                              # required: True → arm64, False → x86_64
    credentials: Credentials | None = None,
    skip_prompt: bool = False,
    uv_sync_options: UvSyncOptions = UvSyncOptions(),
    path_script: Path = <bundled container script>,   # leave as is
    verbose: bool = True,
    printer = print,
)
.path_layout -> LayerPathLayout
.run() / .step_1_preflight_check() / .step_2_prepare_environment() / .step_3_execute_build() / .step_4_finalize_artifacts()
.image_uri -> str          # public.ecr.aws/sam/build-python3.12:latest-x86_64
.platform -> str           # linux/amd64 | linux/arm64
.container_name -> str     # lambda_layer_builder-python312-amd64
.script_args -> list[str]  # == uv_sync_options.to_args(), forwarded to the container
.docker_run_args -> list[str]
```

Mounts `{root}/build/lambda/layer/` at `/var/task/` in the AWS SAM build image, installs uv inside it, runs the same `uv sync`, then moves the result to `artifacts/python/` on the host. The output matches the Lambda runtime and architecture exactly, so C extensions work. Pick `py_ver_*` and `is_arm` to match the function's runtime and `CompatibleArchitectures`.

- Step 1 raises `FileNotFoundError` if `{root}/uv.lock` is missing (before pulling the image). Run `uv lock` first.
- `credentials` are written to `build/lambda/layer/private-repository-credentials.json` for the container to read, never put on the command line. Delete the build directory afterwards if the token must not stay on disk.
- First run pulls the image (several hundred MB). Docker must be running.

```python
builder = layer_api.UvLambdaLayerContainerBuilder(
    path_pyproject_toml=dir_project / "pyproject.toml",
    py_ver_major=3,
    py_ver_minor=12,
    is_arm=False,
    skip_prompt=True,
)
builder.run()
```

---

## `UvSyncOptions`

```python
UvSyncOptions(
    extras: list[str] = [],          # --extra NAME (one per name)
    all_extras: bool = False,        # --all-extras
    no_extras: list[str] = [],       # --no-extra NAME, only with all_extras=True
    groups: list[str] = [],          # --group NAME
    no_groups: list[str] = [],       # --no-group NAME
    all_groups: bool = False,        # --all-groups
    no_default_groups: bool = False, # --no-default-groups
    no_dev: bool = True,             # --no-dev
    frozen: bool = True,             # --frozen: use uv.lock as is, no re-resolve
    extra_args: list[str] = [],      # any other uv sync flag, verbatim
)
.to_args() -> list[str]
UvSyncOptions.managed_args: dict[str, str]   # flag → field name, e.g. "--extra" → "extras"
```

Decides which dependencies land in the layer. The default (`["--frozen", "--no-dev"]`) installs `[project] dependencies` only. `to_args()` order: `--frozen`, `--no-dev`, `--no-default-groups`, `--all-extras`, `--extra`s, `--no-extra`s, `--all-groups`, `--group`s, `--no-group`s, then `extra_args`. It never includes `STRUCTURAL_ARGS`.

Construction raises `ValueError` when:

- `extras` and `all_extras=True` are both set.
- `no_extras` is set without `all_extras=True` (uv would ignore it silently).
- an `extra_args` entry is `--no-install-project` or `--link-mode[=...]` (structural; the message quotes `STRUCTURAL_REASONS`).
- an `extra_args` entry is a flag already owned by a field (`--extra`, `--group`, `--frozen`, `--no-dev`, ...); the message names the field to use.

Bare values in `extra_args` (e.g. `"x86_64-manylinux_2_28"` after `--python-platform`) are not mistaken for flags.

```python
UvSyncOptions(extras=["a", "b"], groups=["g"]).to_args()
# ['--frozen', '--no-dev', '--extra', 'a', '--extra', 'b', '--group', 'g']

UvSyncOptions(all_extras=True, no_extras=["dev"]).to_args()
# ['--frozen', '--no-dev', '--all-extras', '--no-extra', 'dev']

UvSyncOptions(extra_args=["--python-platform", "x86_64-manylinux_2_28"])

UvSyncOptions(extra_args=["--extra", "a"])   # ValueError: set the 'extras' field instead
```

To get a build that really differs on a structural flag, subclass the builder and override `step_3_2_run_uv_sync` (local builder only); producing a working layer is then up to you.

### `STRUCTURAL_ARGS`, `STRUCTURAL_REASONS`

```python
STRUCTURAL_ARGS = ["--no-install-project", "--link-mode=copy"]
STRUCTURAL_REASONS: dict[str, str]   # keys "--no-install-project", "--link-mode"
```

Always passed by both builders. `--no-install-project`: the layer holds dependencies only, and installing the project from the build directory would produce a broken editable install. `--link-mode=copy`: symlinks into the uv cache do not survive zipping.

---

## `validate_artifacts`

```python
validate_artifacts(
    dir_python: Path,              # builder.path_layout.dir_python
    path_pyproject_toml: Path,
    check_linux: bool = False,     # True → fail on non-Linux platform wheels
    extras: list[str] | None = None,
    all_extras: bool = False,
) -> dict   # {"ok": bool, "packages": [{"name", "found", "tags", "linux"}], "errors": [str]}
```

Checks that every **direct** dependency in `[project] dependencies` (plus those of `extras`, or of every extra with `all_extras=True`) has a `{name}-{version}.dist-info` folder in `dir_python`. Names are compared PEP 503-normalized. Transitive dependencies are not checked. `linux` per package is `True` (Linux wheel), `False` (other platform) or `None` (pure Python).

- Prints a human-readable report to stdout.
- Raises `AssertionError` listing the errors on failure; so the returned dict always has `"ok": True`.
- Raises `KeyError` for an extra not declared in `[project.optional-dependencies]`.
- Pass the same extras as `UvSyncOptions`, or the packages they pulled in go unchecked. Dependency groups are not checked.
- Use `check_linux=True` after container builds; after a local macOS build it fails on any C extension (which is the point).

```python
layer_api.validate_artifacts(
    dir_python=builder.path_layout.dir_python,
    path_pyproject_toml=builder.path_layout.path_pyproject_toml,
    check_linux=True,
)
```

---

## Re-exported from `aws_lbd_art_builder_core.layer_api`

Same objects as in core 1.x; see the `pypi-aws_lbd_art_builder_core` skill for full detail.

### `Credentials`

```python
Credentials(index_name: str, index_url: str, username: str, password: str)
.uv_login() -> tuple[str, str]   # sets UV_INDEX_{NAME}_USERNAME="aws" and _PASSWORD, returns the env var names
.dump(path) / Credentials.load(path)
```

`index_name` must equal the `name` of a `[[tool.uv.index]]` in `pyproject.toml` (the env var uses it upper-cased, `-` → `_`). Designed for AWS CodeArtifact: uv always logs in as user `aws` and `password` is the CodeArtifact token.

```python
import boto3

ca = boto3.client("codeartifact")
index_url = ca.get_repository_endpoint(domain=domain, repository=repo, format="pypi")["repositoryEndpoint"]
token = ca.get_authorization_token(domain=domain, durationSeconds=900)["authorizationToken"]
credentials = layer_api.Credentials(index_name="esc", index_url=index_url, username="aws", password=token)
builder = layer_api.UvLambdaLayerLocalBuilder(path_pyproject_toml=..., credentials=credentials, skip_prompt=True)
```

### Paths

- `LayerPathLayout(path_pyproject_toml)`: `.dir_project_root`, `.dir_build_lambda_layer` (`build/lambda/layer/`), `.dir_repo`, `.dir_python` (`artifacts/python/`), `.path_build_lambda_layer_zip` (`build/lambda/layer/layer.zip`), `.dir_build_lambda_layer_repo_venv_site_packages`, `.clean(skip_prompt=False)`, `.mkdirs()`.
- `LayerS3Layout(s3dir_lambda: S3Path)`: `.s3path_temp_layer_zip` (`{s3dir_lambda}/layer/layer.zip`), `.get_s3dir_layer_version(n)`, `.get_s3path_layer_manifest(n, filename)`.

### Package, upload, publish

```python
default_ignore_package_list: list[str]   # boto3, botocore, s3transfer, urllib3, setuptools, pip, wheel, twine, _pytest, pytest
move_to_dir_python(dir_site_packages: Path, dir_python: Path)
create_layer_zip_file(dir_python: Path, path_layer_zip: Path, ignore_package_list: list[str] | None = None, verbose: bool = True)
upload_layer_zip_to_s3(s3_client, path_pyproject_toml: Path, s3dir_lambda: S3Path, path_manifest: Path, verbose=True, printer=print)
LambdaLayerVersionPublisher(path_pyproject_toml, s3dir_lambda, path_manifest, s3_client, layer_name, lambda_client,
                            publish_layer_version_kwargs: dict | None = None, verbose=True, printer=print)
    .run() -> LayerDeployment
    .is_layer_zip_exists() -> bool / .is_layer_zip_consistent() -> bool / .has_dependency_manifest_changed() -> bool
LayerDeployment(layer_name: str, layer_version: int, layer_version_arn: str, s3path_manifest: S3Path)
```

- `create_layer_zip_file` leaves out `default_ignore_package_list` by default, because the Lambda runtime already ships boto3 and friends. Pass `ignore_package_list=[]` to keep everything.
- For a uv build, `path_manifest` is `{root}/uv.lock`. Change detection compares it with the copy stored for the last published version.
- `LambdaLayerVersionPublisher.run()` raises `ValueError` when `uv.lock` is unchanged, so publishing twice in a row fails on purpose. Check `.has_dependency_manifest_changed()` first for a soft skip.
- `publish_layer_version_kwargs` go to boto3 `publish_layer_version` (`CompatibleRuntimes`, `CompatibleArchitectures`, `Description`, ...).

### End to end (trimmed from `tests/layer/test_deployment_e2e.py`)

```python
import boto3
from s3pathlib.api import S3Path
import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv

layer_api = aws_lbd_art_builder_uv.layer_api
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")
s3dir_lambda = S3Path("s3://my-bucket/projects/my_app/lambda/").to_dir()
path_pyproject_toml = dir_project / "pyproject.toml"
path_manifest = dir_project / "uv.lock"

builder = layer_api.UvLambdaLayerLocalBuilder(path_pyproject_toml=path_pyproject_toml, skip_prompt=True)
builder.run()
layer_api.validate_artifacts(dir_python=builder.path_layout.dir_python, path_pyproject_toml=path_pyproject_toml)

layer_api.create_layer_zip_file(
    dir_python=builder.path_layout.dir_python,
    path_layer_zip=builder.path_layout.path_build_lambda_layer_zip,
)
layer_api.upload_layer_zip_to_s3(
    s3_client=s3_client,
    path_pyproject_toml=path_pyproject_toml,
    s3dir_lambda=s3dir_lambda,
    path_manifest=path_manifest,
)
layer_deployment = layer_api.LambdaLayerVersionPublisher(
    path_pyproject_toml=path_pyproject_toml,
    s3dir_lambda=s3dir_lambda,
    path_manifest=path_manifest,
    s3_client=s3_client,
    layer_name="my_app",
    lambda_client=lambda_client,
    publish_layer_version_kwargs={"CompatibleRuntimes": ["python3.12"]},
).run()
print(layer_deployment.layer_version_arn)
```

### One call with core's workflow

`LayerDeploymentWorkflow` is not re-exported; import it from core. It accepts either builder.

```python
from aws_lbd_art_builder_core.api import layer_api as core_layer_api

layer_deployment = core_layer_api.LayerDeploymentWorkflow(
    builder=builder,                 # UvLambdaLayerLocalBuilder or UvLambdaLayerContainerBuilder
    path_manifest=path_manifest,
    s3dir_lambda=s3dir_lambda,
    layer_name="my_app",
    s3_client=s3_client,
    lambda_client=lambda_client,
    publish_layer_version_kwargs={"CompatibleRuntimes": ["python3.12"]},
).run()
```
