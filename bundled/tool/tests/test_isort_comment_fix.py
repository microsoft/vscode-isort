# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Unit tests for isort_comment_fix.repair_comment_placement.

Regression tests for https://github.com/microsoft/vscode-isort/issues/712
("Incorrect pyright comment movement"). These tests run the real isort
engine (not a mock) so they fail loudly if a future isort release changes
the buggy output shape this workaround targets, or fixes the bug upstream
(in which case repair_comment_placement should still be a safe no-op).
"""

from __future__ import annotations

import pathlib
import subprocess
import sys

import pytest

# Ensure bundled/tool is on sys.path so we can import the module directly,
# and run isort with a cwd/config that can't pick up this repo's own
# pyproject.toml (which sets `profile = "black"` and changes wrap
# behavior) -- these tests want to exercise isort's *default* config,
# matching how a typical user project without a profile set would behave.
_TOOL_DIR = str(pathlib.Path(__file__).parent.parent)
if _TOOL_DIR not in sys.path:
    sys.path.insert(0, _TOOL_DIR)

import isort_comment_fix as fix  # noqa: E402


def _run_isort(source: str, tmp_path: pathlib.Path, filename: str = "x.py") -> str:
    """Run the real isort CLI on ``source``, from a directory with no
    isort config of its own, and return its stdout.

    Writes ``source`` to the target path on disk first: isort's config
    resolution behaves differently when the ``--filename`` path doesn't
    physically exist (as it always does for the real extension, which
    only ever runs against a file the editor has open), so tests must
    match that or they won't exercise the same code path.
    """
    target = tmp_path / filename
    target.write_text(source)
    proc = subprocess.run(
        [sys.executable, "-m", "isort", "-", "--filename", str(target)],
        input=source,
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert proc.returncode == 0, proc.stderr
    return proc.stdout


# ---------------------------------------------------------------------------
# The exact case reported in #712
# ---------------------------------------------------------------------------


def test_reported_repro_round_trips_exactly(tmp_path):
    source = (
        "from bpy.props import (  # pyright: ignore[reportMissingModuleSource]\n"
        "    BoolProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    EnumProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    StringProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        ")\n"
    )
    isort_output = _run_isort(source, tmp_path)

    # Sanity check: confirm isort's real output is still the buggy shape
    # this workaround targets. If this assertion starts failing, isort
    # has likely fixed the bug upstream (see module docstring).
    assert "from bpy.props import \\\n" in isort_output

    repaired = fix.repair_comment_placement(source, isort_output)
    assert repaired == source


# ---------------------------------------------------------------------------
# Reordering, surrounding imports, aliases
# ---------------------------------------------------------------------------


def test_reorders_names_and_keeps_surrounding_imports(tmp_path):
    source = (
        "import os\n"
        "\n"
        "from bpy.props import (  # pyright: ignore[reportMissingModuleSource]\n"
        "    StringProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    BoolProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    EnumProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        ")\n"
        "import sys\n"
        "\n"
        "print(os, sys, BoolProperty, EnumProperty, StringProperty)\n"
    )
    isort_output = _run_isort(source, tmp_path)
    assert "from bpy.props import \\\n" in isort_output  # bug still firing

    repaired = fix.repair_comment_placement(source, isort_output)

    assert "import os\nimport sys\n" in repaired
    assert (
        "from bpy.props import (  # pyright: ignore[reportMissingModuleSource]\n"
        "    BoolProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    EnumProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    StringProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        ")\n"
    ) in repaired
    assert "print(os, sys, BoolProperty, EnumProperty, StringProperty)" in repaired
    # No leftover backslash-continuation lines.
    assert "\\\n" not in repaired


def test_aliases_and_mixed_commented_names(tmp_path):
    source = (
        "from bpy.props import (\n"
        "    StringProperty as SP,  # pyright: ignore[reportUnknownVariableType]\n"
        "    BoolProperty,\n"
        "    EnumProperty as EP,  # noqa\n"
        ")\n"
    )
    isort_output = _run_isort(source, tmp_path)
    repaired = fix.repair_comment_placement(source, isort_output)

    assert "BoolProperty," in repaired
    assert "EnumProperty as EP,  # noqa" in repaired
    assert "StringProperty as SP,  # pyright: ignore[reportUnknownVariableType]" in repaired


# ---------------------------------------------------------------------------
# Safety: must be a no-op whenever the bug doesn't apply
# ---------------------------------------------------------------------------


def test_noop_when_no_comments_present(tmp_path):
    source = (
        "import sys\n"
        "import os\n"
        "from collections import (\n"
        "    OrderedDict,\n"
        "    defaultdict,\n"
        ")\n"
    )
    isort_output = _run_isort(source, tmp_path)
    assert fix.repair_comment_placement(source, isort_output) == isort_output


def test_noop_on_non_import_file(tmp_path):
    source = "x = 1\ny = 2\n"
    isort_output = _run_isort(source, tmp_path)
    assert fix.repair_comment_placement(source, isort_output) == isort_output


def test_noop_when_isort_output_unchanged_by_profile(tmp_path):
    # A `profile = "black"` config (this repo's own pyproject.toml is a
    # real example) makes isort wrap differently and doesn't hit the
    # buggy code path -- repair_comment_placement must leave that
    # untouched rather than "fixing" something that wasn't broken.
    (tmp_path / "pyproject.toml").write_text('[tool.isort]\nprofile = "black"\n')
    source = (
        "from bpy.props import (  # pyright: ignore[reportMissingModuleSource]\n"
        "    StringProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    BoolProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    EnumProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        ")\n"
    )
    isort_output = _run_isort(source, tmp_path)
    assert "\\\n" not in isort_output  # confirm the bug didn't fire here
    assert fix.repair_comment_placement(source, isort_output) == isort_output


def test_noop_on_empty_and_trivial_input():
    assert fix.repair_comment_placement("", "") == ""
    assert fix.repair_comment_placement("import os\n", "import os\n") == "import os\n"


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------


def test_idempotent(tmp_path):
    source = (
        "from bpy.props import (  # pyright: ignore[reportMissingModuleSource]\n"
        "    BoolProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    EnumProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        "    StringProperty,  # pyright: ignore[reportUnknownVariableType]\n"
        ")\n"
    )
    isort_output = _run_isort(source, tmp_path)
    repaired_once = fix.repair_comment_placement(source, isort_output)
    isort_output_again = _run_isort(repaired_once, tmp_path)
    repaired_twice = fix.repair_comment_placement(repaired_once, isort_output_again)
    assert repaired_once == repaired_twice
