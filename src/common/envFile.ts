// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as dotenv from 'dotenv';
import * as fs from 'fs-extra';
import * as path from 'path';
import { WorkspaceFolder } from 'vscode';
import { traceLog, traceWarn } from './logging';
import { getConfiguration } from './vscodeapi';

/**
 * Reads the env file configured via `python.envFile` (defaults to `${workspaceFolder}/.env`),
 * parses it using dotenv, and returns the resulting environment variables.
 * Returns an empty record if the file does not exist or cannot be read.
 */
export async function getEnvFileVars(workspace: WorkspaceFolder): Promise<Record<string, string>> {
    const pythonConfig = getConfiguration('python', workspace.uri);
    let envFilePath = pythonConfig.get<string>('envFile', '${workspaceFolder}/.env') ?? '${workspaceFolder}/.env';

    // Resolve ${workspaceFolder}
    envFilePath = envFilePath.replace(/\$\{workspaceFolder\}/g, workspace.uri.fsPath);

    if (!path.isAbsolute(envFilePath)) {
        envFilePath = path.join(workspace.uri.fsPath, envFilePath);
    }

    try {
        if (await fs.pathExists(envFilePath)) {
            const content = await fs.readFile(envFilePath, 'utf-8');
            const vars = dotenv.parse(content);
            const count = Object.keys(vars).length;
            if (count > 0) {
                traceLog(`Loaded ${count} environment variable(s) from ${envFilePath}`);
            }
            return vars;
        }
    } catch (err) {
        traceWarn(`Failed to read env file ${envFilePath}: ${err}`);
    }
    return {};
}
