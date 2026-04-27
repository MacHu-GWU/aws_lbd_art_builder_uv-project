# -*- coding: utf-8 -*-

"""
Validate Lambda layer artifacts against pyproject.toml dependencies.

Checks that each direct dependency declared in ``pyproject.toml`` is present
in ``artifacts/python/`` and, optionally, that compiled extensions target Linux.
"""

import re
import tomllib
from pathlib import Path


def _normalize(name: str) -> str:
    """
    Normalize a package name for comparison (PEP 503).

    ``My-Package`` → ``my-package``, ``my_package`` → ``my-package``.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def _strip_version_spec(dep: str) -> str:
    """
    Extract the package name from a dependency string.

    ``"boto3>=1.28,<2"`` → ``"boto3"``.
    """
    return re.split(r"[><=!~;\[@ ]", dep, maxsplit=1)[0].strip()


def _find_dist_info(dir_python: Path, name: str) -> Path | None:
    """
    Find the ``.dist-info`` directory for *name* inside *dir_python*.

    Why the regex approach instead of a simple ``rsplit("-", 1)``?
    dist-info directories are named ``{name}-{version}.dist-info``.
    A naive split on the last hyphen breaks for packages whose names
    contain digits that look like version numbers (e.g.
    ``zipp-3.20.2.dist-info`` — ``rsplit("-", 1)`` would give
    ``"zipp-3.20"`` as the name).  The regex ``^(.+?)-\\d`` matches the
    *first* hyphen followed by a digit, which is where the version
    segment always starts.  This correctly extracts ``"zipp"`` from
    ``"zipp-3.20.2"``.
    """
    norm = _normalize(name)
    for p in dir_python.iterdir():
        if not p.name.endswith(".dist-info"):
            continue
        # dist-info dir name format: {name}-{version}.dist-info
        dist_name = p.name.rsplit("-", 1)[0]  # drop version + .dist-info
        # handle: name-version.dist-info  (split on last hyphen may fail for
        # names that contain digits looking like versions, so normalize both)
        # More robust: split off .dist-info, then split name-version
        stem = p.name[: -len(".dist-info")]
        # The name portion is everything before the last hyphen-followed-by-digit
        m = re.match(r"^(.+?)-\d", stem)
        if m:
            dist_name = m.group(1)
        if _normalize(dist_name) == norm:
            return p
    return None


def _read_wheel_tags(dist_info: Path) -> list[str]:
    """
    Read ``Tag:`` lines from the ``WHEEL`` file.
    """
    wheel_file = dist_info / "WHEEL"
    if not wheel_file.exists():
        return []
    tags = []
    for line in wheel_file.read_text().splitlines():
        if line.startswith("Tag:"):
            tags.append(line.split(":", 1)[1].strip())
    return tags


def _is_linux_compatible(tags: list[str]) -> bool | None:
    """
    Determine Linux compatibility from wheel tags.

    Returns ``True`` if tags indicate Linux platform, ``False`` if they
    indicate a non-Linux platform (e.g. macOS), or ``None`` if the package
    is pure Python (``any`` platform — compatible everywhere).
    """
    if not tags:
        return None
    for tag in tags:
        parts = tag.split("-")
        platform = parts[-1] if len(parts) >= 3 else ""
        if platform == "any":
            return None  # pure Python, compatible everywhere
        if "linux" in platform or "manylinux" in platform or "musllinux" in platform:
            return True
    return False


def validate_artifacts(
    dir_python: Path,
    path_pyproject_toml: Path,
    check_linux: bool = False,
) -> dict:
    """
    Validate that ``artifacts/python/`` contains the expected dependencies.

    :param dir_python: Path to the ``artifacts/python/`` directory.
    :param path_pyproject_toml: Path to the project's ``pyproject.toml``.
    :param check_linux: If ``True``, also verify that compiled extensions
        target Linux (useful for container builds).
    :return: A dict with keys ``"ok"`` (bool), ``"packages"`` (list of per-package
        results), and ``"errors"`` (list of error messages).

    Raises :class:`AssertionError` if validation fails, making it easy to
    use in test scripts::

        validate_artifacts(dir_python, path_pyproject_toml, check_linux=True)
    """
    with open(path_pyproject_toml, "rb") as f:
        pyproject = tomllib.load(f)

    deps = pyproject.get("project", {}).get("dependencies", [])
    dep_names = [_strip_version_spec(d) for d in deps]

    packages = []
    errors = []

    for name in dep_names:
        result = {"name": name, "found": False, "tags": [], "linux": None}
        dist_info = _find_dist_info(dir_python, name)

        if dist_info is None:
            result["found"] = False
            errors.append(f"Package '{name}' not found in {dir_python}")
        else:
            result["found"] = True
            tags = _read_wheel_tags(dist_info)
            result["tags"] = tags
            linux_compat = _is_linux_compatible(tags)
            result["linux"] = linux_compat

            if check_linux and linux_compat is False:
                errors.append(
                    f"Package '{name}' has non-Linux platform tags: {tags}"
                )

        packages.append(result)

    ok = len(errors) == 0

    # Print summary directly to stdout so build scripts show human-readable
    # output without requiring a logging framework.  The structured dict is
    # returned for programmatic use; the print block is for operators watching
    # the terminal during a build.
    print("")
    print("+----- Validate Artifacts")
    print("|")
    print(f"|  pyproject.toml: {path_pyproject_toml}")
    print(f"|  artifacts dir:  {dir_python}")
    print(f"|  dependencies:   {len(dep_names)}")
    print("|")
    for pkg in packages:
        status = "OK" if pkg["found"] else "MISSING"
        platform = ""
        if pkg["found"]:
            linux = pkg["linux"]
            if linux is True:
                platform = " [linux]"
            elif linux is False:
                platform = " [non-linux]"
            else:
                platform = " [pure-python]"
        print(f"|  {status:>7s}  {pkg['name']}{platform}")
    print("|")
    if ok:
        print("|  Result: ALL PASSED")
    else:
        print("|  Result: FAILED")
        for err in errors:
            print(f"|    - {err}")
    print("")

    # Why assert instead of raising a custom exception?  This function is
    # designed to be called at the end of build scripts and integration tests.
    # An AssertionError is the natural choice: pytest displays it with a clear
    # message, and in scripts it crashes immediately with a traceback.  A custom
    # exception would need to be imported and caught — unnecessary ceremony
    # for a "build succeeded or didn't" check.  The return value is still
    # available for callers that want to inspect individual package results
    # programmatically (the assert fires first if anything is wrong).
    assert ok, f"Artifact validation failed: {errors}"
    return {"ok": ok, "packages": packages, "errors": errors}
