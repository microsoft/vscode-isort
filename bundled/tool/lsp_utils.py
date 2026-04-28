# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Utility functions and classes for use with running tools over LSP.

Thin wrapper: delegates to vscode-common-python-lsp shared package,
providing backward-compatible names used by lsp_server.py.
"""

from __future__ import annotations

from vscode_common_python_lsp import (
    CWD_LOCK,
    SERVER_CWD,
    CustomIO,
    PythonFileKind,
    QuickFixRegistrationError,
    RunResult,
    as_list,
    change_cwd,
    classify_python_file,
    is_current_interpreter,
    is_match,
    is_same_path,
    normalize_path,
    redirect_io,
    run_api,
    run_module,
    run_path,
    substitute_attr,
)

__all__ = [
    "SERVER_CWD",
    "CWD_LOCK",
    "as_list",
    "normalize_path",
    "is_same_path",
    "is_current_interpreter",
    "is_user_site_packages_file",
    "is_system_site_packages_file",
    "is_stdlib_file",
    "is_match",
    "RunResult",
    "CustomIO",
    "substitute_attr",
    "redirect_io",
    "change_cwd",
    "run_module",
    "run_path",
    "run_api",
    "QuickFixRegistrationError",
]


# Compatibility wrappers: the shared package uses classify_python_file()
# returning a PythonFileKind enum; these preserve the old per-kind API.


def is_user_site_packages_file(file_path: str) -> bool:
    """Return True if the file belongs to the user site-packages directory."""
    return classify_python_file(file_path) == PythonFileKind.USER_SITE


def is_system_site_packages_file(file_path: str) -> bool:
    """Return True if the file belongs to system site-packages directories."""
    return classify_python_file(file_path) == PythonFileKind.SYSTEM_SITE


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to the standard library."""
    return classify_python_file(file_path) == PythonFileKind.STDLIB
