# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Extension-specific overrides on top of vscode-common-python-lsp.

Only symbols actually consumed by lsp_server.py are exported here.
``is_stdlib_file`` widens the shared-package classification to match
the original broad semantics (any classified Python file, not just stdlib).
"""

from __future__ import annotations

from vscode_common_python_lsp import PythonFileKind, classify_python_file

__all__ = [
    "is_stdlib_file",
]


def is_stdlib_file(file_path: str) -> bool:
    """Return True if the file belongs to a non-user Python path.

    The original implementation included stdlib, system site-packages,
    user site-packages, and extensions dir. Matching that broad semantics.
    """
    return classify_python_file(file_path) is not None
