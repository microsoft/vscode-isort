# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""

from __future__ import annotations

import ast
import copy
import json
import os
import pathlib
import re
import sys
import traceback
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse, urlunparse


# **********************************************************
# Update sys.path before importing any bundled libraries.
# **********************************************************
def update_sys_path(path_to_add: str, strategy: str) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        if strategy == "useBundled":
            sys.path.insert(0, path_to_add)
        elif strategy == "fromEnvironment":
            sys.path.append(path_to_add)


# Ensure that we can import LSP libraries, and other bundled libraries.
update_sys_path(
    os.fspath(pathlib.Path(__file__).parent.parent / "libs"),
    os.getenv("LS_IMPORT_STRATEGY", "useBundled"),
)

# https://github.com/microsoft/vscode-isort/issues/316#issuecomment-2103588949
update_sys_path(os.fspath(pathlib.Path(__file__).parent.parent / "tool"), "useBundled")

# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
# pylint: disable=wrong-import-position,import-error
import isort
import lsp_jsonrpc as jsonrpc
import lsp_utils as utils
import lsprotocol.types as lsp
from pygls import uris, workspace
from pygls.lsp.server import LanguageServer

WORKSPACE_SETTINGS = {}
GLOBAL_SETTINGS = {}
RUNNER = pathlib.Path(__file__).parent / "lsp_runner.py"

MAX_WORKERS = 5
LSP_SERVER = LanguageServer(
    name="isort-server", version="v0.1.0", max_workers=MAX_WORKERS
)


def _get_document_path(document: workspace.TextDocument) -> str:
    """Returns the filesystem path for a document.

    Examples:
        file:///path/to/file.py -> /path/to/file.py
        vscode-notebook-cell:... -> /path/to/file.py
    """

    if not document.uri.startswith("file:"):
        parsed = urlparse(document.uri)
        file_uri = urlunparse(("file", *parsed[1:-1], ""))
        if result := uris.to_fs_path(file_uri):
            return result
    return document.path


# **********************************************************
# Tool specific code goes below this.
# **********************************************************
TOOL_MODULE = "isort"
TOOL_DISPLAY = "isort"

# Default arguments always passed to isort.
TOOL_ARGS = []

# Minimum version of isort supported.
MIN_VERSION = "7.0.0"

# **********************************************************
# Linting features start here
# **********************************************************


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_OPEN)
def did_open(params: lsp.DidOpenTextDocumentParams) -> None:
    """LSP handler for textDocument/didOpen request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
    )


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_SAVE)
def did_save(params: lsp.DidSaveTextDocumentParams) -> None:
    """LSP handler for textDocument/didSave request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
    )


@LSP_SERVER.feature(lsp.TEXT_DOCUMENT_DID_CLOSE)
def did_close(params: lsp.DidCloseTextDocumentParams) -> None:
    """LSP handler for textDocument/didClose request."""
    document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)
    # Publishing empty diagnostics to clear the entries for this file.
    LSP_SERVER.text_document_publish_diagnostics(
        lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=[])
    )


def _linting_helper(document: workspace.TextDocument) -> list[lsp.Diagnostic]:
    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))

    if not settings.get("check", False):
        # If sorting check is disabled, return empty diagnostics.
        return []

    try:
        result = _run_tool_on_document(document, use_stdin=True, extra_args=["--check"])
        if result and result.stderr:
            return _parse_output(
                document, result.stderr, severity=settings.get("severity", [])
            )
    except Exception:  # pylint: disable=broad-except
        LSP_SERVER.window_log_message(
            lsp.LogMessageParams(
                type=lsp.MessageType.Error,
                message=f"isort check failed with error:\r\n{traceback.format_exc()}",
            )
        )
    return []


def _get_severity(code_type: str, severity: Dict[str, str]) -> lsp.DiagnosticSeverity:
    """Converts severity provided by isort to LSP specific value."""
    value = severity.get(code_type, "Warning")
    try:
        return lsp.DiagnosticSeverity[value]
    except KeyError:
        pass

    return lsp.DiagnosticSeverity.Warning


def _is_sorting_error(line: str) -> bool:
    return (
        line.startswith("ERROR")
        and line.lower().find("imports are incorrectly sorted") > 0
    )


def _parse_output(
    document: workspace.TextDocument,
    output: str,
    severity: Dict[str, str],
) -> Sequence[lsp.Diagnostic]:
    """Parses isort messages and return LSP diagnostic object for each message."""
    diagnostics = []
    has_error = any(
        [_is_sorting_error(line) for line in output.splitlines(keepends=False)]
    )

    if has_error:
        try:
            import_line = [
                i
                for i, l in enumerate(document.lines)
                if l.startswith("import") or l.startswith("from")
            ][0]
        except IndexError:
            import_line = 0

        diagnostics.append(
            lsp.Diagnostic(
                range=lsp.Range(
                    start=lsp.Position(
                        line=import_line,
                        character=0,
                    ),
                    end=lsp.Position(
                        line=import_line + 1,
                        character=0,
                    ),
                ),
                message="Imports are incorrectly sorted and/or formatted.",
                severity=_get_severity("E", severity),
                code="E",
                source="isort",
            )
        )

    return diagnostics


# **********************************************************
# Linting features end here
# **********************************************************

# **********************************************************
# Code Action features start here
# **********************************************************


@LSP_SERVER.feature(
    lsp.TEXT_DOCUMENT_CODE_ACTION,
    lsp.CodeActionOptions(
        code_action_kinds=[
            lsp.CodeActionKind.SourceOrganizeImports,
            lsp.CodeActionKind.QuickFix,
        ],
        resolve_provider=True,
    ),
)
def code_action_organize_imports(params: lsp.CodeActionParams):
    text_document = LSP_SERVER.workspace.get_text_document(params.text_document.uri)

    if utils.is_stdlib_file(_get_document_path(text_document)):
        # Don't format standard library python files.
        # Publishing empty diagnostics clears the entry
        return None

    if (
        params.context.only
        and len(params.context.only) == 1
        and lsp.CodeActionKind.SourceOrganizeImports in params.context.only
    ):
        # This is triggered with users run the Organize Imports command from
        # VS Code. The `context.only` field will have one item that is the
        # `SourceOrganizeImports` code action.
        results = _formatting_helper(text_document)
        if results:
            # Clear out diagnostics, since we are making changes to address
            # import sorting issues.
            LSP_SERVER.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=text_document.uri, diagnostics=[])
            )
            return [
                lsp.CodeAction(
                    title="isort: Organize Imports",
                    kind=lsp.CodeActionKind.SourceOrganizeImports,
                    data=params.text_document.uri,
                    edit=_create_workspace_edits(text_document, results),
                    diagnostics=[],
                )
            ]

    actions = []
    if (
        not params.context.only
        or lsp.CodeActionKind.SourceOrganizeImports in params.context.only
    ):
        actions.append(
            lsp.CodeAction(
                title="isort: Organize Imports",
                kind=lsp.CodeActionKind.SourceOrganizeImports,
                data=params.text_document.uri,
                edit=None,
                diagnostics=[],
            ),
        )

    if not params.context.only or lsp.CodeActionKind.QuickFix in params.context.only:
        diagnostics = [
            d
            for d in params.context.diagnostics
            if d.source == "isort" and d.code == "E"
        ]
        if diagnostics:
            actions.append(
                lsp.CodeAction(
                    title="isort: Fix import sorting and/or formatting",
                    kind=lsp.CodeActionKind.QuickFix,
                    data=params.text_document.uri,
                    edit=None,
                    diagnostics=diagnostics,
                ),
            )

    return actions if actions else None


@LSP_SERVER.feature(lsp.CODE_ACTION_RESOLVE)
def code_action_resolve(params: lsp.CodeAction):
    text_document = LSP_SERVER.workspace.get_text_document(params.data)

    results = _formatting_helper(text_document)
    if results:
        # Clear out diagnostics, since we are making changes to address
        # import sorting issues.
        LSP_SERVER.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=text_document.uri, diagnostics=[])
        )
    else:
        # There are no changes so return the original code as is.
        # This could be due to error while running import sorter
        # so, don't clear out the diagnostics.
        results = [
            lsp.TextEdit(
                range=lsp.Range(
                    start=lsp.Position(line=0, character=0),
                    end=lsp.Position(line=len(text_document.lines), character=0),
                ),
                new_text=text_document.source,
            )
        ]

    params.edit = _create_workspace_edits(text_document, results)
    return params


# Matches Jupyter/IPython magic commands and shell escapes:
#   %matplotlib inline   - line magic
#   %%time               - cell magic
#   !pip install foo     - shell escape
MAGIC_COMMAND_REGEX = re.compile(r"^\s*(%{1,2}\w|!)")


def strip_magic_commands(source: str) -> str:
    """Strips magic commands from the source code."""
    lines = source.splitlines(keepends=True)
    new_lines = ["\n" if MAGIC_COMMAND_REGEX.match(line) else line for line in lines]
    return "".join(new_lines)


def is_python(code: str) -> bool:
    """Ensures that the code provided is python."""
    code = strip_magic_commands(code)
    try:
        ast.parse(code)
    except SyntaxError:
        log_error(f"Syntax error in code: {traceback.format_exc()}")
        return False
    return True


def is_interactive(file_path: str) -> bool:
    """Checks if the file path represents interactive window."""
    return file_path.endswith(".interactive")


def _formatting_helper(document: workspace.TextDocument) -> list[lsp.TextEdit] | None:
    result = _run_tool_on_document(document, use_stdin=True)
    if result and result.stdout:
        new_source = _match_line_endings(document, result.stdout)

        # Skip last line ending in a notebook cell
        if document.uri.startswith("vscode-notebook-cell"):
            if new_source.endswith("\r\n"):
                new_source = new_source[:-2]
            elif new_source.endswith("\n"):
                new_source = new_source[:-1]

        if new_source != document.source:
            return [
                lsp.TextEdit(
                    range=lsp.Range(
                        start=lsp.Position(line=0, character=0),
                        end=lsp.Position(line=len(document.lines), character=0),
                    ),
                    new_text=new_source,
                )
            ]
    return None


def _create_workspace_edits(
    document: workspace.TextDocument, results: Optional[List[lsp.TextEdit]]
):
    return lsp.WorkspaceEdit(
        document_changes=[
            lsp.TextDocumentEdit(
                text_document=lsp.VersionedTextDocumentIdentifier(
                    uri=document.uri,
                    version=0 if document.version is None else document.version,
                ),
                edits=results,
            )
        ],
    )


def _get_line_endings(lines: list[str]) -> str:
    """Returns line endings used in the text."""
    try:
        if lines[0][-2:] == "\r\n":
            return "\r\n"
        return "\n"
    except Exception:  # pylint: disable=broad-except
        return None


def _match_line_endings(document: workspace.TextDocument, text: str) -> str:
    """Ensures that the edited text line endings matches the document line endings."""
    expected = _get_line_endings(document.source.splitlines(keepends=True))
    actual = _get_line_endings(text.splitlines(keepends=True))
    if actual == expected or actual is None or expected is None:
        return text
    return text.replace(actual, expected)


# **********************************************************
# Code Action features ends here
# **********************************************************


# **********************************************************
# Required Language Server Initialization and Exit handlers.
# **********************************************************
@LSP_SERVER.feature(lsp.INITIALIZE)
def initialize(params: lsp.InitializeParams) -> None:
    """LSP handler for initialize request."""
    log_to_output(f"CWD Server: {os.getcwd()}")

    paths = "\r\n   ".join(sys.path)
    log_to_output(f"sys.path used to run Server:\r\n   {paths}")

    GLOBAL_SETTINGS.update(**params.initialization_options.get("globalSettings", {}))

    settings = params.initialization_options["settings"]
    _update_workspace_settings(settings)
    log_to_output(
        f"Settings used to run Server:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )
    log_to_output(
        f"Global settings:\r\n{json.dumps(GLOBAL_SETTINGS, indent=4, ensure_ascii=False)}\r\n"
    )

    # Log version and config
    _log_info()


@LSP_SERVER.feature(lsp.EXIT)
def on_exit(_params: Optional[Any] = None):
    """Handle clean up on exit."""
    jsonrpc.shutdown_json_rpc()


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None):
    """Handle clean up on exit."""
    jsonrpc.shutdown_json_rpc()


def _log_info() -> None:
    for settings in WORKSPACE_SETTINGS.values():
        _log_version_info(settings)
        _log_verbose_config(settings)


def _log_version_info(settings: Dict[str, str]) -> None:
    try:
        from packaging.version import parse as parse_version

        settings = copy.deepcopy(settings)
        result = _run_tool(["--version-number"], settings)
        code_workspace = settings["workspaceFS"]

        if result and result.stdout:
            log_to_output(
                f"Version info for isort running for {code_workspace}:\r\n{result.stdout}"
            )
            # This is text we get from running `isort --version-number`
            # 5.10.1
            actual_version = result.stdout.strip()

            version = parse_version(actual_version)
            min_version = parse_version(MIN_VERSION)

            if version < min_version:
                log_error(
                    f"Version of isort running for {code_workspace} is NOT supported:\r\n"
                    f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                    f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
                )
            else:
                log_to_output(
                    f"SUPPORTED {TOOL_MODULE}>={min_version}\r\n"
                    f"FOUND {TOOL_MODULE}=={actual_version}\r\n"
                )
    except:  # pylint: disable=bare-except
        log_to_output(
            f"Error while detecting isort version:\r\n{traceback.format_exc()}"
        )


def _log_verbose_config(settings: Dict[str, str]) -> None:
    if LSP_SERVER.protocol.trace == lsp.TraceValue.Verbose:
        try:
            settings = copy.deepcopy(settings)
            result = _run_tool(["--show-config"], settings)
            code_workspace = settings["workspaceFS"]
            log_to_output(
                f"Config details for isort running for {code_workspace}:\r\n{result.stdout}"
            )
        except:  # pylint: disable=bare-except
            log_to_output(
                f"Error while getting `isort --show-config` config:\r\n{traceback.format_exc()}"
            )


# *****************************************************
# Internal functional and settings management APIs.
# *****************************************************
def _get_global_defaults():
    return {
        "check": GLOBAL_SETTINGS.get("check", False),
        "path": GLOBAL_SETTINGS.get("path", []),
        "severity": GLOBAL_SETTINGS.get("severity", {"E": "Hint", "W": "Warning"}),
        "interpreter": GLOBAL_SETTINGS.get("interpreter", [sys.executable]),
        "args": GLOBAL_SETTINGS.get("args", []),
        "importStrategy": GLOBAL_SETTINGS.get("importStrategy", "useBundled"),
        "showNotifications": GLOBAL_SETTINGS.get("showNotifications", "off"),
    }


def _update_workspace_settings(settings):
    if not settings:
        key = utils.normalize_path(os.getcwd())
        WORKSPACE_SETTINGS[key] = {
            "cwd": key,
            "workspaceFS": key,
            "workspace": uris.from_fs_path(key),
            **_get_global_defaults(),
        }
        return

    for setting in settings:
        key = utils.normalize_path(uris.to_fs_path(setting["workspace"]))
        WORKSPACE_SETTINGS[key] = {
            **setting,
            "workspaceFS": key,
        }


def _get_settings_by_path(file_path: pathlib.Path):
    workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

    while file_path != file_path.parent:
        str_file_path = utils.normalize_path(file_path)
        if str_file_path in workspaces:
            return WORKSPACE_SETTINGS[str_file_path]
        file_path = file_path.parent

    setting_values = list(WORKSPACE_SETTINGS.values())
    return setting_values[0]


def _get_document_key(document: workspace.TextDocument):
    if WORKSPACE_SETTINGS:
        document_workspace = pathlib.Path(_get_document_path(document))
        workspaces = {s["workspaceFS"] for s in WORKSPACE_SETTINGS.values()}

        # Find workspace settings for the given file.
        while document_workspace != document_workspace.parent:
            norm_path = utils.normalize_path(document_workspace)
            if norm_path in workspaces:
                return norm_path
            document_workspace = document_workspace.parent

    return None


def _get_settings_by_document(document: workspace.TextDocument | None):
    if document is None or document.path is None:
        return list(WORKSPACE_SETTINGS.values())[0]

    key = _get_document_key(document)
    if key is None:
        # This is either a non-workspace file or there is no workspace.
        key = utils.normalize_path(pathlib.Path(_get_document_path(document)).parent)
        return {
            "cwd": key,
            "workspaceFS": key,
            "workspace": uris.from_fs_path(key),
            **_get_global_defaults(),
        }

    return WORKSPACE_SETTINGS[str(key)]


# *****************************************************
# Internal execution APIs.
# *****************************************************
def get_cwd(
    settings: Dict[str, Any], document: Optional[workspace.TextDocument]
) -> str:
    """Returns the working directory for running the tool.

    Resolves the following VS Code file-related variable substitutions when
    a document is available:

    - ``${file}`` – absolute path of the current document.
    - ``${fileBasename}`` – file name with extension (e.g. ``foo.py``).
    - ``${fileBasenameNoExtension}`` – file name without extension (e.g. ``foo``).
    - ``${fileExtname}`` – file extension including the dot (e.g. ``.py``).
    - ``${fileDirname}`` – directory containing the current document.
    - ``${fileDirnameBasename}`` – name of the directory containing the document.
    - ``${relativeFile}`` – document path relative to the workspace root.
    - ``${relativeFileDirname}`` – document directory relative to the workspace root.
    - ``${fileWorkspaceFolder}`` – workspace root folder for the document.

    Variables that do not depend on the document (``${workspaceFolder}``,
    ``${userHome}``, ``${cwd}``) are pre-resolved by the TypeScript client.

    If no document is available and the value contains any unresolvable
    file-variable, the workspace root is returned as a fallback.
    """
    cwd = settings.get("cwd", settings["workspaceFS"])

    workspace_fs = settings["workspaceFS"]

    if document is not None:
        file_path = _get_document_path(document)
        file_dir = os.path.dirname(file_path)
        file_basename = os.path.basename(file_path)
        file_stem, file_ext = os.path.splitext(file_basename)

        substitutions = {
            "${file}": file_path,
            "${fileBasename}": file_basename,
            "${fileBasenameNoExtension}": file_stem,
            "${fileExtname}": file_ext,
            "${fileDirname}": file_dir,
            "${fileDirnameBasename}": os.path.basename(file_dir),
            "${relativeFile}": os.path.relpath(file_path, workspace_fs),
            "${relativeFileDirname}": os.path.relpath(file_dir, workspace_fs),
            "${fileWorkspaceFolder}": workspace_fs,
        }

        for token, value in substitutions.items():
            cwd = cwd.replace(token, value)
    else:
        # Without a document we cannot resolve file-related variables.
        # Fall back to workspace root if any remain.
        if "${file" in cwd or "${relativeFile" in cwd:
            cwd = workspace_fs

    return cwd


# pylint: disable=too-many-branches
def _run_tool_on_document(
    document: workspace.TextDocument,
    use_stdin: bool = False,
    extra_args: Sequence[str] = [],
) -> utils.RunResult | None:
    """Runs tool on the given document.

    if use_stdin is true then contents of the document is passed to the
    tool via stdin.
    """
    doc_path = _get_document_path(document)
    if utils.is_stdlib_file(doc_path):
        log_warning(f"Skipping standard library file: {doc_path}")
        return None

    if is_interactive(doc_path):
        log_warning(f"Skipping interactive window: {doc_path}")
        return None

    if not is_python(document.source):
        log_warning(f"Skipping non python code: {doc_path}")
        return None

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))

    code_workspace = settings["workspaceFS"]
    cwd = get_cwd(settings, document)

    use_path = False
    use_rpc = False
    if settings["path"]:
        # 'path' setting takes priority over everything.
        use_path = True
        argv = settings["path"]
    elif settings["interpreter"] and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use JSON-RPC to the subprocess
        # running under that interpreter.
        argv = [TOOL_MODULE]
        use_rpc = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [TOOL_MODULE]

    if use_stdin:
        # `isort` requires the first argument to be "-" when using stdin.
        argv += ["-"] + TOOL_ARGS + settings["args"] + extra_args
        argv += ["--filename", doc_path]
    else:
        argv += TOOL_ARGS + settings["args"] + extra_args
        argv += [doc_path]

    source = document.source.replace("\r\n", "\n")

    argv = [os.path.dirname(doc_path) if a == "${fileDirname}" else a for a in argv]

    if use_path:
        # This mode is used when running executables.
        log_to_output(" ".join(argv))
        log_to_output(f"CWD Server: {cwd}")
        result = utils.run_path(
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=source,
        )
        if result.stderr:
            log_to_output(result.stderr)
    elif use_rpc:
        # This mode is used if the interpreter running this server is different from
        # the interpreter used for running this server.
        log_to_output(" ".join(settings["interpreter"] + ["-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")

        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=use_stdin,
            cwd=cwd,
            source=source,
            env={
                "LS_IMPORT_STRATEGY": settings["importStrategy"],
            },
        )
        result = _to_run_result_with_logging(result)
    else:
        # In this mode the tool is run as a module in the same process as the language server.
        log_to_output(" ".join([sys.executable, "-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")

        try:
            result = utils.run_module(
                module=TOOL_MODULE,
                argv=argv,
                use_stdin=use_stdin,
                cwd=cwd,
                source=source,
            )
        except isort.exceptions.FileSkipComment:
            log_warning(f"Skipping file with 'skip_file' comment: {doc_path}")
            return None
        except isort.exceptions.FileSkipped:
            log_warning(traceback.format_exc(chain=True))
            return None
        except Exception:
            log_error(traceback.format_exc(chain=True))
            raise
        if result.stderr:
            log_to_output(result.stderr)

    return result


def _run_tool(extra_args: Sequence[str], settings: Dict[str, Any]) -> utils.RunResult:
    """Runs tool."""
    code_workspace = settings["workspaceFS"]
    cwd = get_cwd(settings, None)

    use_path = False
    use_rpc = False
    if len(settings["path"]) > 0:
        # 'path' setting takes priority over everything.
        use_path = True
        argv = settings["path"]
    elif len(settings["interpreter"]) > 0 and not utils.is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use JSON-RPC to the subprocess
        # running under that interpreter.
        argv = [TOOL_MODULE]
        use_rpc = True
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        argv = [TOOL_MODULE]

    argv += extra_args

    if use_path:
        # This mode is used when running executables.
        log_to_output(" ".join(argv))
        log_to_output(f"CWD Server: {cwd}")
        result = utils.run_path(argv=argv, use_stdin=True, cwd=cwd)
        if result.stderr:
            log_to_output(result.stderr)
    elif use_rpc:
        # This mode is used if the interpreter running this server is different from
        # the interpreter used for running this server.
        log_to_output(" ".join(settings["interpreter"] + ["-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")
        result = jsonrpc.run_over_json_rpc(
            workspace=code_workspace,
            interpreter=settings["interpreter"],
            module=TOOL_MODULE,
            argv=argv,
            use_stdin=True,
            cwd=cwd,
            env={
                "LS_IMPORT_STRATEGY": settings["importStrategy"],
            },
        )
        result = _to_run_result_with_logging(result)
    else:
        # In this mode the tool is run as a module in the same process as the language server.
        log_to_output(" ".join([sys.executable, "-m"] + argv))
        log_to_output(f"CWD Linter: {cwd}")
        # This is needed to preserve sys.path, in cases where the tool modifies
        # sys.path and that might not work for this scenario next time around.
        with utils.substitute_attr(sys, "path", [""] + sys.path[:]):
            try:
                result = utils.run_module(
                    module=TOOL_MODULE, argv=argv, use_stdin=True, cwd=cwd
                )
            except Exception:
                log_error(traceback.format_exc(chain=True))
                raise
        if result.stderr:
            log_to_output(result.stderr)

    return result


def _to_run_result_with_logging(rpc_result: jsonrpc.RpcRunResult) -> utils.RunResult:
    error = ""
    if rpc_result.exception:
        log_error(rpc_result.exception)
        error = rpc_result.exception
    elif rpc_result.stderr:
        log_to_output(rpc_result.stderr)
        error = rpc_result.stderr
    return utils.RunResult(rpc_result.stdout, error)


# *****************************************************
# Logging and notification.
# *****************************************************
def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    """Logs messages to Output > Pylint channel only."""
    LSP_SERVER.window_log_message(lsp.LogMessageParams(type=msg_type, message=message))


def log_error(message: str) -> None:
    """Logs messages with notification on error."""
    LSP_SERVER.window_log_message(
        lsp.LogMessageParams(type=lsp.MessageType.Error, message=message)
    )
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["onError", "onWarning", "always"]:
        LSP_SERVER.window_show_message(
            lsp.ShowMessageParams(type=lsp.MessageType.Error, message=message)
        )


def log_warning(message: str) -> None:
    """Logs messages with notification on warning."""
    LSP_SERVER.window_log_message(
        lsp.LogMessageParams(type=lsp.MessageType.Warning, message=message)
    )
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["onWarning", "always"]:
        LSP_SERVER.window_show_message(
            lsp.ShowMessageParams(type=lsp.MessageType.Warning, message=message)
        )


def log_always(message: str) -> None:
    """Logs messages with notification."""
    LSP_SERVER.window_log_message(
        lsp.LogMessageParams(type=lsp.MessageType.Info, message=message)
    )
    if os.getenv("LS_SHOW_NOTIFICATION", "off") in ["always"]:
        LSP_SERVER.window_show_message(
            lsp.ShowMessageParams(type=lsp.MessageType.Info, message=message)
        )


# *****************************************************
# Start the server.
# *****************************************************
if __name__ == "__main__":
    LSP_SERVER.start_io()
