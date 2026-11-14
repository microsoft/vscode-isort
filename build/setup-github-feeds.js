// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const { appendFileSync } = require('node:fs');
const { URL } = require('node:url');
const { microsoft } = require('./package-feeds.json');

try {
    const { AZURE_DEVOPS_TOKEN: token, GITHUB_ENV: environmentFile } = process.env;
    if (!token || token === 'null' || /[\r\n]/.test(token)) {
        throw new Error('A nonempty, single-line Azure DevOps token is required.');
    }
    if (!environmentFile) {
        throw new Error('GITHUB_ENV is required.');
    }

    console.log(`::add-mask::${token}`);
    const pipIndex = new URL(microsoft.pip);
    pipIndex.username = 'build';
    pipIndex.password = token;
    console.log(`::add-mask::${pipIndex.href}`);

    appendFileSync(environmentFile, [`PIP_INDEX_URL=${pipIndex.href}`, 'PIP_NO_INPUT=1', ''].join('\n'), 'utf8');
} catch (error) {
    console.error(`[setup] GitHub feed authentication failed: ${error.message}`);
    process.exitCode = 1;
}
