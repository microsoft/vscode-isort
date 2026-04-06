// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as sinon from 'sinon';
import * as path from 'path';
import { Uri, WorkspaceFolder } from 'vscode';
import * as fsExtra from 'fs-extra';
import * as vscodeapi from '../../../../common/vscodeapi';
import { getEnvFileVars } from '../../../../common/envFile';

suite('getEnvFileVars Tests', () => {
    let sandbox: sinon.SinonSandbox;
    let getConfigurationStub: sinon.SinonStub;
    let pathExistsStub: sinon.SinonStub;
    let readFileStub: sinon.SinonStub;

    const workspaceFolder: WorkspaceFolder = {
        uri: Uri.file('/test/workspace'),
        name: 'workspace',
        index: 0,
    };

    setup(() => {
        sandbox = sinon.createSandbox();
        getConfigurationStub = sandbox.stub(vscodeapi, 'getConfiguration');
        pathExistsStub = sandbox.stub(fsExtra, 'pathExists');
        readFileStub = sandbox.stub(fsExtra, 'readFile');
    });

    teardown(() => {
        sandbox.restore();
    });

    test('returns parsed variables from existing .env file', async () => {
        getConfigurationStub.returns({
            get: (_key: string, defaultValue: string) => defaultValue,
        });
        pathExistsStub.resolves(true);
        readFileStub.resolves('FOO=bar\nBAZ=qux\n');

        const vars = await getEnvFileVars(workspaceFolder);
        assert.deepStrictEqual(vars, { FOO: 'bar', BAZ: 'qux' });
    });

    test('returns empty object for missing file', async () => {
        getConfigurationStub.returns({
            get: (_key: string, defaultValue: string) => defaultValue,
        });
        pathExistsStub.resolves(false);

        const vars = await getEnvFileVars(workspaceFolder);
        assert.deepStrictEqual(vars, {});
    });

    test('resolves ${workspaceFolder} in path', async () => {
        getConfigurationStub.returns({
            get: (_key: string, _defaultValue: string) => '${workspaceFolder}/.env.test',
        });
        const expectedPath = path.join(workspaceFolder.uri.fsPath, '.env.test');
        pathExistsStub.resolves(true);
        readFileStub.resolves('KEY=value\n');

        const vars = await getEnvFileVars(workspaceFolder);
        assert.deepStrictEqual(vars, { KEY: 'value' });
        assert.isTrue(pathExistsStub.calledOnce, 'pathExists should be called once');
        const calledPath = pathExistsStub.firstCall.args[0];
        assert.strictEqual(calledPath, expectedPath);
    });

    test('resolves relative paths', async () => {
        getConfigurationStub.returns({
            get: (_key: string, _defaultValue: string) => '.env.local',
        });
        const expectedPath = path.join(workspaceFolder.uri.fsPath, '.env.local');
        pathExistsStub.resolves(true);
        readFileStub.resolves('RELATIVE=yes\n');

        const vars = await getEnvFileVars(workspaceFolder);
        assert.deepStrictEqual(vars, { RELATIVE: 'yes' });
        const calledPath = pathExistsStub.firstCall.args[0];
        assert.strictEqual(calledPath, expectedPath);
    });
});
