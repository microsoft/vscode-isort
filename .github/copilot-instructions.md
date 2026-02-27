# Copilot Instructions for vscode-isort

## Architecture

This is a VS Code extension that wraps [isort](https://pycqa.github.io/isort/) for Python import sorting. It's a **dual-language project**: TypeScript for the VS Code client, Python for the LSP server.

- **`src/`** — TypeScript extension client. Entry point: `src/extension.ts`. Common modules in `src/common/` handle settings, server lifecycle, logging, and a fallback code action provider (`sortImports.ts` + `runner.ts`) used when the LSP server is disabled.
- **`bundled/tool/`** — Python LSP server (`lsp_server.py`) built on [pygls](https://github.com/openlawlibrary/pygls). Communicates with the client via stdio. Handles linting (diagnostics via `--check`), code actions (organize imports, quick fix), and formatting. Uses JSON-RPC subprocess calls when the workspace interpreter differs from the server interpreter.
- **`bundled/libs/`** — Bundled Python dependencies (isort, pygls, lsprotocol, etc.), installed via nox.
- **`build/`** — Azure DevOps pipeline definitions and version update scripts.

The extension operates in two modes controlled by the `isort.serverEnabled` setting:
1. **Server mode (default):** TypeScript client starts the Python LSP server as a child process. The server handles all sorting/diagnostics via LSP protocol.
2. **Server-less mode:** TypeScript client runs isort directly via `script_runner.py`, providing code actions and diagnostics without the LSP server.

## Build & Test Commands

### TypeScript (extension client)
```bash
npm run compile          # Webpack build (development)
npm run package          # Webpack build (production, used for publishing)
npm run lint             # ESLint on src/
npm run format-check     # Prettier check on src/**/*.ts and YAML files
npm run compile-tests    # Compile TypeScript tests to out/
npm run tests            # Run TypeScript tests (requires VS Code test infrastructure)
```

### Python (LSP server & tests)
```bash
nox -s tests                  # Run all Python tests (pytest)
nox -s lint                   # Flake8 + black --check + isort --check on Python files
nox -s install_bundled_libs   # Install bundled Python dependencies into bundled/libs/

# Run a single Python test file
pytest src/test/python_tests/test_sort.py

# Run a single Python test by name
pytest src/test/python_tests/test_sort.py -k "test_name"
```

### Packaging
```bash
npm run vsce-package          # Build .vsix for stable release
npm run vsce-package-pre      # Build .vsix for pre-release
```

## Key Conventions

- **Localization:** All user-facing strings use `vscode.l10n.t()`. Display strings in `package.json` use `%key%` placeholders resolved from `package.nls.json` and locale-specific variants (`package.nls.*.json`).
- **Prettier config:** Single quotes, 120 print width, 4-space tabs for TS, 2-space for YAML. Configured in `.prettierrc.js`.
- **Python style:** Black formatting, isort for imports, flake8 for linting. Config in `.flake8` and `pyproject.toml`/`setup.cfg` (if present).
- **Settings resolution:** `src/common/settings.ts` resolves VS Code variables (`${workspaceFolder}`, `${fileDirname}`, `${interpreter}`, `${env:*}`) in user-provided settings arrays. It also handles legacy `python.sortImports.*` settings with deprecation logging.
- **Server info from package.json:** The `serverInfo` field in `package.json` (`{ name, module }`) drives the server ID and module name throughout both the client and server code. Changes there propagate automatically.
- **Copyright header:** All source files start with `// Copyright (c) Microsoft Corporation. All rights reserved.` (TS) or `# Copyright (c) Microsoft Corporation. All rights reserved.` (Python), followed by the MIT license line.
- **Dependency management:** `nox -s update_packages` updates both pip and npm dependencies. Some npm packages are pinned (`vscode-languageclient`, `@types/vscode`, `@types/node`).

## Development Guidelines

- When introducing new functionality, add basic tests following the existing repo test structure.
- Always make sure all tests pass before submitting changes.
- Always ensure documents and code are linted before submitting.
- Do multiple rounds of review and refinement.
- Do not feature creep — keep changes focused on the task at hand.
