---
name: learn-this-project
description: >
  Learn the Lambda layer builder project — architecture, implementation,
  testing strategy, and design decisions.  Use when you need to understand
  how the UV-based Lambda layer build system works, why certain design
  choices were made, or how to test/debug the build pipeline.
disable-model-invocation: true
---

# Learn This Project — UV Lambda Layer Builder

Read the files listed below to build a complete mental model of this project.
After reading, provide a structured summary covering: architecture overview,
the two build paths (local vs container), credential handling, artifact
validation, testing strategy, and key design decisions (the "why" behind
non-obvious choices).

## 1. Architecture & Design Docs

Read these docs first — they explain the overall design and the "why":

- [Local build guide](docs/source/99-Maintainer-Guide/02-Build-Lambda-Layer-using-UV-in-Local/index.rst)
  — When and why to build locally, directory layout, uv flags explained.
- [Container build guide](docs/source/99-Maintainer-Guide/03-Build-Lambda-Layer-using-UV-in-Container/index.rst)
  — Why containerized builds exist (binary compatibility), host/container split,
    Docker mount scheme, AWS SAM image selection.
- [Test strategy](docs/source/99-Maintainer-Guide/04-Test-Strategy/index.rst)
  — Why testing is complex, two-layer approach (unit + integration), CI limitations,
    manual-only private repo testing.

## 2. Core Implementation

Read these source files — pay attention to inline "why" comments:

- [api.py](aws_lbd_art_builder_uv/layer/api.py)
  — Public re-export surface.  Entry point for end users.
- [local_builder.py](aws_lbd_art_builder_uv/layer/local_builder.py)
  — `UvLambdaLayerLocalBuilder`: 4-step workflow running `uv sync` on the host.
    Key decisions: no Python version required (uses host's), credentials set in
    Step 3 (not Step 2) to minimize env var exposure window.
- [container_builder.py](aws_lbd_art_builder_uv/layer/container_builder.py)
  — `UvLambdaLayerContainerBuilder`: 4-step workflow running `uv sync` inside Docker.
    Key decisions: early `uv.lock` check (container builds are slow), credentials
    written as JSON file (not docker env vars, for security).
- [_build_in_container.py](aws_lbd_art_builder_uv/layer/_build_in_container.py)
  — The script that runs *inside* the Docker container.  Pure stdlib by design
    (bare SAM image has nothing installed).  Installs uv via curl at runtime
    (avoids maintaining a custom Docker image).
- [validate.py](aws_lbd_art_builder_uv/layer/validate.py)
  — Post-build validation: checks each dependency in `pyproject.toml` has a
    matching `.dist-info` in artifacts.  Uses assert (designed for scripts/pytest).
    Complex regex in `_find_dist_info` handles package names with embedded digits.

## 3. Integration Test Examples

These are standalone projects that double as integration tests:

- [examples/my_lbd_app-project/example_build_lambda_layer_using_uv_in_local.py](examples/my_lbd_app-project/example_build_lambda_layer_using_uv_in_local.py)
- [examples/my_lbd_app-project/example_build_lambda_layer_using_uv_in_container.py](examples/my_lbd_app-project/example_build_lambda_layer_using_uv_in_container.py)
- [examples/my_lbd_app_with_private_pkg/example_build_lambda_layer_using_uv_in_local.py](examples/my_lbd_app_with_private_pkg/example_build_lambda_layer_using_uv_in_local.py)
- [examples/my_lbd_app_with_private_pkg/example_build_lambda_layer_using_uv_in_container.py](examples/my_lbd_app_with_private_pkg/example_build_lambda_layer_using_uv_in_container.py)

Note: the `my_lbd_app-project` examples use `shutil.copytree` to copy the dev
version of the builder package into the example project.  This is intentional —
these are standalone projects with their own `pyproject.toml` / `uv.lock`, and
need to test the *development* code, not a released version.

## 4. Key Design Decisions Cheat Sheet

After reading all files, confirm you understand these decisions and their rationale:

| Decision | Why |
|---|---|
| Container script is pure stdlib | SAM image has nothing installed; avoids extra install steps |
| uv installed via curl at runtime | Avoids maintaining custom Docker image; always gets latest uv |
| Credentials via JSON file (container) | Avoids leaking tokens in `docker run` command lines |
| Credentials in Step 3 (local) | Minimizes env var exposure window; adjacent to the command that needs them |
| `--link-mode=copy` | Lambda layers are zipped — symlinks would break in the Lambda runtime |
| `--frozen` | Reproducible builds from lock file, no re-resolution |
| `--no-install-project` | Layer only needs dependencies, not the project itself |
| Container builder checks `uv.lock` early | Container builds are slow; fail-early saves minutes |
| Local builder skips `uv.lock` check | Local builds are fast; `uv sync` will fail quickly anyway |
| No Python version in local builder | Always uses host's Python; can't target another version without a container |
| `validate_artifacts` uses assert | Designed for build scripts and pytest — crashes clearly on failure |
| Complex regex in `_find_dist_info` | Handles package names with digits (e.g. `zipp-3.20.2.dist-info`) |
| Examples copy source with `shutil.copytree` | Standalone projects testing dev version without pip install |