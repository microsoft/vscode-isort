// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

// NOTE: Variable resolution and getWorkspaceSettings tests live in the shared
// package (@vscode/common-python-lsp) test suite. Extension-level tests focus
// on extension-specific wrapper behavior.

import { assert } from 'chai';
import * as sinon from 'sinon';
import * as TypeMoq from 'typemoq';
import { ConfigurationChangeEvent, WorkspaceConfiguration } from 'vscode';
import { checkIfConfigurationChanged, getServerEnabled } from '../../../../common/settings';
import * as vscodeapi from '../../../../common/vscodeapi';

suite('Settings Tests', () => {
    suite('getServerEnabled tests', () => {
        let getConfigurationStub: sinon.SinonStub;

        setup(() => {
            getConfigurationStub = sinon.stub(vscodeapi, 'getConfiguration');
        });

        teardown(() => {
            sinon.restore();
        });

        test('Returns true when serverEnabled is true', () => {
            const configMock = TypeMoq.Mock.ofType<WorkspaceConfiguration>();
            configMock.setup((c) => c.get('serverEnabled', true)).returns(() => true);
            getConfigurationStub.returns(configMock.object);

            assert.isTrue(getServerEnabled('isort'));
        });

        test('Returns false when serverEnabled is false', () => {
            const configMock = TypeMoq.Mock.ofType<WorkspaceConfiguration>();
            configMock.setup((c) => c.get('serverEnabled', true)).returns(() => false);
            getConfigurationStub.returns(configMock.object);

            assert.isFalse(getServerEnabled('isort'));
        });

        test('Defaults to true when serverEnabled is not set', () => {
            const configMock = TypeMoq.Mock.ofType<WorkspaceConfiguration>();
            configMock.setup((c) => c.get('serverEnabled', true)).returns(() => true);
            getConfigurationStub.returns(configMock.object);

            assert.isTrue(getServerEnabled('isort'));
        });
    });

    suite('checkIfConfigurationChanged tests', () => {
        test('Detects serverEnabled change', () => {
            const event: ConfigurationChangeEvent = {
                affectsConfiguration: (section: string) => section === 'isort.serverEnabled',
            };
            assert.isTrue(checkIfConfigurationChanged(event, 'isort'));
        });

        test('Detects interpreter change', () => {
            const event: ConfigurationChangeEvent = {
                affectsConfiguration: (section: string) => section === 'isort.interpreter',
            };
            assert.isTrue(checkIfConfigurationChanged(event, 'isort'));
        });

        test('Detects importStrategy change', () => {
            const event: ConfigurationChangeEvent = {
                affectsConfiguration: (section: string) => section === 'isort.importStrategy',
            };
            assert.isTrue(checkIfConfigurationChanged(event, 'isort'));
        });

        test('Returns false for unrelated configuration change', () => {
            const event: ConfigurationChangeEvent = {
                affectsConfiguration: () => false,
            };
            assert.isFalse(checkIfConfigurationChanged(event, 'isort'));
        });
    });
});
