# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Workaround for an isort bug where re-wrapping a parenthesized
multi-import block whose individual names carry trailing inline comments
(e.g. ``# pyright: ignore[...]``) causes isort to split the block into
several single-name backslash-continuation lines and relocate the comment
that was attached to the *opening* ``from X import (`` line onto the
*last* individual import, semicolon-joined with that import's own
comment.

Example (isort 8.0.1, zero config)::

    # input
    from bpy.props import (  # pyright: ignore[reportMissingModuleSource]
        BoolProperty,  # pyright: ignore[reportUnknownVariableType]
        EnumProperty,  # pyright: ignore[reportUnknownVariableType]
        StringProperty,  # pyright: ignore[reportUnknownVariableType]
    )

    # isort's output (wrong)
    from bpy.props import \\
        BoolProperty  # pyright: ignore[reportUnknownVariableType]
    from bpy.props import \\
        EnumProperty  # pyright: ignore[reportUnknownVariableType]
    from bpy.props import \\
        StringProperty  # pyright: ignore[reportMissingModuleSource]; pyright: ignore[reportUnknownVariableType]

``repair_comment_placement`` detects this exact output shape and rewrites
it back into a parenthesized block with each name's original comment
restored to that same name, and the header comment restored to the
opening ``(`` line. The corrected name *order* is always taken from
isort's own output (that part isn't broken -- only comment placement is),
so this never second-guesses a real sorting decision isort made.

This is a workaround for an upstream isort defect, not a full fix -- see
https://github.com/microsoft/vscode-isort/issues/712 for the report and
root-cause discussion.
"""

from __future__ import annotations

import re
from typing import Dict, List, Optional

# A parenthesized multi-import block in the *original* (pre-isort) source,
# e.g.:
#     from bpy.props import (  # header comment
#         BoolProperty,  # comment
#         EnumProperty,  # comment
#     )
_BLOCK_RE = re.compile(
    r"^from[ \t]+(?P<module>[\w.]+)[ \t]+import[ \t]*\([ \t]*"
    r"(?P<header_comment>#[^\n]*)?\n"
    r"(?P<body>(?:[ \t]+.+\n)+?)"
    r"\)[ \t]*\n",
    re.MULTILINE,
)

# One imported name line inside a block body, e.g.:
#     "    StringProperty,  # pyright: ignore[reportUnknownVariableType]"
#     "    Foo as Bar,"
_NAME_LINE_RE = re.compile(
    r"^[ \t]+(?P<name>\w+)"
    r"(?:[ \t]+as[ \t]+(?P<alias>\w+))?"
    r"[ \t]*,?[ \t]*"
    r"(?P<comment>#[^\n]*)?[ \t]*\n?$"
)

# One "unit" of isort's buggy split output. isort produces either shape
# depending on whether that particular name+comment fits the line length:
#     from MODULE import \
#         NAME[ as ALIAS]  [# comment]
# or, when it fits on one line:
#     from MODULE import NAME[ as ALIAS]  [# comment]
# A run can mix both shapes for different names from the same original
# block, so both must be recognized as the same kind of "unit".
_BUGGY_UNIT_RE = re.compile(
    r"^from[ \t]+(?P<module>[\w.]+)[ \t]+import[ \t]*"
    r"(?:\\\n[ \t]+(?P<full_wrapped>\w+(?:[ \t]+as[ \t]+\w+)?)"
    r"|(?P<full_plain>\w+(?:[ \t]+as[ \t]+\w+)?))"
    r"[ \t]*(?:#[^\n]*)?\n",
    re.MULTILINE,
)


def _normalize(full: str) -> str:
    return re.sub(r"\s+", " ", full.strip())


class _CommentBlock:
    __slots__ = ("module", "header_comment", "names")

    def __init__(self, module: str, header_comment: Optional[str], names: Dict[str, str]):
        self.module = module
        self.header_comment = header_comment
        self.names = names  # normalized "name" or "name as alias" -> comment or None


def _extract_comment_blocks(source: str) -> Dict[str, List[_CommentBlock]]:
    """Find parenthesized multi-import blocks in ``source`` that have at
    least one trailing inline comment (on a name, or on the opening ``(``
    line) -- i.e. blocks isort's bug can affect. Returns module -> list of
    blocks, in the order they appear in the source."""
    blocks: Dict[str, List[_CommentBlock]] = {}
    for m in _BLOCK_RE.finditer(source):
        body = m.group("body")
        names: Dict[str, str] = {}
        ok = True
        for line in body.splitlines(keepends=True):
            if not line.strip():
                continue
            nm = _NAME_LINE_RE.match(line)
            if not nm:
                # Doesn't match our simple one-name-per-line assumption
                # (e.g. multiple names crammed onto one line) -- skip this
                # block entirely rather than guess.
                ok = False
                break
            full = nm.group("name")
            if nm.group("alias"):
                full = f"{full} as {nm.group('alias')}"
            names[_normalize(full)] = nm.group("comment")
        if not ok:
            continue

        header_comment = m.group("header_comment")
        if not header_comment and not any(names.values()):
            continue  # no comments anywhere -> isort's bug doesn't apply

        blocks.setdefault(m.group("module"), []).append(
            _CommentBlock(m.group("module"), header_comment, names)
        )
    return blocks


def repair_comment_placement(original_source: str, isort_output: str) -> str:
    """Return ``isort_output`` with any comment-misplacement caused by the
    isort bug described in the module docstring corrected, by
    cross-referencing the original (pre-isort) source.

    Safe to call unconditionally: if nothing in ``original_source`` could
    have triggered the bug, or the buggy output shape isn't found,
    ``isort_output`` is returned unchanged.
    """
    if "#" not in original_source:
        # Fast path: the bug can only fire when the original source had a
        # comment somewhere (on a name or the opening "(" line).
        return isort_output

    orig = original_source.replace("\r\n", "\n")
    out = isort_output.replace("\r\n", "\n")

    blocks_by_module = _extract_comment_blocks(orig)
    if not blocks_by_module:
        return isort_output

    units = list(_BUGGY_UNIT_RE.finditer(out))
    if not units:
        return isort_output

    # Group consecutive (no gap, same module) units into runs -- isort
    # emits each split-out name back-to-back for the same original block.
    runs = []
    i = 0
    while i < len(units):
        j = i + 1
        module = units[i].group("module")
        while (
            j < len(units)
            and units[j].group("module") == module
            and units[j].start() == units[j - 1].end()
        ):
            j += 1
        runs.append((module, units[i], units[j - 1]))
        i = j

    # Track how many blocks-per-module we've already consumed, so multiple
    # occurrences of the same module are matched in source order.
    consumed = {module: 0 for module in blocks_by_module}

    # Apply fixes back-to-front so earlier string offsets stay valid.
    for module, first, last in reversed(runs):
        candidates = blocks_by_module.get(module)
        if not candidates:
            continue
        idx = consumed[module]
        if idx >= len(candidates):
            continue

        run_text = out[first.start() : last.end()]
        names_in_order = [
            _normalize(um.group("full_wrapped") or um.group("full_plain"))
            for um in _BUGGY_UNIT_RE.finditer(run_text)
        ]

        block = candidates[idx]
        if set(names_in_order) != set(block.names.keys()):
            # Not a match for this block (e.g. isort merged in an
            # unrelated same-module import) -- don't guess, leave alone.
            continue
        consumed[module] += 1

        lines = [f"from {module} import ("]
        if block.header_comment:
            lines[0] += f"  {block.header_comment}"
        lines[0] += "\n"
        for full in names_in_order:
            line = f"    {full},"
            comment = block.names.get(full)
            if comment:
                line += f"  {comment}"
            lines.append(line + "\n")
        lines.append(")\n")

        out = out[: first.start()] + "".join(lines) + out[last.end() :]

    # Line-ending normalization back to the document's original style is
    # already handled by the caller (_match_line_endings), so we return
    # \n-normalized text here just like isort's own stdout.
    return out
