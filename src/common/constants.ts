// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import type { ToolConfig } from '@vscode/common-python-lsp';

const folderName = path.basename(__dirname);
export const EXTENSION_ROOT_DIR =
    folderName === 'common' ? path.dirname(path.dirname(__dirname)) : path.dirname(__dirname);

export const RUNNER_SCRIPT_PATH = path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', 'script_runner.py');

export const ISORT_CONFIG_FILES = ['.isort.cfg', 'pyproject.toml', 'setup.cfg', 'tox.ini', '.editorconfig'];

/* eslint-disable @typescript-eslint/naming-convention */
const DEFAULT_SEVERITY: Record<string, string> = {
    W: 'Warning',
    E: 'Hint',
};

export const ISORT_TOOL_CONFIG: ToolConfig = {
    toolId: 'isort',
    toolDisplayName: 'isort',
    toolModule: 'isort',
    minimumPythonVersion: { major: 3, minor: 10 },
    configFiles: ISORT_CONFIG_FILES,
    serverScript: path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', 'lsp_server.py'),
    debugServerScript: path.join(EXTENSION_ROOT_DIR, 'bundled', 'tool', '_debug_server.py'),
    settingsDefaults: {
        check: false,
        severity: DEFAULT_SEVERITY,
        extraPaths: [],
    },
    trackedSettings: [
        'check',
        'args',
        'cwd',
        'severity',
        'path',
        'interpreter',
        'importStrategy',
        'showNotifications',
        'serverEnabled',
        'extraPaths',
    ],
};
