# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""
Runner to use when running under a different interpreter.
"""

import os
import pathlib
import sys
import traceback

# **********************************************************
# Update sys.path before importing any bundled libraries.
# Always prioritize bundled LSP infrastructure.
# **********************************************************
_bundled_libs = os.fspath(pathlib.Path(__file__).parent.parent / "libs")
if _bundled_libs not in sys.path and os.path.isdir(_bundled_libs):
    sys.path.insert(0, _bundled_libs)


# pylint: disable=wrong-import-position,import-error
import lsp_jsonrpc as jsonrpc
import lsp_utils as utils

RPC = jsonrpc.create_json_rpc(sys.stdin.buffer, sys.stdout.buffer)

EXIT_NOW = False
while not EXIT_NOW:
    msg = RPC.receive_data()

    method = msg["method"]
    if method == "exit":
        EXIT_NOW = True
        continue

    if method == "run":
        is_exception = False  # pylint: disable=invalid-name
        # This is needed to preserve sys.path, pylint modifies
        # sys.path and that might not work for this scenario
        # next time around.
        with utils.substitute_attr(sys, "path", [""] + sys.path[:]):
            try:
                result = utils.run_module(
                    module=msg["module"],
                    argv=msg["argv"],
                    use_stdin=msg["useStdin"],
                    cwd=msg["cwd"],
                    source=msg["source"] if "source" in msg else None,
                )
            except Exception:  # pylint: disable=broad-except
                result = utils.RunResult("", traceback.format_exc(chain=True))
                is_exception = True  # pylint: disable=invalid-name

        response = {"id": msg["id"], "error": result.stderr}
        if is_exception:
            response["exception"] = is_exception
        elif result.stdout:
            response["result"] = result.stdout

        RPC.send_data(response)
