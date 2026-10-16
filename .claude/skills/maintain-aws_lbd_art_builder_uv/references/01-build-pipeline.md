---
description: "How the build code of aws_lbd_art_builder_uv fits together: the module map, what comes from aws_lbd_art_builder_core, the build directory layout, the four-step workflow shared by both builders, the local builder, UvSyncOptions and its three tiers of uv sync flags, validate_artifacts, and the design decisions to keep. Read before changing, fixing, or reviewing code in aws_lbd_art_builder_uv/layer/."
---

# Build Pipeline

## 1. Module map

| File | Role | Covered by `mise run cov`? |
| :--- | :--- | :--- |
| `layer/api.py` | Public surface of the layer subpackage; also re-exports `Credentials`, `LayerPathLayout`, `create_layer_zip_file`, `upload_layer_zip_to_s3`, `LambdaLayerVersionPublisher`, ... from `aws_lbd_art_builder_core` | yes |
| `layer/local_builder.py` | `UvLambdaLayerLocalBuilder`: `uv sync` on the host | yes |
| `layer/container_builder.py` | `UvLambdaLayerContainerBuilder`: `uv sync` inside an AWS SAM image | no, `# pragma: no cover` (needs Docker) |
| `layer/_build_in_container.py` | The script that runs **inside** the container | no, `# pragma: no cover` |
| `layer/uv_sync_options.py` | `UvSyncOptions`, `STRUCTURAL_ARGS`, `STRUCTURAL_REASONS` | yes |
| `layer/validate.py` | `validate_artifacts`: checks the built layer against `pyproject.toml` | yes |
| `paths.py` | `path_enum.path_build_in_container_script` points at `_build_in_container.py` | omitted |

This package only builds. Zipping, uploading, publishing, the path layout, `Credentials`, and the logger all live in `aws_lbd_art_builder_core` (the only runtime dependency). A bug in those belongs upstream; re-export, don't reimplement.

## 2. Build directory layout

`LayerPathLayout` (core) owns these paths. `{git_repo}` is the directory of the `pyproject.toml` passed in.

| Path | What |
| :--- | :--- |
| `{git_repo}/build/lambda/layer/` | Build working directory; deleted and recreated on every run |
| `.../layer/repo/pyproject.toml`, `.../layer/repo/uv.lock` | Copies of the project's files; `uv sync` runs here, never in the project's own `.venv` |
| `.../layer/repo/.venv/lib/pythonX.Y/site-packages/` | Where `uv sync` installs (intermediate) |
| `.../layer/artifacts/python/` | Final layer content, ready to zip |
| `.../layer/build_lambda_layer_in_container.py` | Container builder only: renamed copy of `_build_in_container.py` |
| `.../layer/private-repository-credentials.json` | Container builder only, optional |

## 3. The four-step workflow

Both builders expose `run()` plus `step_1_...` to `step_4_...`, each split into numbered sub-steps (`step_3_2_run_uv_sync`). The steps are public so users can run, inspect, or override them one at a time; keep that granularity when adding work.

| Step | Local builder | Container builder |
| :--- | :--- | :--- |
| 1 Preflight | print build info | print build info, **fail if `uv.lock` is missing** |
| 2 Prepare | clean build dir, copy `pyproject.toml` + `uv.lock` | clean build dir, copy container script, dump credentials JSON (optional), copy `pyproject.toml` + `uv.lock` |
| 3 Execute | `credentials.uv_login()` (optional), then `uv sync` | `docker run` (see `02-container-build.md`) |
| 4 Finalize | move `site-packages` → `artifacts/python/` | same |

The resulting command in both cases is:

```bash
uv sync --no-install-project --link-mode=copy <UvSyncOptions.to_args()>
```

With default options that is `... --frozen --no-dev`.

## 4. The local builder

- No `py_ver_major` / `py_ver_minor`: it always uses the host's Python. Targeting another version needs the container builder.
- `path_bin_uv=None` means "`uv` on `PATH`".
- Credentials are set in **step 3**, not step 2: `uv_login()` sets process-level `UV_INDEX_{NAME}_USERNAME` / `_PASSWORD`, so doing it right before `uv sync` keeps the exposure window short and avoids leaving them set if step 2 fails. `{NAME}` is the index name uppercased with `-` → `_`, and the user's `pyproject.toml` must declare a matching `[[tool.uv.index]]` with `authenticate = "always"`.
- Produces host-native binaries. Fine for pure-Python layers; packages with C extensions need the container builder.

## 5. UvSyncOptions: three tiers of flags

Every `uv sync` flag falls in exactly one tier, decided by one question: what happens if the user gets it wrong?

| Tier | Flags | How |
| :--- | :--- | :--- |
| Structural | `--no-install-project`, `--link-mode=copy` (`STRUCTURAL_ARGS`) | Always added by the builders, never configurable. A wrong value builds a layer that looks fine and fails on Lambda. Each has a reason in `STRUCTURAL_REASONS`, quoted in the error. |
| Managed | `--frozen`, `--no-dev`, `--extra`, `--all-extras`, `--no-extra`, `--group`, `--no-group`, `--all-groups`, `--no-default-groups` | Named, validated dataclass fields; `managed_args` maps each flag to its field. |
| Pass-through | everything else | `extra_args`, verbatim. |

Rules to keep:

- `extra_args` is checked at construction: a structural or managed flag there raises `ValueError` saying why and what to use instead. A silent duplicate would make uv take the last value.
- Conflicts uv would report late (or ignore silently) fail at construction: `extras` with `all_extras`; `no_extras` without `all_extras`.
- `to_args()` never includes `STRUCTURAL_ARGS`. That is what lets the same list be forwarded into the container, which supplies its own copy.
- `managed_args` must cover every flag `to_args()` can emit; `test_managed_args_covers_everything_to_args_emits` checks it.
- Promoting a flag from `extra_args` to a named field (`--python-platform` is the likely first): add the field (one per line inside `# fmt: off`), its `managed_args` entry, its `to_args()` branch, and tests.
- Adding a structural flag is a high bar: only if a wrong value builds an artifact that installs cleanly and fails on Lambda. `--frozen` was evaluated and kept a managed field. A new structural flag must also be added to the literal in `_build_in_container.py`.

## 6. validate_artifacts

Checks that every dependency in `[project].dependencies` (plus the selected `extras` / `all_extras`) has a `.dist-info` in `artifacts/python/`, and with `check_linux=True` that no compiled package carries a non-Linux wheel tag.

- Only **direct** dependencies are checked, deduplicated by name.
- `_find_dist_info` takes the name as everything before the first `-<digit>` of the `.dist-info` stem; a plain `rsplit("-", 1)` breaks on names like `zipp-3.20.2`.
- Wheel tags with platform `any` count as pure Python (`linux=None`), never as a failure.
- It prints a human-readable summary and ends with `assert ok`. It is meant for build scripts and pytest, where an `AssertionError` is the clearest failure; keep it that way rather than adding a custom exception.
- Callers that pass extras to `UvSyncOptions` must pass the same extras here, or the packages those extras pulled in go unchecked.

## 7. Design decisions

| Decision | Why |
| :--- | :--- |
| Build in a copy of `pyproject.toml` + `uv.lock` under `build/lambda/layer/repo/` | Never touches the project's own `.venv`; the build dir can be wiped freely |
| `--no-install-project` is structural | Only the two files are copied, so installing the project would leave an editable pointer to a host path that does not exist on Lambda |
| `--link-mode=copy` is structural | The layer is zipped; symlink targets do not exist on Lambda |
| `--frozen` and `--no-dev` default on, but are fields | Reproducible, minimal layers by default; turning them off is visible in the build log, not silent at runtime |
| Container builder checks `uv.lock` early, local does not | Container builds are slow; a local `uv sync` fails fast anyway |
| Credentials set in step 3 (local) but written in step 2 (container) | Local sets env vars, so keep them next to the command; for the container, writing a file is a prepare action |
| `validate_artifacts` uses `assert` | Designed for build scripts and pytest |
