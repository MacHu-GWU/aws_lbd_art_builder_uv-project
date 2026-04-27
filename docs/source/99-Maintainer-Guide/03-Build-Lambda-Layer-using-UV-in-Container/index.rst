Build Lambda Layer using UV in Container
==============================================================================


Why Build in a Container?
------------------------------------------------------------------------------
When your Lambda function depends on packages with C extensions (e.g. ``numpy``, ``pandas``, ``lxml``), building on macOS or a non-Amazon-Linux host produces binaries that are **incompatible** with the Lambda runtime. A containerized build solves this by running ``uv sync`` inside an official AWS SAM image that matches the Lambda execution environment exactly.

This guide walks through how ``UvLambdaLayerContainerBuilder`` orchestrates a reproducible, container-based Lambda layer build using **uv** as the package manager.


Prerequisites
------------------------------------------------------------------------------
- **Host OS**: macOS or Linux (Windows is NOT supported)
- **Docker**: installed and running
- **uv**: installed on the host (for generating ``uv.lock`` before the build)
- **uv.lock**: already generated and up-to-date (run ``uv lock`` manually if needed)


Container Image
------------------------------------------------------------------------------
We use the official `AWS SAM build images <https://gallery.ecr.aws/sam>`_ from the public ECR registry. These images are built on Amazon Linux and include the same shared libraries available in the Lambda runtime.

Image URI pattern::

    public.ecr.aws/sam/build-python{major}.{minor}:{tag}

For Python 3.12 on x86_64::

    public.ecr.aws/sam/build-python3.12:latest-x86_64

For Python 3.12 on ARM64::

    public.ecr.aws/sam/build-python3.12:latest-arm64

The Docker ``--platform`` flag is set accordingly (``linux/amd64`` or ``linux/arm64``).


Directory Layout and Mount Scheme
------------------------------------------------------------------------------
The builder mounts a single host directory into the container. All file exchange between host and container happens through this mount point.

Let ``{git_repo}`` denote the project's git repository root on the host.

.. list-table::
   :header-rows: 1
   :widths: 55 45

   * - Host Path
     - Container Path
   * - ``{git_repo}/build/lambda/layer``
     - ``/var/task``
   * - ``{git_repo}/build/lambda/layer/build_lambda_layer_in_container.py``
     - ``/var/task/build_lambda_layer_in_container.py``
   * - ``{git_repo}/build/lambda/layer/private-repository-credentials.json``
     - ``/var/task/private-repository-credentials.json``
   * - ``{git_repo}/build/lambda/layer/repo/pyproject.toml``
     - ``/var/task/repo/pyproject.toml``
   * - ``{git_repo}/build/lambda/layer/repo/uv.lock``
     - ``/var/task/repo/uv.lock``
   * - ``{git_repo}/build/lambda/layer/repo/.venv``
     - ``/var/task/repo/.venv``
   * - ``{git_repo}/build/lambda/layer/repo/.venv/lib/python3.12/site-packages``
     - ``/var/task/repo/.venv/lib/python3.12/site-packages``
   * - ``{git_repo}/build/lambda/layer/artifacts/python`` (Layer folder)
     - ``/var/task/artifacts/python`` (Layer folder)

.. note::

   We mount ``build/lambda/layer/`` — not the project root — to ``/var/task``.
   This avoids exposing the host's ``.venv`` or other project files to the container.


Host-Side Workflow (UvLambdaLayerContainerBuilder)
------------------------------------------------------------------------------
The builder runs **four steps** on the host machine. Each step is idempotent and can be inspected independently.


Step 1 — Preflight Check
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Print build configuration (Python version, architecture, paths) and verify that ``uv.lock`` exists in the project root.

This step is **read-only** — it intentionally does NOT run ``uv lock``. Generating or updating the lock file is a state-changing operation that should be done explicitly by the developer before starting a build.


Step 2 — Prepare Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
1. Delete ``{git_repo}/build/lambda/layer/`` to ensure a clean slate.
2. Recreate the directory structure.
3. Copy the following files into the build directory:

   - ``build_lambda_layer_in_container.py`` — the container build script (source: ``_build_in_container.py`` in the package)
   - ``private-repository-credentials.json`` — credentials for private PyPI index (**optional**, skipped if no credentials are configured)
   - ``repo/pyproject.toml`` — copied from the project root
   - ``repo/uv.lock`` — copied from the project root


Step 3 — Execute Build
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Run the Docker container with the mount and execute the build script:

.. code-block:: bash

    docker run --rm \
        --name lambda_layer_builder-python312-amd64 \
        --platform linux/amd64 \
        --mount type=bind,source={git_repo}/build/lambda/layer,target=/var/task \
        public.ecr.aws/sam/build-python3.12:latest-x86_64 \
        python -u /var/task/build_lambda_layer_in_container.py

The container script installs dependencies into ``/var/task/repo/.venv/``. Because the directory is bind-mounted, the installed files are immediately visible on the host after the container exits.


Step 4 — Finalize Artifacts
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Move ``{git_repo}/build/lambda/layer/repo/.venv/lib/python3.12/site-packages`` to ``{git_repo}/build/lambda/layer/artifacts/python/``.

The ``artifacts/python/`` directory is the final Lambda layer content — ready to be zipped and uploaded to AWS.


Container-Side Script (build_lambda_layer_in_container.py)
------------------------------------------------------------------------------
This script runs **inside** the container. It is written in pure Python standard library (3.11+) so it requires no pre-installed third-party packages. The script performs **four steps**:


Step 1 — Verify Container Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Check that the script is running inside the container by verifying ``/var/task/repo`` exists. If not, raise an error — this script must NOT be executed on the host.


Step 2 — Install uv
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Install uv globally inside the container using the official installer:

.. code-block:: bash

    curl -LsSf https://astral.sh/uv/install.sh | sh

After installation, the uv binary is available at ``/root/.local/bin/uv``.


Step 3 — Setup Private Repository Credentials (Optional)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
If ``/var/task/private-repository-credentials.json`` exists, read it and set the corresponding environment variables for uv authentication:

.. code-block:: json

    {
        "index_name": "my-private-pypi",
        "username": "...",
        "password": "..."
    }

The index name is normalized (uppercased, hyphens replaced with underscores) and used to set:

- ``UV_INDEX_MY_PRIVATE_PYPI_USERNAME``
- ``UV_INDEX_MY_PRIVATE_PYPI_PASSWORD``


Step 4 — Run uv sync
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Change directory to ``/var/task/repo`` and execute:

.. code-block:: bash

    /root/.local/bin/uv sync --frozen --no-dev --no-install-project --link-mode=copy

Flag breakdown:

- ``--frozen`` — Use the existing ``uv.lock`` exactly as-is; do not resolve or update.
- ``--no-dev`` — Exclude development dependencies.
- ``--no-install-project`` — Do not install the project itself, only its dependencies.
- ``--link-mode=copy`` — Copy files instead of symlinking, which is required for Lambda layers.

After this step, all dependencies are installed into ``/var/task/repo/.venv/lib/python3.12/site-packages``.


End-to-End Summary
------------------------------------------------------------------------------

.. code-block:: text

    Host                                          Container
    ──────────────────────────────────────────    ──────────────────────────────────
    step_1: check uv.lock exists
    step_2: clean + copy files to build dir
    step_3: docker run ──────────────────────►   1. verify /var/task/repo exists
                                                  2. install uv
                                                  3. setup credentials (optional)
                                                  4. uv sync --frozen ...
            ◄────────────────────────────────    container exits
    step_4: move site-packages → artifacts/python
    ──────────────────────────────────────────    ──────────────────────────────────

    Result: {git_repo}/build/lambda/layer/artifacts/python/
            └── <all dependency packages, ready for Lambda layer>
