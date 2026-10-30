// Copyright (c) Microsoft Corporation. All rights reserved.
// Licensed under the MIT License.

const assert = require('node:assert/strict');
const { spawnSync } = require('node:child_process');
const { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, rmSync, writeFileSync } = require('node:fs');
const { tmpdir } = require('node:os');
const path = require('node:path');
const { test } = require('node:test');

const script = path.join(__dirname, 'localization.ps1');
const locales = ['cs', 'de', 'es', 'fr', 'it', 'ja', 'ko', 'pl', 'pt-br', 'qps-ploc', 'ru', 'tr', 'zh-cn', 'zh-tw'];

function fixture(t) {
    const root = mkdtempSync(path.join(tmpdir(), 'isort localization '));
    t.after(() => rmSync(root, { recursive: true, force: true }));
    writeFileSync(
        path.join(root, 'package.json'),
        JSON.stringify({ publisher: 'ms-python', name: 'isort', l10n: './l10n' }),
    );
    writeFileSync(path.join(root, 'package.nls.json'), '{"description":"English source"}\n');
    const translated = path.join(root, 'translated output');
    mkdirSync(translated);
    writeFileSync(path.join(translated, 'isort-new.xlf'), '<xliff/>');
    const handback = path.join(root, 'handback');
    mkdirSync(handback);
    for (const locale of locales) {
        writeFileSync(path.join(handback, `package.nls.${locale}.json`), JSON.stringify({ description: locale }));
        writeFileSync(path.join(handback, `bundle.l10n.${locale}.json`), JSON.stringify({ 'Open logs': locale }));
    }
    const wrapper = path.join(root, 'run.ps1');
    writeFileSync(
        wrapper,
        `
$ErrorActionPreference = 'Stop'
function npx {
    if (Test-Path 'fail-cli') { throw 'CLI failed' }
    $args | ConvertTo-Json -Compress | Add-Content -LiteralPath 'cli-calls.jsonl'
    $output = $args[4]
    switch ($args[2]) {
        export {
            if (!(Test-Path 'missing-bundle')) {
                $bundle = if (Test-Path 'empty-bundle') { '{}' } else { '{"Open logs":"Open logs"}' }
                Set-Content -LiteralPath (Join-Path $output 'bundle.l10n.json') -Value $bundle
            }
        }
        generate-xlf {
            [IO.File]::WriteAllText($output, "<xliff>\`r\`n</xliff>\`r\`n")
        }
        import-xlf { Copy-Item -Path 'handback/*.json' -Destination $output }
        default { throw "Unexpected CLI operation: $($args[2])" }
    }
}
& $env:LOCALIZATION_SCRIPT -Operation $env:OPERATION -OutputDirectory $env:OUTPUT_DIRECTORY -TranslationsPath $env:TRANSLATIONS_PATH
`,
    );
    return {
        root,
        handback,
        translated,
        run(operation) {
            return spawnSync('pwsh', ['-NoProfile', '-NonInteractive', '-File', wrapper], {
                cwd: root,
                encoding: 'utf8',
                env: {
                    ...process.env,
                    LOCALIZATION_SCRIPT: script,
                    OPERATION: operation,
                    OUTPUT_DIRECTORY: path.join(root, 'generated output'),
                    TRANSLATIONS_PATH: translated,
                },
            });
        },
    };
}

test('exports runtime and manifest inputs, including the shared submodule, with normalized XLF', (t) => {
    const context = fixture(t);
    const result = context.run('export');
    assert.equal(result.status, 0, result.stderr);
    const calls = readFileSync(path.join(context.root, 'cli-calls.jsonl'), 'utf8')
        .trim()
        .split(/\r?\n/)
        .map(JSON.parse);
    assert.deepEqual(calls[0].slice(5), ['./src', './external/vscode-common-python-lsp/typescript/src']);
    assert.equal(calls[1].at(-1), 'package.nls.json');
    assert.equal(calls[0][1], '@vscode/l10n-dev@0.0.35');
    const xlf = readFileSync(path.join(context.root, 'generated output', 'ms-python.isort-new.xlf'), 'utf8');
    assert.equal(xlf, '<xliff>\n</xliff>\n');
});

for (const marker of ['missing-bundle', 'empty-bundle', 'fail-cli']) {
    test(`rejects ${marker} instead of submitting manifest-only English`, (t) => {
        const context = fixture(t);
        writeFileSync(path.join(context.root, marker), '');
        const result = context.run('export');
        assert.notEqual(result.status, 0);
        assert.equal(existsSync(path.join(context.root, 'generated output', 'ms-python.isort-new.xlf')), false);
    });
}

test('imports all 28 tables, overwrites generated translations, and preserves English source', (t) => {
    const context = fixture(t);
    writeFileSync(path.join(context.root, 'package.nls.de.json'), '{"description":"stale"}');
    const result = context.run('import');
    assert.equal(result.status, 0, result.stderr);
    assert.equal(
        readFileSync(path.join(context.root, 'package.nls.json'), 'utf8'),
        '{"description":"English source"}\n',
    );
    for (const locale of locales) {
        assert.deepEqual(JSON.parse(readFileSync(path.join(context.root, `package.nls.${locale}.json`))), {
            description: locale,
        });
        assert.deepEqual(JSON.parse(readFileSync(path.join(context.root, 'l10n', `bundle.l10n.${locale}.json`))), {
            'Open logs': locale,
        });
    }
    assert.equal(readdirSync(path.join(context.root, 'l10n')).length, 14);
});

test('imports into a clean checkout without making generated translations eligible for source control', (t) => {
    const context = fixture(t);
    writeFileSync(path.join(context.root, '.gitignore'), readFileSync(path.join(__dirname, '..', '.gitignore')));
    const init = spawnSync('git', ['init', '--quiet'], { cwd: context.root, encoding: 'utf8' });
    assert.equal(init.status, 0, init.stderr);
    const result = context.run('import');
    assert.equal(result.status, 0, result.stderr);
    const generated = locales.flatMap((locale) => [`package.nls.${locale}.json`, `l10n/bundle.l10n.${locale}.json`]);
    assert.ok(generated.every((file) => existsSync(path.join(context.root, file))));
    const ignored = spawnSync('git', ['check-ignore', '--stdin'], {
        cwd: context.root,
        encoding: 'utf8',
        input: [...generated, 'package.nls.json'].join('\n') + '\n',
    });
    assert.equal(ignored.status, 0, ignored.stderr);
    assert.deepEqual(new Set(ignored.stdout.trim().split(/\r?\n/)), new Set(generated));
});

for (const invalid of ['missing-runtime', 'missing-locale', 'empty-table', 'invalid-json']) {
    test(`rejects ${invalid} before changing existing translations`, (t) => {
        const context = fixture(t);
        const file = path.join(context.handback, 'bundle.l10n.zh-tw.json');
        if (invalid === 'missing-runtime') {
            for (const locale of locales) {
                rmSync(path.join(context.handback, `bundle.l10n.${locale}.json`));
            }
        } else if (invalid === 'missing-locale') {
            rmSync(file);
        } else {
            writeFileSync(file, invalid === 'empty-table' ? '{}' : '{');
        }
        const original = '{"description":"keep existing translation"}';
        writeFileSync(path.join(context.root, 'package.nls.de.json'), original);
        const result = context.run('import');
        assert.notEqual(result.status, 0);
        assert.equal(readFileSync(path.join(context.root, 'package.nls.de.json'), 'utf8'), original);
        assert.equal(existsSync(path.join(context.root, 'l10n')), false);
    });
}

test('reports missing translated output explicitly', (t) => {
    const context = fixture(t);
    rmSync(context.translated, { recursive: true });
    const result = context.run('import');
    assert.notEqual(result.status, 0);
    assert.match(result.stderr, /Translated output is unavailable/);
});
