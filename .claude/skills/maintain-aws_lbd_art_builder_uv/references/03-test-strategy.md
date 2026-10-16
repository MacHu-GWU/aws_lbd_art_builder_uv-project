---
description: "How aws_lbd_art_builder_uv is tested: the split between unit tests in tests/ (pytest, moto, CI, Codecov) and integration tests in examples/ (real uv, Docker, AWS CodeArtifact, manual only), what each test file covers, the conftest .venv workaround, what is not covered and why, why examples copy the source, and the test matrix. Read when writing or fixing tests, deciding where a new test goes, or running the integration tests."
---

# Test Strategy

The code is small, but it shells out to `uv`, launches Docker, authenticates against a private index, and publishes to S3 and Lambda. So testing is split into two independent layers. The generic conventions (file mapping, `run_cov_test`, coverage rules) are in `pywf-oss-base`; this file covers what is specific to this repo.

## 1. Two layers

| | Unit tests (`tests/`) | Integration tests (`examples/`) |
| :--- | :--- | :--- |
| Run by | `mise run cov` | `mise run int-test` |
| Runner | pytest + pytest-cov | standalone scripts via each example's `mise.toml` |
| CI | yes, every push and PR (Ubuntu and Windows, Python 3.11 to 3.14) | no, manual only |
| AWS | mocked with `moto` | real CodeArtifact for the private-package example |
| Docker | not needed | needed for the container builder |
| Coverage | measured, uploaded to Codecov | not measured (runs a copy of the source) |
| Purpose | catch regressions, gate merges | prove the real workflows end to end |

## 2. Unit tests

| File | Covers | Needs |
| :--- | :--- | :--- |
| `tests/test_api.py`, `tests/layer/test_layer_api.py` | public imports | nothing |
| `tests/layer/test_uv_sync_options.py` | flag rendering, construction-time conflicts, `extra_args` rejection, `managed_args` completeness, `STRUCTURAL_ARGS` reasons, and the container script's literal copy (via `ast`) | nothing |
| `tests/layer/test_validate.py` | name normalization, version stripping, `.dist-info` lookup, wheel tags, `validate_artifacts` with synthetic `tmp_path` fixtures | nothing |
| `tests/layer/test_local_builder_e2e.py` | a real `uv sync` of `examples/my_lbd_app-project`, all four steps of the local builder, then `validate_artifacts` | `uv` |
| `tests/layer/test_deployment_e2e.py` | build → validate → `create_layer_zip_file` → `upload_layer_zip_to_s3` → `LambdaLayerVersionPublisher` under `@mock_aws`; asserts version 1, ARN format, manifest in S3 | `uv`, the test extra (`moto`, `boto_session_manager`, `s3pathlib`) |

`tests/layer/conftest.py` has a session-scoped autouse fixture, `ensure_example_venv`. Core's `LayerPathLayout.venv_python_version` runs `{project_root}/.venv/bin/python --version` on the **example project's** `.venv` (a known core bug: it should look at the build dir). Locally that `.venv` exists; on CI the fixture creates it with `uv venv --allow-existing`. Remove the fixture only once core is fixed.

Not covered by unit tests, on purpose:

- `container_builder.py` and `_build_in_container.py`: need Docker, marked `# pragma: no cover`.
- The credentials branch of the local builder (`step_3_1_uv_login` with credentials): needs a live private index.

Anything else new must be covered; a pure function goes in a synthetic-fixture test, not an e2e one.

## 3. Integration tests

| Example project | Dependencies | Scripts |
| :--- | :--- | :--- |
| `examples/my_lbd_app-project` | `boto3` (public PyPI) | `example_build_lambda_layer_using_uv_in_local.py`, `..._in_container.py` |
| `examples/my_lbd_app_with_private_pkg` | `boto3` + `esc-dummy-lib` from AWS CodeArtifact | same two, plus `example_settings.py` (fetches a CodeArtifact token with `boto_session_manager`) |

Each is a self-contained project with its own `pyproject.toml`, `uv.lock`, `mise.toml`, and `.venv`. The private one sources `.mise/tasks/codeartifact-env.sh` before `uv sync` and needs the AWS profiles in its `mise.toml` `[env]`.

```bash
mise run int-test
```

runs all four scenarios. One at a time:

```bash
mise run -C examples/my_lbd_app-project test-in-local
```

```bash
mise run -C examples/my_lbd_app-project test-in-container
```

```bash
mise run -C examples/my_lbd_app_with_private_pkg test-in-container
```

The container scripts call `validate_artifacts(..., check_linux=True)`.

### Why the examples copy the source

Each script (or `example_settings.py`) starts with `shutil.rmtree` + `shutil.copytree` of `aws_lbd_art_builder_uv/` into the example project. The examples are standalone projects that must exercise the **development** code without installing it. Consequences: changes are picked up on every run, coverage cannot see these runs, and the copies are git-ignored (`examples/*/aws_lbd_art_builder_uv`).

### Why the examples stay out of tests/

They are also user-facing documentation of how to call the library, and they carry their own `mise.toml`, `.venv`, and CodeArtifact setup. `tests/` imports the package directly and runs on CI.

## 4. Test matrix

| Scenario | Unit test | CI | Integration | Requires |
| :--- | :--- | :--- | :--- | :--- |
| API imports | `test_api.py`, `test_layer_api.py` | yes | — | nothing |
| `UvSyncOptions` | `test_uv_sync_options.py` | yes | — | nothing |
| Artifact validation | `test_validate.py` | yes | all four | nothing |
| Local build, public PyPI | `test_local_builder_e2e.py` | yes | `my_lbd_app-project` | `uv` |
| Build → zip → S3 → publish | `test_deployment_e2e.py` | yes | — | `uv`, `moto` |
| Local build, private index | — | — | `my_lbd_app_with_private_pkg` | `uv`, CodeArtifact |
| Container build, public PyPI | — | — | `my_lbd_app-project` | `uv`, Docker |
| Container build, private index | — | — | `my_lbd_app_with_private_pkg` | `uv`, Docker, CodeArtifact |

## 5. Which tests to run for a change

| Changed | Run |
| :--- | :--- |
| `uv_sync_options.py`, `validate.py`, `local_builder.py` | `mise run cov` |
| `container_builder.py`, `_build_in_container.py` | `mise run cov` (for the literal-sync test), then `test-in-container` in `my_lbd_app-project` |
| Credentials handling | the `my_lbd_app_with_private_pkg` scenarios (need AWS access) |
| Before a release | `mise run cov` and `mise run int-test` |

If a run needs Docker or AWS access you do not have, say which scenarios were not run instead of reporting the change as tested.
