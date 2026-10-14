# Import sorting extension for Visual Studio Code using isort

A Visual Studio Code extension that provides import sorting for Python projects using isort. The extension uses the Language Server Protocol ([LSP](https://microsoft.github.io/language-server-protocol/)) to run `isort` in a server-like mode.

This extension ships with `isort=9.0.1`.

> **Note**: The minimum version of isort this extension supports is `8.0.1`. If you have any issues sorting imports with isort, please report it to [this issue tracker](https://github.com/PyCQA/isort/issues) as this extension is just a wrapper around isort.

This extension supports all [actively supported versions](https://devguide.python.org/#status-of-python-branches) of the Python language.

For more information on isort, see https://pycqa.github.io/isort/


## Usage and Features

The isort extension provides a series of import sorting features to help with readability of your Python code in Visual Studio Code. Check out the [Settings section](#settings) below for more details on how to customize the extension.

- **Integrated Import Sorting**: Once this extension is installed in Visual Studio Code, isort is automatically registered as an import organizer. You can use `Shift + Alt + O` to trigger the organize imports editor action. You can also trigger this from the quick fix available when imports are not organized.

- **Customizable isort Arguments**: You can customize the arguments passed to isort by modifying the `isort.args` setting.

- **Import Sorting on Save**: You can enable import sorting on save for Python files by changing the `editor.codeActionsOnSave` setting. It also works alongside the [VS Code Black formatter extension](https://marketplace.visualstudio.com/items?itemName=ms-python.black-formatter) if you set the following settings: 
    
  ```json
    "[python]": {
      "editor.defaultFormatter": "ms-python.black-formatter",
      "editor.formatOnSave": true,
      "editor.codeActionsOnSave": {
          "source.organizeImports": "explicit"
      },
    },
    "isort.args":["--profile", "black"],
  ```


![Fixing import sorting with a code action.](images/vscode-isort.gif)



### Disabling isort

If you want to disable isort for your entire workspace or globally, you can [disable this extension](https://code.visualstudio.com/docs/editor/extension-marketplace#_disable-an-extension) in Visual Studio Code.

## Settings

| Settings               | Default                           | Description                                                                                                                                                                                                                                                              |
| ---------------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| isort.args             | `[]`                              | Arguments passed to isort for sorting imports in Python files. Each argument should be provided as a separate string in the array. <br> Examples: <br> - `"isort.args" = ["--settings-file", "<file>"]` <br> - `"isort.args" = ["--settings-path", "${fileDirname}"]`                                                                                                                                                                          |
| isort.check            | `false`                           | Whether to run `isort --check` on open Python files and report sorting issues as a "Hint" in the Problems window. You can update `isort.severity` to show sorting issues with higher severity.                                                                                                                            |
| isort.severity         | `{ "W": "Warning", "E": "Hint" }` | Mapping of isort's message types to VS Code's diagnostic severity levels as displayed in the Problems window.                                                                                                                                                                   |
| isort.path             | `[]`                              | Path of the isort binary to be used by this extension. Note: This may slow down formatting.<br> Examples: <br>- `isort.path : ["~/global_env/isort"]` <br> - `isort.path : ["conda", "run", "-n", "lint_env", "python", "-m", "isort"]` |
| isort.interpreter      | `[]`                              | Path to a Python executable or a command that will be used to launch the isort server and any subprocess. Accepts an array of a single or multiple strings. When set to `[]`, the extension will use the path to the selected Python interpreter.                                                                                                                   |
| isort.importStrategy   | `useBundled`                      | Defines which isort binary to be used to lint Python files. When set to `useBundled`, the extension will use the isort binary that is shipped with the extension. When set to `fromEnvironment`, the extension will attempt to use the isort binary and all dependencies that are available in the currently selected environment. Note: If the extension can't find a valid isort binary in the selected environment, it will fallback to using the isort binary that is shipped with the extension. The `isort.path` setting may also be ignored when this setting is set to `fromEnvironment`.                                                                                           |
| isort.showNotification | `off`                             | Controls when notifications are shown by this extension. Accepted values are `onError`, `onWarning`, `always` and `off`.                                                                                                                                                                                                                         |
| isort.serverEnabled    | `true`                            | **Experimental** setting to control whether to run isort in a server-like mode. By default `isort` is run behind LSP server, but you can disable this setting to run isort directly. Disabling this setting will also disable import sorting via Code Actions or Organize Imports, but you can still sort imports through the **isort: Sort Imports** command.                                                                                                                                                                                                                           |

## Commands

| Command        | Description                      |
| -------------- | -------------------------------- |
| isort: Restart | Force re-start the isort server. |

## Logging

From the Command Palette (**View** > **Command Palette ...**), run the **Developer: Set Log Level...** command. Select **isort** from the **Extension logs** group. Then select the log level you want to set.

Alternatively, you can set the `isort.trace.server` setting to `verbose` to get more detailed logs from the isort server. This can be helpful when filing bug reports.

To open the logs, click on the language status icon (`{}`) on the bottom right of the Status bar, next to the Python language mode. Locate the **isort** entry and select **Open logs**.

## Development

This extension uses the shared [`vscode-common-python-lsp`](https://github.com/microsoft/vscode-common-python-lsp) TypeScript and Python libraries from the git submodule at `external/vscode-common-python-lsp`. The setup commands below initialize that submodule before npm resolves the local dependency, install and build the shared Node package, install extension dependencies, and bundle the Python libraries.

Prerequisites: Git, Node.js (see `.nvmrc`), and Python 3.10 or later (`python` on Windows or `python3` on macOS/Linux). Setup creates or reuses a project-local `.venv` for Python tools rather than installing into your global Python environment. The nox bundling session uses Python 3.10 and may download that interpreter if it is not already installed.

Clone the repository and enter its directory:

```bash
git clone https://github.com/microsoft/vscode-isort.git
cd vscode-isort
```

Setup initializes submodules automatically. If installing manually instead, initialize (or update) the submodule before installing dependencies:

```bash
git submodule update --init --recursive
```

### Local package feeds

Choose the appropriate setup below before installing dependencies. Both paths use the same checked-in lockfile; do not rewrite its package URLs.

#### Public contributors (non-Microsoft employees)

Use the public setup, which selects `https://registry.npmjs.org/` and `https://pypi.org/simple/` for its child processes. No Microsoft account or internal-feed credentials are needed, and this command works before `node_modules` exists:

From the repository root:

```bash
npm run setup
```

#### Microsoft employees

Use the Microsoft setup, which selects `https://packagefeedproxy.microsoft.io/npm/` and `https://packagefeedproxy.microsoft.io/pypi/simple/` for its child processes:

```bash
npm run setup:msft
```

Both commands use the same setup implementation, stop on errors, and keep registry overrides scoped to setup's child processes; they do not change your shell environment or add credentials. Neither command edits `.npmrc` or rewrites the checked-in lockfiles. Existing `registry.npmjs.org` lockfile URLs do not need rewriting for proxy installs.

After setup, run `npm run compile` to build the extension. For subsequent Python commands, use `.venv\Scripts\python.exe` on Windows or `.venv/bin/python` on macOS/Linux (or activate that virtual environment). Registry overrides are not retained after setup.

### GitHub Actions package feeds

The PR, push, and CodeQL workflows set `NPM_CONFIG_REGISTRY` to `https://packagefeedproxy.microsoft.io/npm/` and `PIP_INDEX_URL` to `https://packagefeedproxy.microsoft.io/pypi/simple/`. These workflow-level settings also apply to the shared build/lint actions, nested npm commands, and pip installs in nox sessions. The npm endpoint follows the [TypeScript CI package-feed-proxy job](https://github.com/microsoft/TypeScript/blob/main/.github/workflows/ci.yml).

The workflow settings leave local registry configuration, public URLs in `package-lock.json`, and Dependabot configuration unchanged. Existing dependency caches are retained; uncached package requests use the configured proxy.
