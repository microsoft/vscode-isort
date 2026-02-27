// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import { assert } from 'chai';
import * as path from 'path';
import * as sinon from 'sinon';
import * as TypeMoq from 'typemoq';
import { Uri, WorkspaceConfiguration, WorkspaceFolder } from 'vscode';
import { EXTENSION_ROOT_DIR } from '../../../../common/constants';
import * as python from '../../../../common/python';
import { ISettings, getWorkspaceSettings } from '../../../../common/settings';
import * as vscodeapi from '../../../../common/vscodeapi';

function setupDefaultConfigMocks(
    configMock: TypeMoq.IMock<WorkspaceConfiguration>,
    pythonConfigMock: TypeMoq.IMock<WorkspaceConfiguration>,
    cwdValue: string,
    workspace: WorkspaceFolder,
): void {
    configMock.setup((c) => c.get('args', [])).returns(() => []);
    configMock.setup((c) => c.get('path', [])).returns(() => []);
    configMock.setup((c) => c.get('check', false)).returns(() => false);
    configMock.setup((c) => c.get('severity', TypeMoq.It.isAny())).returns(() => ({ W: 'Warning', E: 'Hint' }));
    configMock.setup((c) => c.get('importStrategy', 'useBundled')).returns(() => 'useBundled');
    configMock.setup((c) => c.get('showNotifications', 'off')).returns(() => 'off');
    configMock.setup((c) => c.get('cwd', workspace.uri.fsPath)).returns(() => cwdValue);
    pythonConfigMock.setup((c) => c.get('sortImports.args', [])).returns(() => []);
    pythonConfigMock.setup((c) => c.get('sortImports.path', '')).returns(() => '');
}

// eslint-disable-next-line @typescript-eslint/naming-convention
const DEFAULT_SEVERITY: Record<string, string> = { W: 'Warning', E: 'Hint' };

suite('Settings Tests', () => {
    suite('getWorkspaceSettings tests', () => {
        let getConfigurationStub: sinon.SinonStub;
        let getInterpreterDetailsStub: sinon.SinonStub;
        let configMock: TypeMoq.IMock<WorkspaceConfiguration>;
        let pythonConfigMock: TypeMoq.IMock<WorkspaceConfiguration>;
        let workspace1: WorkspaceFolder = {
            uri: Uri.file(path.join(EXTENSION_ROOT_DIR, 'src', 'test', 'testWorkspace', 'workspace1')),
            name: 'workspace1',
            index: 0,
        };

        setup(() => {
            getConfigurationStub = sinon.stub(vscodeapi, 'getConfiguration');
            // resolveVariables() always calls getWorkspaceFolders() for ${workspaceFolder:<name>} substitutions
            sinon.stub(vscodeapi, 'getWorkspaceFolders').returns([workspace1]);
            getInterpreterDetailsStub = sinon.stub(python, 'getInterpreterDetails');
            configMock = TypeMoq.Mock.ofType<WorkspaceConfiguration>();
            pythonConfigMock = TypeMoq.Mock.ofType<WorkspaceConfiguration>();
            getConfigurationStub.callsFake((namespace: string, uri: Uri) => {
                if (namespace.startsWith('isort')) {
                    return configMock.object;
                }
                return pythonConfigMock.object;
            });
        });

        teardown(() => {
            sinon.restore();
        });

        test('Default Settings test', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            configMock
                .setup((c) => c.get('args', []))
                .returns(() => [])
                .verifiable(TypeMoq.Times.atLeastOnce());
            configMock
                .setup((c) => c.get('path', []))
                .returns(() => [])
                .verifiable(TypeMoq.Times.atLeastOnce());
            configMock
                .setup((c) => c.get('check', false))
                .returns(() => false)
                .verifiable(TypeMoq.Times.atLeastOnce());
            configMock
                .setup((c) => c.get('severity', DEFAULT_SEVERITY))
                .returns(() => DEFAULT_SEVERITY)
                .verifiable(TypeMoq.Times.atLeastOnce());
            configMock
                .setup((c) => c.get('importStrategy', 'useBundled'))
                .returns(() => 'useBundled')
                .verifiable(TypeMoq.Times.atLeastOnce());
            configMock
                .setup((c) => c.get('showNotifications', 'off'))
                .returns(() => 'off')
                .verifiable(TypeMoq.Times.atLeastOnce());
            configMock
                .setup((c) => c.get('cwd', workspace1.uri.fsPath))
                .returns(() => workspace1.uri.fsPath)
                .verifiable(TypeMoq.Times.atLeastOnce());

            pythonConfigMock
                .setup((c) => c.get('sortImports.args', []))
                .returns(() => [])
                .verifiable(TypeMoq.Times.atLeastOnce());
            pythonConfigMock
                .setup((c) => c.get('sortImports.path', ''))
                .returns(() => 'isort')
                .verifiable(TypeMoq.Times.atLeastOnce());

            const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
            assert.deepStrictEqual(settings.args, []);
            assert.deepStrictEqual(settings.cwd, workspace1.uri.fsPath);
            assert.deepStrictEqual(settings.importStrategy, 'useBundled');
            assert.deepStrictEqual(settings.interpreter, []);
            assert.deepStrictEqual(settings.path, []);
            assert.deepStrictEqual(settings.severity, DEFAULT_SEVERITY);
            assert.deepStrictEqual(settings.showNotifications, 'off');
            assert.deepStrictEqual(settings.workspace, workspace1.uri.toString());

            configMock.verifyAll();
            pythonConfigMock.verifyAll();
        });

        test('cwd with ${workspaceFolder} is resolved', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            setupDefaultConfigMocks(configMock, pythonConfigMock, '${workspaceFolder}', workspace1);

            const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
            assert.strictEqual(settings.cwd, workspace1.uri.fsPath);
        });

        test('cwd with ${workspaceFolder:name} is resolved', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            setupDefaultConfigMocks(configMock, pythonConfigMock, '${workspaceFolder:workspace1}', workspace1);

            const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
            assert.strictEqual(settings.cwd, workspace1.uri.fsPath);
        });

        test('cwd with ${userHome} is resolved', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            setupDefaultConfigMocks(configMock, pythonConfigMock, '${userHome}', workspace1);

            const expected = process.env.HOME || process.env.USERPROFILE || '${userHome}';
            const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
            assert.strictEqual(settings.cwd, expected);
        });

        test('cwd with ${cwd} is resolved to process.cwd()', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            setupDefaultConfigMocks(configMock, pythonConfigMock, '${cwd}', workspace1);

            const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
            assert.strictEqual(settings.cwd, process.cwd());
        });

        test('cwd with ${env:VAR} is resolved', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            process.env.ISORT_TEST_CWD = '/test/env/path';
            try {
                setupDefaultConfigMocks(configMock, pythonConfigMock, '${env:ISORT_TEST_CWD}', workspace1);

                const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
                assert.strictEqual(settings.cwd, '/test/env/path');
            } finally {
                delete process.env.ISORT_TEST_CWD;
            }
        });
    });
});
