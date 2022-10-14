// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

import * as path from 'path';
import * as sinon from 'sinon';
import * as vscodeapi from '../../../../common/vscodeapi';
import * as python from '../../../../common/python';
import { assert } from 'chai';
import { ConfigurationTarget, Uri, WorkspaceConfiguration, WorkspaceFolder } from 'vscode';
import { EXTENSION_ROOT_DIR } from '../../../../common/constants';
import { getWorkspaceSettings, ISettings } from '../../../../common/settings';

class MockConfig implements WorkspaceConfiguration {
    readonly [key: string]: any;
    get<T>(section: string): T | undefined;
    get<T>(section: string, defaultValue: T): T;
    get(section: unknown, defaultValue?: unknown): unknown | undefined {
        return undefined;
    }
    has(section: string): boolean {
        throw new Error('Method not implemented.');
    }
    inspect<T>(section: string):
        | {
              key: string;
              defaultValue?:
                  | T
                  // Licensed under the MIT License. // Licensed under the MIT License.
                  | undefined;
              globalValue?: T | undefined;
              workspaceValue?: T | undefined;
              workspaceFolderValue?: T | undefined;
              defaultLanguageValue?: T | undefined;
              globalLanguageValue?: T | undefined;
              workspaceLanguageValue?: T | undefined;
              workspaceFolderLanguageValue?: T | undefined;
              languageIds?: string[] | undefined;
          }
        | undefined {
        throw new Error('Method not implemented.');
    }
    update(
        section: string,
        value: any,
        configurationTarget?: boolean | ConfigurationTarget | null | undefined,
        overrideInLanguage?: boolean | undefined,
    ): Thenable<void> {
        return Promise.resolve();
    }
}

suite('Settings Tests', () => {
    suite('getWorkspaceSettings tests', () => {
        let getConfigurationStub: sinon.SinonStub;
        let getInterpreterDetailsStub: sinon.SinonStub;
        let config: WorkspaceConfiguration;
        let configMock: sinon.SinonMock;
        let workspace1: WorkspaceFolder = {
            uri: Uri.file(path.join(EXTENSION_ROOT_DIR, 'src', 'test', 'testWorkspace', 'workspace1')),
            name: 'workspace1',
            index: 0,
        };

        setup(() => {
            getConfigurationStub = sinon.stub(vscodeapi, 'getConfiguration');
            getInterpreterDetailsStub = sinon.stub(python, 'getInterpreterDetails');
            config = new MockConfig();
            configMock = sinon.mock(config);
            getConfigurationStub.returns(config);
        });

        teardown(() => {
            sinon.restore();
        });

        test('Defaults test', async () => {
            getInterpreterDetailsStub.resolves({ path: undefined });
            const settings: ISettings = await getWorkspaceSettings('isort', workspace1);
            assert.deepStrictEqual(settings.args, []);
            assert.deepStrictEqual(settings.importStrategy, 'useBundled');
            assert.deepStrictEqual(settings.interpreter, []);
            assert.deepStrictEqual(settings.logLevel, 'error');
            assert.deepStrictEqual(settings.path, []);
            assert.deepStrictEqual(settings.severity, {});
            assert.deepStrictEqual(settings.showNotifications, 'off');
            assert.deepStrictEqual(settings.workspace, workspace1.uri.toString());
        });
    });
});
