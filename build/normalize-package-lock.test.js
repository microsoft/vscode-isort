// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { createHash } = require('node:crypto');
const { test } = require('node:test');
const { normalizePackageLock } = require('./normalize-package-lock');

const tarball = Buffer.from('public npm tarball');
const integrity = `sha512-${createHash('sha512').update(tarball).digest('base64')}`;
const mirror = 'https://devdiv.pkgs.visualstudio.com/DevDiv/_packaging/Pylance_PublicPackages/npm/registry/';
const publicRegistry = 'https://registry.npmjs.org/';

function lockfile(packages, extra = {}) {
    return JSON.stringify({ name: 'isort', lockfileVersion: 3, packages, ...extra }, null, 4) + '\n';
}

function publicFetch(url, options) {
    assert.ok(url.startsWith(publicRegistry));
    assert.equal(options.redirect, 'error');
    assert.ok(options.signal instanceof AbortSignal);
    return Promise.resolve({
        ok: true,
        arrayBuffer: async () => tarball,
    });
}

test('normalizes scoped and nested dependencies without changing other bytes', async () => {
    const source = lockfile({
        'node_modules/@typescript-eslint/parser': {
            version: '8.71.0',
            resolved: `${mirror}@typescript-eslint/parser/-/parser-8.71.0.tgz`,
            integrity,
            dev: true,
        },
        'node_modules/example/node_modules/other': {
            version: '1.0.0',
            resolved: `${mirror}other/-/other-1.0.0.tgz`,
            integrity,
        },
    }).replace(/\n/g, '\r\n');
    const result = await normalizePackageLock(source, publicFetch);
    assert.equal(result, source.replaceAll(mirror, publicRegistry));
    assert.equal(await normalizePackageLock(result, () => assert.fail('Unexpected download')), result);
});

test('preserves public, intentional Azure, git, file, and linked dependencies', async () => {
    const source = lockfile({
        '': { name: 'isort' },
        'node_modules/public': { resolved: `${publicRegistry}public/-/public-1.0.0.tgz` },
        'node_modules/azure': {
            resolved:
                'https://pkgs.dev.azure.com/azure-public/vside/_packaging/msft_consumption/npm/registry/example.tgz',
        },
        'node_modules/git': { resolved: 'git+https://github.com/example/example.git#abc' },
        'node_modules/local': { resolved: 'file:external/example' },
        'node_modules/shared': { resolved: 'external/example', link: true },
    });
    assert.equal(await normalizePackageLock(source, () => assert.fail('Unexpected download')), source);
});

test('handles the Azure mirror hostname and v2 legacy entries, downloading each tarball once', async () => {
    const resolved =
        'https://pkgs.dev.azure.com/devdiv/DevDiv/_packaging/Pylance_PublicPackages/npm/registry/example/-/example-1.0.0.tgz';
    const entry = { version: '1.0.0', resolved, integrity };
    const source = lockfile(
        { 'node_modules/example': entry },
        { lockfileVersion: 2, dependencies: { example: entry } },
    );
    let downloads = 0;
    const result = await normalizePackageLock(source, (url, options) => {
        downloads++;
        return publicFetch(url, options);
    });
    assert.equal(downloads, 1);
    assert.equal(result, source.replaceAll(resolved, `${publicRegistry}example/-/example-1.0.0.tgz`));
});

test('rejects unavailable public packages and mismatched integrity instead of rewriting', async () => {
    const source = lockfile({
        'node_modules/example': { resolved: `${mirror}example/-/example-1.0.0.tgz`, integrity },
    });
    await assert.rejects(
        normalizePackageLock(source, async () => ({ ok: false, status: 404 })),
        /HTTP 404/,
    );
    await assert.rejects(
        normalizePackageLock(source, async () => ({ ok: true, arrayBuffer: async () => Buffer.from('different') })),
        /integrity mismatch/,
    );
    await assert.rejects(
        normalizePackageLock(source, async () => {
            throw new Error('Network unavailable');
        }),
        /Network unavailable/,
    );
});

test('rejects missing integrity, unsupported hashes, and unexpected mirror URLs', async () => {
    for (const [entry, error] of [
        [{ resolved: `${mirror}example/-/example-1.0.0.tgz` }, /without an integrity hash/],
        [{ resolved: `${mirror}example/-/example-1.0.0.tgz`, integrity: 'md5-invalid' }, /Unsupported integrity/],
        [{ resolved: `${mirror}example/-/example-1.0.0.tgz?token=example`, integrity }, /Unexpected npm mirror/],
    ]) {
        await assert.rejects(
            normalizePackageLock(lockfile({ 'node_modules/example': entry }), () => assert.fail('Unexpected download')),
            error,
        );
    }
});

test('uses the strongest integrity algorithm and supports sha1-only lockfile entries', async () => {
    const sha1 = `sha1-${createHash('sha1').update(tarball).digest('base64')}`;
    const entry = { resolved: `${mirror}example/-/example-1.0.0.tgz`, integrity: sha1 };
    await normalizePackageLock(lockfile({ 'node_modules/example': entry }), publicFetch);
    entry.integrity = `${sha1} sha512-invalid`;
    await assert.rejects(
        normalizePackageLock(lockfile({ 'node_modules/example': entry }), publicFetch),
        /integrity mismatch/,
    );
});

test('rejects malformed or unsupported lockfiles', async () => {
    await assert.rejects(normalizePackageLock('{'), SyntaxError);
    await assert.rejects(normalizePackageLock('{"lockfileVersion":1}'), /Expected an npm lockfile/);
});

test(
    'verifies a real locked package against public npm',
    { skip: process.env.LOCKFILE_INTEGRATION_TEST !== '1' },
    async () => {
        const entry = require('../package-lock.json').packages['node_modules/@typescript-eslint/parser'];
        const suffix = `@typescript-eslint/parser/-/parser-${entry.version}.tgz`;
        const source = lockfile({
            'node_modules/@typescript-eslint/parser': { ...entry, resolved: mirror + suffix },
        });
        assert.equal(await normalizePackageLock(source), source.replace(mirror + suffix, publicRegistry + suffix));
    },
);
