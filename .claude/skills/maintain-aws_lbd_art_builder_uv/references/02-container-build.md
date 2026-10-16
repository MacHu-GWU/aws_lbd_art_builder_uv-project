---
description: "How UvLambdaLayerContainerBuilder runs uv sync inside an AWS SAM Docker image: why a container, the image and platform selection, the single bind mount, the docker run command, the container-side script _build_in_container.py and its pure-stdlib rule, credential handoff through a JSON file, and the STRUCTURAL_ARGS literal that must stay in sync. Read before changing container_builder.py or _build_in_container.py, or when a container build fails."
---

# Container Build

Read `01-build-pipeline.md` first; this file covers only what differs for the container.

## 1. Why a container

Packages with C extensions (`numpy`, `pandas`, `lxml`) built on macOS or a non-Amazon-Linux host produce binaries the Lambda runtime cannot load. The container builder runs `uv sync` inside the official AWS SAM build image, which matches the Lambda execution environment.

Requirements: macOS or Linux host (Windows is not supported), Docker running, and an up-to-date `uv.lock` (the builder never runs `uv lock`; that is a state change the developer makes explicitly).

## 2. Image and platform

`UvLambdaLayerContainerBuilder` subclasses core's `BaseLambdaLayerContainerBuilder`, which owns `py_ver_major`, `py_ver_minor`, `is_arm`, the image URI, and `docker_run_args`.

| `is_arm` | Image | `--platform` |
| :--- | :--- | :--- |
| `False` | `public.ecr.aws/sam/build-python{major}.{minor}:latest-x86_64` | `linux/amd64` |
| `True` | `public.ecr.aws/sam/build-python{major}.{minor}:latest-arm64` | `linux/arm64` |

This package adds `path_script`, `credentials`, `skip_prompt`, and `uv_sync_options`, and overrides core's `script_args` hook to return `uv_sync_options.to_args()`; core appends `script_args` to the `docker run` command.

## 3. Mount scheme

One bind mount, and all host ↔ container exchange goes through it:

| Host | Container |
| :--- | :--- |
| `{git_repo}/build/lambda/layer` | `/var/task` |
| `.../build_lambda_layer_in_container.py` | `/var/task/build_lambda_layer_in_container.py` |
| `.../private-repository-credentials.json` | `/var/task/private-repository-credentials.json` |
| `.../repo/` (`pyproject.toml`, `uv.lock`, `.venv/`) | `/var/task/repo/` |

Mount `build/lambda/layer/`, never the project root, so the host's `.venv` and source never enter the container. Because it is a bind mount, what `uv sync` installs is on the host as soon as the container exits, and host step 4 moves it to `artifacts/python/`.

The step 3 command has the shape:

```bash
docker run --rm \
    --name lambda_layer_builder-python312-amd64 \
    --platform linux/amd64 \
    --mount type=bind,source={git_repo}/build/lambda/layer,target=/var/task \
    public.ecr.aws/sam/build-python3.12:latest-x86_64 \
    python -u /var/task/build_lambda_layer_in_container.py <script_args>
```

## 4. The container-side script

`_build_in_container.py` is copied in step 2 and runs inside the container in four steps:

1. Verify `/var/task/repo` exists, so the script refuses to run on the host.
2. Install uv with `curl -LsSf https://astral.sh/uv/install.sh | sh` → `/root/.local/bin/uv`.
3. If the credentials JSON exists, set `UV_INDEX_{NAME}_USERNAME` / `_PASSWORD` (same normalization as `Credentials.uv_login()`).
4. Run `uv sync --no-install-project --link-mode=copy <forwarded args>` in `/var/task/repo`.

Rules to keep:

- **Pure stdlib, Python 3.11+, import-free from this package.** The SAM image has nothing installed but Python. Any import from `aws_lbd_art_builder_uv` or a third-party package breaks it.
- **uv is installed at runtime, not baked into an image.** Using the official SAM image directly guarantees runtime compatibility and avoids maintaining a custom image.
- **Arguments it does not know are forwarded verbatim to `uv sync`** (`parse_known_args`). It declares only `--dir-task`. Never re-declare uv flags here; `UvSyncOptions` is the one place that knows uv's CLI.
- **Credentials travel as a JSON file, not `docker run -e`**, so tokens never appear in a command line visible in process listings.
- **The `uv_sync_command` literal is a copy of `STRUCTURAL_ARGS`.** `test_container_script_copy_is_in_sync` parses the script with `ast` and compares; keep the variable name `uv_sync_command` and keep the flags as string literals in that one list, or the test fails.
- Log through `_log_sub_header` / `_log`, which match the host-side `BaseLogger` format.

## 5. Testing a change here

None of this runs under `mise run cov`. After changing either file, run the container integration tests (see `03-test-strategy.md`):

```bash
mise run -C examples/my_lbd_app-project test-in-container
```

and, if credentials handling changed, the private-package variant too.
