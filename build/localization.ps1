# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

param(
    [Parameter(Mandatory)]
    [ValidateSet('export', 'import')]
    [string] $Operation,
    [Parameter(Mandatory)]
    [string] $OutputDirectory,
    [string] $TranslationsPath
)

$ErrorActionPreference = 'Stop'
$PSNativeCommandUseErrorActionPreference = $true
$package = Get-Content -Raw -LiteralPath 'package.json' | ConvertFrom-Json
$extensionId = "$($package.publisher).$($package.name)"
if ($extensionId -ne 'ms-python.isort' -or $package.l10n -ne './l10n') {
    throw 'Expected the isort extension with its ./l10n runtime localization directory.'
}
if (Test-Path -LiteralPath $OutputDirectory) {
    throw "OutputDirectory must be a new directory: $OutputDirectory"
}
New-Item -ItemType Directory -Path $OutputDirectory -Force | Out-Null

if ($Operation -eq 'export') {
    npx --yes @vscode/l10n-dev@0.0.35 export -o $OutputDirectory ./src ./external/vscode-common-python-lsp/typescript/src
    $bundle = Join-Path $OutputDirectory 'bundle.l10n.json'
    if (!(Test-Path -LiteralPath $bundle -PathType Leaf)) {
        throw 'No runtime localization bundle was generated. Check extension and shared submodule sources.'
    }
    $strings = Get-Content -Raw -LiteralPath $bundle | ConvertFrom-Json -AsHashtable
    if ($strings.Count -eq 0) {
        throw 'The extracted runtime localization bundle is empty.'
    }
    $xlf = Join-Path $OutputDirectory "$extensionId-new.xlf"
    npx --yes @vscode/l10n-dev@0.0.35 generate-xlf -o $xlf $bundle package.nls.json
    if (!(Test-Path -LiteralPath $xlf -PathType Leaf)) {
        throw 'English XLF generation produced no file.'
    }
    $content = [IO.File]::ReadAllText($xlf).Replace("`r`n", "`n")
    [IO.File]::WriteAllText($xlf, $content, [Text.UTF8Encoding]::new($false))
    return
}

if (!$TranslationsPath -or !(Test-Path -LiteralPath $TranslationsPath -PathType Container)) {
    throw 'Translated output is unavailable. Run the Localization workflow to submit English strings and wait for the localization backend.'
}
$files = @(Get-ChildItem -LiteralPath $TranslationsPath -Recurse -Filter '*-new.xlf' -File |
    Select-Object -ExpandProperty FullName)
if ($files.Count -eq 0) {
    throw 'No translated XLF files are available. Wait for the localization backend before importing translations.'
}
npx --yes @vscode/l10n-dev@0.0.35 import-xlf -o $OutputDirectory @files

# Validate the complete handback before copying translations into the extension.
$locales = @('cs', 'de', 'es', 'fr', 'it', 'ja', 'ko', 'pl', 'pt-br', 'qps-ploc', 'ru', 'tr', 'zh-cn', 'zh-tw')
$names = foreach ($locale in $locales) {
    "package.nls.$locale.json"
    "bundle.l10n.$locale.json"
}
foreach ($name in $names) {
    $file = Join-Path $OutputDirectory $name
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Incomplete translation handback: missing $name. Wait for the localization backend to translate both manifest and runtime strings."
    }
    $strings = Get-Content -Raw -LiteralPath $file | ConvertFrom-Json -AsHashtable
    if ($strings -isnot [System.Collections.IDictionary] -or $strings.Count -eq 0) {
        throw "The translated string table is invalid or empty: $name"
    }
}
New-Item -ItemType Directory -Path $package.l10n -Force | Out-Null
foreach ($name in $names) {
    $destination = if ($name.StartsWith('package.nls.')) { '.' } else { $package.l10n }
    Copy-Item -LiteralPath (Join-Path $OutputDirectory $name) -Destination $destination -Force
}
