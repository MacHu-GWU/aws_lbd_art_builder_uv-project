---
name: maintain-aws_lbd_art_builder_uv
description: "Project-specific knowledge for maintaining the aws_lbd_art_builder_uv repo: how the local and container Lambda layer builders work (the four-step workflow, the build directory, UvSyncOptions and its structural / managed / pass-through uv sync flags, validate_artifacts), how the container build runs uv inside an AWS SAM image through one bind mount and a pure-stdlib script, and how testing is split between unit tests on CI and manual integration tests in examples/ (Docker, AWS CodeArtifact). Use before changing the library code, fixing a bug in it, reviewing a change to it, writing or fixing its tests, running the integration tests, or when someone asks how this project works."
---

Knowledge that only this repo needs. The conventions shared by every pywf open-source library (layout, code style, tests, docs, CI, release, dependencies) are in `pywf-oss-base`, not here; load that skill for them.

## The project in three lines

- Two builders turn a project's `pyproject.toml` + `uv.lock` into a Lambda layer folder (`build/lambda/layer/artifacts/python/`): `UvLambdaLayerLocalBuilder` runs `uv sync` on the host, `UvLambdaLayerContainerBuilder` runs it inside an AWS SAM image for C extensions.
- Both always pass `--no-install-project --link-mode=copy` (`STRUCTURAL_ARGS`); every other `uv sync` flag comes from `UvSyncOptions`.
- Zipping, uploading, publishing, paths, and credentials come from `aws_lbd_art_builder_core`; this package only builds and validates.

## Which reference to read

| When | Read |
| :--- | :--- |
| Changing, fixing, or reviewing code in `aws_lbd_art_builder_uv/layer/`, adding a `uv sync` option, or changing artifact validation | [references/01-build-pipeline.md](references/01-build-pipeline.md) |
| Changing `container_builder.py` or `_build_in_container.py`, or debugging a container build | [references/01-build-pipeline.md](references/01-build-pipeline.md), then [references/02-container-build.md](references/02-container-build.md) |
| Writing or fixing tests, deciding where a test goes, or running the integration tests in `examples/` | [references/03-test-strategy.md](references/03-test-strategy.md) |
| Answering "how does this project work?" | all three, in order |

## Related skills

- `pywf-oss-base`: repo-wide conventions, and which `pywf-oss-*` skill does which job (add a module, write tests, write docs, changelog, release).
- `pypi-aws_lbd_art_builder_core`: the core API (zip, upload, publish) this package builds on.
- `pypi-s3pathlib`: `S3Path`, used by the deployment test. `pypi-boto_session_manager`: used only by the private-package example.
