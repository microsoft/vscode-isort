// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { Disposable, workspace } from 'vscode';
import { ISORT_CONFIG_FILES } from './constants';
import { traceLog } from './logging';

export function createConfigFileWatchers(onConfigChanged: () => Promise<void>): Disposable[] {
    return ISORT_CONFIG_FILES.map((pattern) => {
        const watcher = workspace.createFileSystemWatcher(`**/${pattern}`);
        watcher.onDidChange(async () => {
            traceLog(`isort config file changed: ${pattern}`);
            await onConfigChanged();
        });
        watcher.onDidCreate(async () => {
            traceLog(`isort config file created: ${pattern}`);
            await onConfigChanged();
        });
        watcher.onDidDelete(async () => {
            traceLog(`isort config file deleted: ${pattern}`);
            await onConfigChanged();
        });
        return watcher;
    });
}
