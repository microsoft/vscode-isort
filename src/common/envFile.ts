// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as fs from 'fs-extra';
import * as path from 'path';
import { WorkspaceFolder } from 'vscode';
import { traceLog, traceWarn } from './logging';
import { getConfiguration } from './vscodeapi';

/**
 * Parses a `.env` file and returns a map of environment variable key-value pairs.
 * Supports blank lines, `#` comments, `KEY=VALUE`, and basic quoting.
 */
export function parseEnvFile(content: string): Map<string, string> {
    const env = new Map<string, string>();
    for (const rawLine of content.split(/\r?\n/)) {
        const line = rawLine.trim();
        if (!line || line.startsWith('#')) {
            continue;
        }
        const eqIndex = line.indexOf('=');
        if (eqIndex < 0) {
            continue;
        }
        const key = line.substring(0, eqIndex).trim();
        let value = line.substring(eqIndex + 1).trim();
        // Strip matching surrounding quotes
        if (
            (value.startsWith('"') && value.endsWith('"')) ||
            (value.startsWith("'") && value.endsWith("'"))
        ) {
            value = value.slice(1, -1);
        }
        if (key) {
            env.set(key, value);
        }
    }
    return env;
}

/**
 * Reads the env file configured via `python.envFile` (defaults to `${workspaceFolder}/.env`),
 * parses it, and returns the resulting environment variable map.
 * Returns an empty map if the file does not exist or cannot be read.
 */
export async function getEnvFileVars(workspace: WorkspaceFolder): Promise<Map<string, string>> {
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
            const vars = parseEnvFile(content);
            if (vars.size > 0) {
                traceLog(`Loaded ${vars.size} environment variable(s) from ${envFilePath}`);
            }
            return vars;
        }
    } catch (err) {
        traceWarn(`Failed to read env file ${envFilePath}: ${err}`);
    }
    return new Map();
}
