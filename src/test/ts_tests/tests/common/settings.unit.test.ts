// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import * as sinon from 'sinon';
import * as TypeMoq from 'typemoq';
import * as vscodeapi from '../../../../common/vscodeapi';
import * as python from '../../../../common/python';
import { assert } from 'chai';
import { ConfigurationTarget, Uri, WorkspaceConfiguration, WorkspaceFolder } from 'vscode';
import { EXTENSION_ROOT_DIR } from '../../../../common/constants';
import { getWorkspaceSettings, ISettings } from '../../../../common/settings';

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
                .setup((c) => c.get('logLevel', 'error'))
                .returns(() => 'error')
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
            assert.deepStrictEqual(settings.importStrategy, 'useBundled');
            assert.deepStrictEqual(settings.interpreter, []);
            assert.deepStrictEqual(settings.logLevel, 'error');
            assert.deepStrictEqual(settings.path, []);
            assert.deepStrictEqual(settings.severity, DEFAULT_SEVERITY);
            assert.deepStrictEqual(settings.showNotifications, 'off');
            assert.deepStrictEqual(settings.workspace, workspace1.uri.toString());

            configMock.verifyAll();
            pythonConfigMock.verifyAll();
        });
    });
});
