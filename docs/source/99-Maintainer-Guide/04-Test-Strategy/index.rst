.. _Test-Strategy:

Test Strategy
==============================================================================


Why Testing This Project Is Not Straightforward
------------------------------------------------------------------------------
This project has very little code, but its execution environment is unusually complex:

- The **local builder** shells out to ``uv sync``, which creates a real ``.venv`` and downloads packages from PyPI.
- The **container builder** launches a Docker container with an AWS SAM image, bind-mounts a directory, installs ``uv`` inside the container, and runs ``uv sync`` there.
- The **private repository** variant requires live AWS CodeArtifact credentials to authenticate against a private PyPI index.
- The **full pipeline** (build → package → upload → publish) touches S3, Lambda, and depends on manifest consistency checks.

A newcomer cannot just read the source and understand what's testable where. This document explains the full picture.


Two Testing Layers
------------------------------------------------------------------------------
We split testing into two independent layers, each with a different purpose:

.. list-table::
   :header-rows: 1
   :widths: 20 40 40

   * - Layer
     - Unit / Coverage Tests (``tests/``)
     - Integration Tests (``examples/``)
   * - **Where**
     - ``tests/`` directory, run by ``mise run cov``
     - ``examples/`` directory, run by ``mise run int-test``
   * - **Runner**
     - pytest + pytest-cov
     - Standalone Python scripts via mise tasks
   * - **CI**
     - Yes — GitHub Actions on every push/PR
     - No — manual only (requires Docker, CodeArtifact)
   * - **AWS**
     - Mocked with ``moto`` — no credentials needed
     - Real or mocked depending on scenario
   * - **Docker**
     - Not needed
     - Required for container builder tests
   * - **Private repo**
     - Not tested (no CodeArtifact in CI)
     - Tested in ``my_lbd_app_with_private_pkg``
   * - **Coverage**
     - Tracked and reported to Codecov
     - Not tracked (imports a copy of the source)
   * - **Purpose**
     - Catch regressions, verify logic, gate merges
     - Validate real-world workflows end-to-end


Unit / Coverage Tests (``tests/``)
------------------------------------------------------------------------------

Directory structure::

    tests/
    ├── all.py                          ← run all tests with coverage
    ├── test_api.py                     ← top-level API import test
    └── layer/
        ├── all.py                      ← run layer tests with coverage
        ├── conftest.py                 ← shared fixtures
        ├── test_layer_api.py           ← layer API import test
        ├── test_validate.py            ← validate.py unit tests
        ├── test_local_builder_e2e.py   ← local builder e2e test
        └── test_deployment_e2e.py      ← full pipeline e2e test (moto)


How to run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # Run all tests with coverage report
    mise run cov

    # View HTML coverage report in browser
    mise run view-cov


test_validate.py — Pure Unit Tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests for :mod:`~aws_lbd_art_builder_uv.layer.validate` — the artifact validation module.

These tests use **synthetic fixtures only**: they create fake ``.dist-info/WHEEL`` files and ``pyproject.toml`` in ``tmp_path``. No ``uv``, Docker, or AWS needed. This is the fastest and most portable test file.

What it covers:

- Package name normalization (PEP 503)
- Version specifier stripping from dependency strings
- ``.dist-info`` directory lookup by normalized name
- Wheel tag parsing (pure Python, Linux, macOS, musllinux)
- ``validate_artifacts()`` — found/missing packages, ``check_linux`` flag


test_local_builder_e2e.py — Real uv sync
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Runs a real ``uv sync`` against ``examples/my_lbd_app-project/`` and validates the output.

- **Requires**: ``uv`` installed on the host (available in CI via ``astral-sh/setup-uv``)
- **What it does**: Creates a ``UvLambdaLayerLocalBuilder``, calls ``builder.run()``, then runs ``validate_artifacts()`` on the result
- **Covers**: ``local_builder.py`` — all 4 steps (preflight, prepare, build, finalize)
- **Does NOT cover**: The credentials branch (lines 113-115), because the example project has no private index


test_deployment_e2e.py — Full Pipeline with moto
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Tests the complete Build → Package → Upload → Publish pipeline using ``@mock_aws``.

- **Requires**: ``uv`` on host + ``moto``, ``boto_session_manager``, ``s3pathlib`` (all in test extras)
- **No real AWS credentials needed** — S3 and Lambda are fully mocked
- **What it does**:

  1. Creates a mock S3 bucket
  2. Builds with ``UvLambdaLayerLocalBuilder`` (real ``uv sync``)
  3. Validates artifacts
  4. Creates ``layer.zip`` with ``create_layer_zip_file()``
  5. Uploads to mocked S3 with ``upload_layer_zip_to_s3()``
  6. Publishes a Lambda layer version with ``LambdaLayerVersionPublisher``
  7. Asserts: layer version = 1, ARN format correct, manifest stored in S3

- **Covers**: ``local_builder.py`` + ``validate.py`` + core's package/upload/publish modules


conftest.py — The venv Workaround
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Contains a ``session``-scoped ``autouse`` fixture: ``ensure_example_venv``.

**Why it exists**: The core library's ``LayerPathLayout.venv_python_version`` property runs ``{project_root}/.venv/bin/python --version`` to detect the Python version for constructing the ``site-packages`` path. It looks at the **project root's** ``.venv``, not the build directory's ``.venv`` (this is a known bug in core).

Locally, this ``.venv`` exists because developers run ``mise run inst`` in the example project. In CI, it doesn't exist. The fixture creates it with ``uv venv --allow-existing`` before any e2e test runs.


What is NOT covered by unit tests
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
- **container_builder.py** — Requires Docker. Marked with ``# pragma: no cover``. Tested only via integration tests.
- **_build_in_container.py** — Runs inside a Docker container. Marked with ``# pragma: no cover``. Tested only via integration tests.
- **Private repository credentials** — Requires live CodeArtifact. Tested only via ``examples/my_lbd_app_with_private_pkg``.


Integration Tests (``examples/``)
------------------------------------------------------------------------------

Two dummy projects simulate real-world usage:

.. list-table::
   :header-rows: 1
   :widths: 35 30 35

   * - Example Project
     - Dependencies
     - What It Tests
   * - ``my_lbd_app-project``
     - ``boto3`` (public PyPI only)
     - Local build, container build, full pipeline (moto)
   * - ``my_lbd_app_with_private_pkg``
     - ``boto3`` + ``esc-dummy-lib`` (private CodeArtifact)
     - Same as above, plus credential handling

Each example project is a **self-contained Python project** with its own ``pyproject.toml``, ``uv.lock``, ``mise.toml``, and ``.venv``.


Directory layout
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
::

    examples/
    ├── my_lbd_app-project/
    │   ├── pyproject.toml                                    ← deps: boto3
    │   ├── uv.lock
    │   ├── mise.toml                                         ← test tasks
    │   ├── my_lbd_app/                                       ← dummy package
    │   ├── example_build_lambda_layer_using_uv_in_local.py
    │   └── example_build_lambda_layer_using_uv_in_container.py
    │
    └── my_lbd_app_with_private_pkg/
        ├── pyproject.toml                                    ← deps: boto3 + esc-dummy-lib
        ├── uv.lock
        ├── mise.toml                                         ← test tasks + CodeArtifact env vars
        ├── example_settings.py                               ← credential fetching
        ├── example_build_lambda_layer_using_uv_in_local.py
        └── example_build_lambda_layer_using_uv_in_container.py


How to run
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    # From project root — run ALL integration tests
    mise run int-test

    # Or run individual scenarios from inside an example project:
    cd examples/my_lbd_app-project
    mise run test-in-local       # local builder (no Docker)
    mise run test-in-container   # container builder (needs Docker)

    cd examples/my_lbd_app_with_private_pkg
    mise run test-in-local       # local builder + CodeArtifact credentials
    mise run test-in-container   # container builder + CodeArtifact credentials


Why examples copy the source (shutil.copytree)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
The example scripts start with:

.. code-block:: python

    dir_source = dir_project_root.parent.parent / "aws_lbd_art_builder_uv"
    dir_target = dir_project_root / "aws_lbd_art_builder_uv"
    shutil.copytree(dir_source, dir_target)

This is because the library is **not installed** inside the example project's ``.venv`` — it's a development copy. The script copies the source into the example project directory so it can be imported directly. This means:

- Coverage tools cannot track these runs (they see the copy, not the original)
- Changes to the source are picked up immediately (no reinstall needed)
- The ``my_lbd_app_with_private_pkg`` example uses ``example_settings.py`` to centralize this copy logic and credential configuration


Why examples are NOT moved into tests/
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
They serve different purposes:

- **``examples/``** are user-facing documentation — they show "how to use this library" and are referenced from the docs
- **``tests/``** are CI-facing — they verify correctness and track coverage
- Examples have their own ``mise.toml``, ``.venv``, CodeArtifact config — moving them into ``tests/`` would mix concerns
- The ``shutil.copytree`` hack is only needed in examples; ``tests/`` imports the package directly

Both can test the same logic, but with different mechanisms: examples use ``shutil.copytree`` + standalone scripts, tests use ``import`` + pytest + moto.


CI Pipeline
------------------------------------------------------------------------------

GitHub Actions runs on every push and PR to ``main``:

.. code-block:: yaml

    strategy:
      matrix:
        python-version: ["3.11", "3.12", "3.13", "3.14"]

Steps:

1. Checkout code
2. Setup Python (matrix version)
3. Install ``uv`` (via ``astral-sh/setup-uv``)
4. Install dependencies (``uv sync --extra test``, cached by ``uv.lock`` hash)
5. Run ``pytest tests/`` with coverage
6. Upload coverage to Codecov

**What CI does NOT run**: integration tests (no Docker, no CodeArtifact in CI).


Coverage Configuration
------------------------------------------------------------------------------

``.coveragerc`` excludes from measurement:

- ``docs/``, ``tests/``, ``vendor/`` — not production code
- ``_version.py``, ``cli.py``, ``paths.py`` — configuration files
- Lines marked ``# pragma: no cover``
- ``if __name__ == "__main__":`` blocks

Modules marked ``# pragma: no cover`` at class/function level:

- ``container_builder.py`` (entire class) — requires Docker
- ``_build_in_container.py`` (all functions) — runs inside container only


Test Matrix Summary
------------------------------------------------------------------------------

.. list-table::
   :header-rows: 1
   :widths: 35 15 15 15 15

   * - Scenario
     - Unit Test
     - CI
     - Int Test
     - Requires
   * - API imports
     - ``test_api.py``
     - Yes
     - —
     - Nothing
   * - Artifact validation logic
     - ``test_validate.py``
     - Yes
     - —
     - Nothing
   * - Local build (public PyPI)
     - ``test_local_builder_e2e.py``
     - Yes
     - ``my_lbd_app-project``
     - ``uv``
   * - Full pipeline (build→zip→S3→publish)
     - ``test_deployment_e2e.py``
     - Yes
     - ``my_lbd_app-project``
     - ``uv`` + ``moto``
   * - Local build (private repo)
     - —
     - —
     - ``my_lbd_app_with_private_pkg``
     - ``uv`` + CodeArtifact
   * - Container build (public PyPI)
     - —
     - —
     - ``my_lbd_app-project``
     - ``uv`` + Docker
   * - Container build (private repo)
     - —
     - —
     - ``my_lbd_app_with_private_pkg``
     - ``uv`` + Docker + CodeArtifact
