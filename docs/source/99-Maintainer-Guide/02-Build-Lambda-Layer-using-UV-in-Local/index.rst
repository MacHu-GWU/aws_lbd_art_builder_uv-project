.. _Build-Lambda-Layer-using-UV-in-Local:

Build Lambda Layer using UV in Local
==============================================================================


When to Use Local Builds
------------------------------------------------------------------------------
Local builds are the fastest way to create a Lambda layer — no Docker required. They work well when your dependencies are **pure Python** (no C extensions). If your layer includes packages with compiled code (e.g. ``numpy``, ``pandas``, ``lxml``), use the containerized builder instead (see :ref:`Build-Lambda-Layer-using-UV-in-Container`).

This guide walks through how ``UvLambdaLayerLocalBuilder`` creates a Lambda layer using **uv** as the package manager directly on the host machine.


Prerequisites
------------------------------------------------------------------------------
- **Host OS**: macOS or Linux (Windows is NOT supported)
- **uv**: installed on the host
- **uv.lock**: already generated and up-to-date (run ``uv lock`` manually if needed)


Directory Layout
------------------------------------------------------------------------------
Let ``{git_repo}`` denote the project's git repository root on the host.

.. list-table::
   :header-rows: 1
   :widths: 55 45

   * - Path
     - Description
   * - ``{git_repo}/pyproject.toml``
     - Project metadata and dependency specification
   * - ``{git_repo}/uv.lock``
     - Locked dependency versions
   * - ``{git_repo}/build/lambda/layer/``
     - Build working directory (cleaned at each run)
   * - ``{git_repo}/build/lambda/layer/repo/pyproject.toml``
     - Copied from project root
   * - ``{git_repo}/build/lambda/layer/repo/uv.lock``
     - Copied from project root
   * - ``{git_repo}/build/lambda/layer/repo/.venv/``
     - Virtual environment created by ``uv sync``
   * - ``{git_repo}/build/lambda/layer/repo/.venv/lib/python3.12/site-packages/``
     - Installed dependencies (intermediate)
   * - ``{git_repo}/build/lambda/layer/artifacts/python/``
     - Final Lambda layer content

.. note::

   The builder copies ``pyproject.toml`` and ``uv.lock`` into ``build/lambda/layer/repo/`` and runs ``uv sync`` there — it does NOT install into the project's own ``.venv``.


Workflow (UvLambdaLayerLocalBuilder)
------------------------------------------------------------------------------
The builder runs **four steps**. Each step is idempotent and can be inspected independently.


Step 1 — Preflight Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Print build configuration (paths, uv binary location).

This step is **read-only** — it does not modify any files.


Step 2 — Prepare Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. Delete ``{git_repo}/build/lambda/layer/`` to ensure a clean slate.
2. Recreate the directory structure.
3. Copy the following files into the build directory:

   - ``repo/pyproject.toml`` — copied from the project root
   - ``repo/uv.lock`` — copied from the project root


Step 3 — Execute Build
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. **Setup credentials** (optional): If a ``Credentials`` object is provided, call ``credentials.uv_login()`` to set ``UV_INDEX_{NAME}_USERNAME`` and ``UV_INDEX_{NAME}_PASSWORD`` environment variables for private repository authentication.

2. **Run uv sync**: Change directory to ``build/lambda/layer/repo/`` and execute:

.. code-block:: bash

    uv sync --frozen --no-dev --no-install-project --link-mode=copy

Flag breakdown:

- ``--frozen`` — Use the existing ``uv.lock`` exactly as-is; do not resolve or update.
- ``--no-dev`` — Exclude development dependencies.
- ``--no-install-project`` — Do not install the project itself, only its dependencies.
- ``--link-mode=copy`` — Copy files instead of symlinking, which is required for Lambda layers.

After this step, all dependencies are installed into ``build/lambda/layer/repo/.venv/lib/python3.12/site-packages/``.


Step 4 — Finalize Artifacts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Move ``{git_repo}/build/lambda/layer/repo/.venv/lib/python3.12/site-packages`` to ``{git_repo}/build/lambda/layer/artifacts/python/``.

The ``artifacts/python/`` directory is the final Lambda layer content — ready to be zipped and uploaded to AWS.


Private Repository Credentials (Optional)
------------------------------------------------------------------------------
To install packages from a private PyPI index (e.g. AWS CodeArtifact), pass a ``Credentials`` object to the builder. The credentials are used to set uv's authentication environment variables.

.. code-block:: python

    from aws_lbd_art_builder_uv.api import layer_api

    credentials = layer_api.Credentials(
        index_name="my-private-pypi",
        index_url="https://my-domain-123456789.d.codeartifact.us-east-1.amazonaws.com/pypi/my-repo/simple/",
        username="aws",
        password="<auth-token>",
    )

The index name is normalized (uppercased, hyphens replaced with underscores) and used to set:

- ``UV_INDEX_MY_PRIVATE_PYPI_USERNAME``
- ``UV_INDEX_MY_PRIVATE_PYPI_PASSWORD``

Your ``pyproject.toml`` must declare the corresponding uv index:

.. code-block:: toml

    [[tool.uv.index]]
    name = "my-private-pypi"
    url = "https://my-domain-123456789.d.codeartifact.us-east-1.amazonaws.com/pypi/my-repo/simple/"
    authenticate = "always"
    explicit = true

    [tool.uv.sources]
    my-private-package = { index = "my-private-pypi" }


Example — Public PyPI Only
------------------------------------------------------------------------------
This example builds a layer for a project that only depends on public packages.

.. code-block:: python

    import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv
    from pathlib import Path

    builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
        path_pyproject_toml=Path("pyproject.toml"),
        skip_prompt=True,
    )

    # Run the workflow in one line
    builder.run()

    # or run step by step
    # builder.step_1_preflight_check()
    # builder.step_2_prepare_environment()
    # builder.step_3_execute_build()
    # builder.step_4_finalize_artifacts()

See ``examples/my_lbd_app-project/example_build_lambda_layer_using_uv_in_local.py`` for a complete working example.


Example — With Private Repository
------------------------------------------------------------------------------
This example builds a layer that includes packages from a private AWS CodeArtifact repository.

.. code-block:: python

    import aws_lbd_art_builder_uv.api as aws_lbd_art_builder_uv
    from pathlib import Path

    credentials = aws_lbd_art_builder_uv.layer_api.Credentials(
        index_name="esc",
        index_url="https://esc-982534387049.d.codeartifact.us-east-1.amazonaws.com/pypi/esc-python/simple/",
        username="aws",
        password="<auth-token-from-codeartifact>",
    )

    builder = aws_lbd_art_builder_uv.layer_api.UvLambdaLayerLocalBuilder(
        path_pyproject_toml=Path("pyproject.toml"),
        credentials=credentials,
        skip_prompt=True,
    )
    builder.run()

See ``examples/my_lbd_app_with_private_pkg/example_build_lambda_layer_using_uv_in_local.py`` and ``examples/my_lbd_app_with_private_pkg/example_settings.py`` for a complete working example with CodeArtifact credential fetching.


End-to-End Summary
------------------------------------------------------------------------------

.. code-block:: text

    step_1: print build info
    step_2: clean + copy pyproject.toml, uv.lock to build dir
    step_3: uv login (optional) + uv sync --frozen ...
    step_4: move site-packages → artifacts/python

    Result: {git_repo}/build/lambda/layer/artifacts/python/
            └── <all dependency packages, ready for Lambda layer>
