// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const path = require('node:path');
const { test } = require('node:test');
const vm = require('node:vm');

const source = readFileSync(path.join(__dirname, 'setup.js'), 'utf8');

function load({ platform = 'win32', existingVenv = false, failAt, failure, args = [], cli = false } = {}) {
    const paths = platform === 'win32' ? path.win32 : path.posix;
    const root = platform === 'win32' ? 'C:\\workspace with spaces\\isort' : '/workspace with spaces/isort';
    const calls = [];
    const errors = [];
    const env = {
        npm_execpath: paths.join(root, 'npm', 'npm-cli.js'),
        npm_config_registry: 'https://old.example/npm/',
        NPM_CONFIG_REGISTRY: 'https://other.example/npm/',
        PIP_INDEX_URL: 'https://old.example/pypi/',
        HTTPS_PROXY: 'https://network.example/',
    };
    const originalEnv = { ...env };
    const process = { env, platform, execPath: paths.join(root, 'node'), argv: ['node', 'setup.js', ...args] };
    const module = { exports: {} };
    const require = (name) => {
        if (name === 'node:path') {
            return paths;
        }
        if (name === 'node:fs') {
            return { existsSync: () => existingVenv };
        }
        assert.equal(name, 'node:child_process');
        return {
            spawnSync(command, args, options) {
                calls.push({ command, args: Array.from(args), ...options });
                return calls.length === failAt ? failure : { status: 0 };
            },
        };
    };
    require.main = cli ? module : undefined;
    vm.runInNewContext(source, {
        require,
        module,
        process,
        __dirname: paths.join(root, 'build'),
        console: { log() {}, error: (message) => errors.push(message) },
    });
    return { ...module.exports, calls, errors, process, originalEnv, root, paths };
}

for (const platform of ['win32', 'linux']) {
    test(`${platform}: setup orders submodule, venv, shared build, root install and bundling`, () => {
        const context = load({ platform });
        context.setup();
        const { calls, root, paths } = context;
        const python = paths.join(root, '.venv', platform === 'win32' ? 'Scripts\\python.exe' : 'bin/python');
        assert.deepEqual(calls[0].args, ['submodule', 'update', '--init', '--recursive']);
        assert.equal(calls[1].command, platform === 'win32' ? 'python' : 'python3');
        assert.deepEqual(calls[1].args, ['-m', 'venv', '.venv']);
        assert.equal(calls[2].command, python);
        assert.match(calls[2].args[1], /sys.version_info < \(3, 10\)/);
        assert.equal(calls[3].command, python);
        assert.deepEqual(calls[3].args, ['-m', 'pip', 'install', '--upgrade', 'pip', 'wheel', 'nox']);
        assert.deepEqual(calls[4].args, [context.process.env.npm_execpath, 'ci', '--include=dev']);
        assert.equal(calls[4].cwd, paths.join(root, 'external', 'vscode-common-python-lsp', 'typescript'));
        assert.deepEqual(calls[5].args, [context.process.env.npm_execpath, 'run', 'build']);
        assert.equal(calls[5].cwd, calls[4].cwd);
        assert.deepEqual(calls[6].args, [context.process.env.npm_execpath, 'ci', '--include=dev']);
        assert.equal(calls[6].cwd, root);
        assert.deepEqual(calls[7].args, ['-m', 'nox', '--session', 'install_bundled_libs']);
        assert.equal(calls[7].command, python);
        assert.equal(calls.length, 8);
        assert.deepEqual(context.process.env, context.originalEnv);
    });
}

for (const microsoft of [false, true]) {
    test(`${microsoft ? 'Microsoft' : 'public'} setup selects feeds for every child without changing parent config`, () => {
        const context = load();
        context.setup({ microsoft });
        for (const call of context.calls) {
            assert.equal(
                call.env.npm_config_registry,
                microsoft ? 'https://packagefeedproxy.microsoft.io/npm/' : 'https://registry.npmjs.org/',
            );
            assert.equal(
                call.env.PIP_INDEX_URL,
                microsoft ? 'https://packagefeedproxy.microsoft.io/pypi/simple/' : 'https://pypi.org/simple/',
            );
            assert.equal(call.env.NPM_CONFIG_REGISTRY, undefined);
            assert.equal(call.env.HTTPS_PROXY, context.originalEnv.HTTPS_PROXY);
            assert.equal(call.stdio, 'inherit');
            assert.equal(call.shell, undefined);
        }
        assert.deepEqual(context.process.env, context.originalEnv);
    });
}

test('setup reuses an existing project virtual environment', () => {
    const context = load({ existingVenv: true });
    context.setup();
    assert.equal(context.calls.length, 7);
    assert.equal(
        context.calls.some((call) => call.args.includes('venv')),
        false,
    );
});

for (const failure of [{ status: 7 }, { status: null, signal: 'SIGTERM' }, { error: new Error('not found') }]) {
    test(`setup reports failure and stops: ${failure.signal || failure.error?.message || failure.status}`, () => {
        const context = load({ failAt: 5, failure });
        context.runCli();
        assert.equal(context.calls.length, 5);
        assert.equal(context.process.exitCode, failure.status || 1);
        assert.match(context.errors[0], /Setup failed/);
    });
}

test('setup requires npm to supply its CLI path', () => {
    const context = load();
    delete context.process.env.npm_execpath;
    context.runCli();
    assert.equal(context.calls.length, 0);
    assert.equal(context.process.exitCode, 1);
    assert.match(context.errors[0], /npm run setup/);
});

test('public setup runs directly as a standalone entry point', () => {
    const context = load({ cli: true });
    assert.equal(context.calls.length, 8);
    assert.equal(context.calls[0].env.npm_config_registry, 'https://registry.npmjs.org/');
    assert.equal(context.errors.length, 0);
});

test('setup rejects unsupported arguments before running commands', () => {
    const context = load({ args: ['--proxy'] });
    context.runCli();
    assert.equal(context.calls.length, 0);
    assert.equal(context.process.exitCode, 1);
    assert.match(context.errors[0], /takes no arguments/);
});

test('Microsoft setup is a separate entry point using the shared implementation', () => {
    const entry = readFileSync(path.join(__dirname, 'setup-msft.js'), 'utf8');
    let called = false;
    vm.runInNewContext(entry, {
        require(name) {
            assert.equal(name, './setup');
            return {
                runCli(options) {
                    assert.equal(options.microsoft, true);
                    called = true;
                },
            };
        },
    });
    assert.equal(called, true);
    const scripts = JSON.parse(readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8')).scripts;
    assert.equal(scripts.setup, 'node ./build/setup.js');
    assert.equal(scripts['setup:msft'], 'node ./build/setup-msft.js');
});
