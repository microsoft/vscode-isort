# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Export English localization inputs or import release translation handbacks."""

import argparse
import json
import pathlib
import shutil
import subprocess

LOCALES = (
    "cs",
    "de",
    "es",
    "fr",
    "it",
    "ja",
    "ko",
    "pl",
    "pt-br",
    "qps-ploc",
    "ru",
    "tr",
    "zh-cn",
    "zh-tw",
)


def run_cli(*arguments: str) -> None:
    """Run the pinned localization CLI through the configured npm feed."""
    executable = shutil.which("npx")
    if executable is None:
        raise FileNotFoundError("npx is required to run the localization CLI.")
    subprocess.run(
        [executable, "--yes", "@vscode/l10n-dev@0.0.35", *arguments],
        check=True,
    )


def read_table(path: pathlib.Path) -> dict:
    """Read a nonempty localization string table."""
    strings = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(strings, dict) or not strings:
        raise ValueError(
            f"The translated string table is invalid or empty: {path.name}"
        )
    return strings


def main(argv=None) -> None:
    """Run from the extension root, keeping generated files out of source control."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--operation", choices=("export", "import"), required=True)
    parser.add_argument("--output-directory", type=pathlib.Path, required=True)
    parser.add_argument("--translations-path", type=pathlib.Path)
    args = parser.parse_args(argv)
    package = json.loads(pathlib.Path("package.json").read_text(encoding="utf-8"))
    extension_id = f"{package.get('publisher')}.{package.get('name')}"
    if extension_id != "ms-python.isort" or package.get("l10n") != "./l10n":
        raise ValueError(
            "Expected the isort extension with its ./l10n runtime localization directory."
        )
    output = args.output_directory
    if output.exists():
        raise FileExistsError(f"Output directory must be a new directory: {output}")
    output.mkdir(parents=True)

    if args.operation == "export":
        run_cli(
            "export",
            "-o",
            str(output),
            "./src",
            "./external/vscode-common-python-lsp/typescript/src",
        )
        bundle = output / "bundle.l10n.json"
        if not bundle.is_file():
            raise FileNotFoundError(
                "No runtime localization bundle was generated. "
                "Check extension and shared submodule sources."
            )
        read_table(bundle)
        xlf = output / f"{extension_id}-new.xlf"
        run_cli("generate-xlf", "-o", str(xlf), str(bundle), "package.nls.json")
        if not xlf.is_file():
            raise FileNotFoundError("English XLF generation produced no file.")
        content = xlf.read_text(encoding="utf-8-sig")
        with xlf.open("w", encoding="utf-8", newline="\n") as destination:
            destination.write(content)
        return

    if args.translations_path is None or not args.translations_path.is_dir():
        raise FileNotFoundError(
            "Translated output is unavailable. Run the Localization workflow to "
            "submit English strings and wait for the localization backend."
        )
    files = sorted(
        file for file in args.translations_path.rglob("*-new.xlf") if file.is_file()
    )
    if not files:
        raise FileNotFoundError(
            "No translated XLF files are available. "
            "Wait for the localization backend before importing translations."
        )
    run_cli("import-xlf", "-o", str(output), *(str(file) for file in files))
    names = [
        name
        for locale in LOCALES
        for name in (f"package.nls.{locale}.json", f"bundle.l10n.{locale}.json")
    ]
    for name in names:
        file = output / name
        if not file.is_file():
            raise FileNotFoundError(
                f"Incomplete translation handback: missing {name}. "
                "Wait for the localization backend to translate "
                "both manifest and runtime strings."
            )
        read_table(file)
    runtime = pathlib.Path(package["l10n"])
    runtime.mkdir(parents=True, exist_ok=True)
    for name in names:
        destination = pathlib.Path(".") if name.startswith("package.nls.") else runtime
        shutil.copyfile(output / name, destination / name)


if __name__ == "__main__":
    main()
