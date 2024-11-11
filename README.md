# Import sorting extension for Visual Studio Code using isort

A Visual Studio Code extension that provides import sorting for Python projects using isort. The extension uses the Language Server Protocol ([LSP](https://microsoft.github.io/language-server-protocol/)) to run `isort` in a server-like mode.

This extension ships with `isort=5.13.2`.

> **Note**: The minimum version of isort this extension supports is `5.10.1`. If you have any issues sorting imports with isort, please report it to [this issue tracker](https://github.com/PyCQA/isort/issues) as this extension is just a wrapper around isort.

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
