# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Test for stdlib file detection.
"""

import os
import sys
import tempfile
from pathlib import Path

# Add bundled tool to path
bundled_path = Path(__file__).parent.parent.parent.parent / "bundled" / "tool"
sys.path.insert(0, str(bundled_path))

from lsp_utils import is_stdlib_file


def test_stdlib_file_detection():
    """Test that stdlib files are correctly identified."""
    # Test with an actual stdlib file (os module)
    os_file = os.__file__
    assert is_stdlib_file(
        os_file
    ), f"os module file {os_file} should be detected as stdlib"

    # Test with sys module (built-in)
    if hasattr(sys, "__file__"):
        sys_file = sys.__file__
        assert is_stdlib_file(
            sys_file
        ), f"sys module file {sys_file} should be detected as stdlib"


def test_random_file_not_stdlib():
    """Test that random user files are NOT identified as stdlib."""
    # Create a temporary file that's definitely not in stdlib
    with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = is_stdlib_file(tmp_path)
        assert not result, f"Temporary file {tmp_path} should NOT be detected as stdlib"
    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    test_stdlib_file_detection()
    test_random_file_not_stdlib()
    print("All tests passed!")
