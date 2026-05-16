# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
"""Implementation of tool support over LSP."""

from __future__ import annotations

import copy
import json
import os
import pathlib
import sys
import traceback
from typing import Any, Dict, List, Optional, Sequence
from urllib.parse import urlparse, urlunparse

# **********************************************************
# Update sys.path before importing any bundled libraries.
# **********************************************************
_extra_sys_paths: list = []


def update_sys_path(path_to_add: str, strategy: str) -> None:
    """Add given path to `sys.path`."""
    if path_to_add not in sys.path and os.path.isdir(path_to_add):
        if strategy == "useBundled":
            sys.path.insert(0, path_to_add)
        elif strategy == "fromEnvironment":
            sys.path.append(path_to_add)


def configure_bundled_sys_path(bundle_dir: pathlib.Path) -> None:
    """Ensure the server's runtime dependencies always come from the bundle."""
    update_sys_path(os.fspath(bundle_dir / "tool"), "useBundled")
    update_sys_path(os.fspath(bundle_dir / "libs"), "useBundled")


# Ensure that we can import LSP libraries, and other bundled libraries.
configure_bundled_sys_path(pathlib.Path(__file__).parent.parent)


# **********************************************************
# Imports needed for the language server goes below this.
# **********************************************************
# pylint: disable=wrong-import-position,import-error
import isort
import lsp_notebook as notebook
import lsp_utils as utils
import lsprotocol.types as lsp
from pygls import uris
from pygls.lsp.server import LanguageServer
from pygls.workspace import TextDocument
from vscode_common_python_lsp import (
    RunResult,
    is_current_interpreter,
    update_environ_path,
)

update_environ_path()

from vscode_common_python_lsp.server import ToolServer, ToolServerConfig

RUNNER = pathlib.Path(__file__).parent / "lsp_runner.py"

MAX_WORKERS = 5

# Create the LSP server with notebook sync, then wrap in ToolServer for
# shared logging, CWD resolution, tool execution, and settings management.
LSP_SERVER = LanguageServer(
    name="isort-server",
    version="v0.1.0",
    max_workers=MAX_WORKERS,
    notebook_document_sync=notebook.NOTEBOOK_SYNC_OPTIONS,
)

ISORT_CONFIG = ToolServerConfig(
    tool_module="isort",
    tool_display="Linter",
    tool_args=[],
    min_version="7.0.0",
    runner_script=str(RUNNER),
    default_notification_level="off",
    default_settings={
        "check": False,
        "severity": {"E": "Hint", "W": "Warning"},
        "extraPaths": [],
    },
)

tool_server = ToolServer(ISORT_CONFIG, server=LSP_SERVER)

# Backward-compatible module-level aliases — tests and other code reference
# these directly.  They are the *same* dict objects owned by tool_server.
WORKSPACE_SETTINGS = tool_server.workspace_settings
GLOBAL_SETTINGS = tool_server.global_settings


def _get_document_path(document: TextDocument) -> str:
    """Returns the filesystem path for a document.

    Examples:
        file:///path/to/file.py -> /path/to/file.py
        vscode-notebook-cell:/path/to/notebook.ipynb#C00001 -> /path/to/notebook.ipynb
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
TOOL_MODULE = ISORT_CONFIG.tool_module
MIN_VERSION = ISORT_CONFIG.min_version

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


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_OPEN)
def notebook_did_open(params: lsp.DidOpenNotebookDocumentParams) -> None:
    """Run diagnostics on each code cell when a notebook is opened."""
    nb = LSP_SERVER.workspace.get_notebook_document(
        notebook_uri=params.notebook_document.uri
    )
    if nb is None:
        return
    for cell in nb.cells:
        if cell.kind != lsp.NotebookCellKind.Code or cell.document is None:
            continue
        document = LSP_SERVER.workspace.get_text_document(cell.document)
        diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
        LSP_SERVER.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
        )


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_CHANGE)
def notebook_did_change(params: lsp.DidChangeNotebookDocumentParams) -> None:
    """Re-lint cells whose text changed or that were newly added."""
    if params.change is None or params.change.cells is None:
        return

    # Lint cells whose text content changed.
    for cell_content in params.change.cells.text_content or []:
        document = LSP_SERVER.workspace.get_text_document(cell_content.document.uri)
        diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
        LSP_SERVER.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
        )

    # Lint newly added cells.
    structure = params.change.cells.structure
    if structure and structure.did_open:
        for cell_doc in structure.did_open:
            document = LSP_SERVER.workspace.get_text_document(cell_doc.uri)
            diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
            LSP_SERVER.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
            )

    # Clear diagnostics for removed cells.
    if structure and structure.did_close:
        for cell_doc in structure.did_close:
            LSP_SERVER.text_document_publish_diagnostics(
                lsp.PublishDiagnosticsParams(uri=cell_doc.uri, diagnostics=[])
            )


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_SAVE)
def notebook_did_save(params: lsp.DidSaveNotebookDocumentParams) -> None:
    """Re-lint all cells when a notebook is saved."""
    nb = LSP_SERVER.workspace.get_notebook_document(
        notebook_uri=params.notebook_document.uri
    )
    if nb is None:
        return
    for cell in nb.cells:
        if cell.kind != lsp.NotebookCellKind.Code or cell.document is None:
            continue
        document = LSP_SERVER.workspace.get_text_document(cell.document)
        diagnostics: list[lsp.Diagnostic] = _linting_helper(document)
        LSP_SERVER.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=document.uri, diagnostics=diagnostics)
        )


@LSP_SERVER.feature(lsp.NOTEBOOK_DOCUMENT_DID_CLOSE)
def notebook_did_close(params: lsp.DidCloseNotebookDocumentParams) -> None:
    """Clear diagnostics for all cells when the notebook is closed."""
    for cell_doc in params.cell_text_documents:
        LSP_SERVER.text_document_publish_diagnostics(
            lsp.PublishDiagnosticsParams(uri=cell_doc.uri, diagnostics=[])
        )


def _linting_helper(document: TextDocument) -> list[lsp.Diagnostic]:
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
    document: TextDocument,
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


def is_interactive(file_path: str) -> bool:
    """Checks if the file path represents interactive window."""
    return file_path.endswith(".interactive")


def _formatting_helper(document: TextDocument) -> list[lsp.TextEdit] | None:
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
    document: TextDocument, results: Optional[List[lsp.TextEdit]]
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


def _match_line_endings(document: TextDocument, text: str) -> str:
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

    tool_server.global_settings.update(
        **params.initialization_options.get("globalSettings", {})
    )

    settings = params.initialization_options["settings"]
    tool_server.update_workspace_settings(settings)

    # Add extra paths to sys.path for in-process module execution
    for p in _extra_sys_paths:
        if p in sys.path:
            sys.path.remove(p)
    _extra_sys_paths.clear()

    import_strategy = os.getenv("LS_IMPORT_STRATEGY", "useBundled")
    setting = tool_server.get_settings_by_path(pathlib.Path(os.getcwd()))
    for extra in setting.get("extraPaths", []):
        if extra not in sys.path:
            update_sys_path(extra, import_strategy)
            if extra in sys.path:
                _extra_sys_paths.append(extra)

    paths = "\r\n   ".join(sys.path)
    log_to_output(f"sys.path used to run Server:\r\n   {paths}")

    log_to_output(
        f"Settings used to run Server:\r\n{json.dumps(settings, indent=4, ensure_ascii=False)}\r\n"
    )
    log_to_output(
        f"Global settings:\r\n{json.dumps(tool_server.global_settings, indent=4, ensure_ascii=False)}\r\n"
    )

    # Log version and config
    _log_info()


@LSP_SERVER.feature(lsp.EXIT)
def on_exit(_params: Optional[Any] = None):
    """Handle clean up on exit."""
    tool_server.handle_exit()


@LSP_SERVER.feature(lsp.SHUTDOWN)
def on_shutdown(_params: Optional[Any] = None):
    """Handle clean up on shutdown."""
    tool_server.handle_shutdown()


def _log_info() -> None:
    for settings in tool_server.workspace_settings.values():
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
# Internal settings management APIs.
# Thin wrappers delegating to ToolServer for backward compatibility.
# *****************************************************
def _get_global_defaults():
    return tool_server.get_global_defaults()


def _get_settings_by_document(document: TextDocument | None):
    return tool_server.get_settings_by_document(document)


# *****************************************************
# Internal execution APIs.
# *****************************************************
def _get_updated_env(settings: Dict[str, Any]) -> Dict[str, str]:
    """Returns environment variables to pass to subprocesses, including extraPaths."""
    extra_paths = settings.get("extraPaths", [])
    paths = os.environ.get("PYTHONPATH", "").split(os.pathsep) + extra_paths
    python_paths = os.pathsep.join([p for p in paths if len(p) > 0])

    env: Dict[str, str] = {
        "LS_IMPORT_STRATEGY": settings["importStrategy"],
    }
    if python_paths:
        env["PYTHONPATH"] = python_paths
    return env


def get_cwd(settings: Dict[str, Any], document: Optional[TextDocument]) -> str:
    """Returns the working directory for running the tool."""
    return tool_server.get_cwd(settings, document)


# pylint: disable=too-many-branches
def _run_tool_on_document(
    document: TextDocument,
    use_stdin: bool = False,
    extra_args: Sequence[str] = [],
) -> RunResult | None:
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

    # deep copy here to prevent accidentally updating global settings.
    settings = copy.deepcopy(_get_settings_by_document(document))

    code_workspace = settings["workspaceFS"]
    cwd = get_cwd(settings, document)

    # Determine execution mode and build argv.
    if settings["path"]:
        # 'path' setting takes priority over everything.
        mode = "path"
        argv = settings["path"]
    elif settings["interpreter"] and not is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use JSON-RPC to the subprocess
        # running under that interpreter.
        mode = "rpc"
        argv = [TOOL_MODULE]
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        mode = "module"
        argv = [TOOL_MODULE]

    if use_stdin:
        # `isort` requires the first argument to be "-" when using stdin.
        argv += ["-"] + ISORT_CONFIG.tool_args + settings["args"] + extra_args
        argv += ["--filename", doc_path]
    else:
        argv += ISORT_CONFIG.tool_args + settings["args"] + extra_args
        argv += [doc_path]

    source = document.source.replace("\r\n", "\n")

    argv = [os.path.dirname(doc_path) if a == "${fileDirname}" else a for a in argv]

    if mode == "module":
        # isort-specific: handle FileSkipComment/FileSkipped exceptions that
        # are raised when isort encounters skip directives.
        try:
            return tool_server.execute_tool(
                argv=argv,
                mode=mode,
                settings=settings,
                use_stdin=use_stdin,
                cwd=cwd,
                workspace=code_workspace,
                source=source,
            )
        except isort.exceptions.FileSkipComment:
            log_warning(f"Skipping file with 'skip_file' comment: {doc_path}")
            return None
        except isort.exceptions.FileSkipped:
            log_warning(traceback.format_exc(chain=True))
            return None

    return tool_server.execute_tool(
        argv=argv,
        mode=mode,
        settings=settings,
        use_stdin=use_stdin,
        cwd=cwd,
        workspace=code_workspace,
        source=source,
        env=_get_updated_env(settings),
    )


def _run_tool(extra_args: Sequence[str], settings: Dict[str, Any]) -> RunResult:
    """Runs tool (e.g. ``--version``).  Delegates to :meth:`ToolServer.execute_tool`."""
    code_workspace = settings["workspaceFS"]
    cwd = get_cwd(settings, None)

    if len(settings["path"]) > 0:
        # 'path' setting takes priority over everything.
        mode = "path"
        argv = settings["path"]
    elif len(settings["interpreter"]) > 0 and not is_current_interpreter(
        settings["interpreter"][0]
    ):
        # If there is a different interpreter set use JSON-RPC to the subprocess
        # running under that interpreter.
        mode = "rpc"
        argv = [TOOL_MODULE]
    else:
        # if the interpreter is same as the interpreter running this
        # process then run as module.
        mode = "module"
        argv = [TOOL_MODULE]

    argv += extra_args

    result = tool_server.execute_tool(
        argv=argv,
        mode=mode,
        settings=settings,
        use_stdin=True,
        cwd=cwd,
        workspace=code_workspace,
        env=_get_updated_env(settings),
    )

    log_to_output(f"\r\n{result.stdout}\r\n")
    return result


# *****************************************************
# Logging and notification.
# Thin wrappers delegating to ToolServer for backward compatibility.
# *****************************************************
def log_to_output(
    message: str, msg_type: lsp.MessageType = lsp.MessageType.Log
) -> None:
    """Logs messages to Output > isort channel only."""
    tool_server.log_to_output(message, msg_type)


def log_error(message: str) -> None:
    """Logs messages with notification on error."""
    tool_server.log_error(message)


def log_warning(message: str) -> None:
    """Logs messages with notification on warning."""
    tool_server.log_warning(message)


def log_always(message: str) -> None:
    """Logs messages with notification."""
    tool_server.log_always(message)


# *****************************************************
# Start the server.
# *****************************************************
if __name__ == "__main__":
    LSP_SERVER.start_io()
