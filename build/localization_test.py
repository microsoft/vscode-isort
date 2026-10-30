# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.

"""Dependency-free regression tests for the localization helper."""

import json
import os
import pathlib
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

import localization


class LocalizationTests(unittest.TestCase):
    """Exercise export, clean imports, and invalid handbacks."""

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="isort localization ")
        self.addCleanup(self.temporary.cleanup)
        self.root = pathlib.Path(self.temporary.name)
        original_directory = pathlib.Path.cwd()
        os.chdir(self.root)
        self.addCleanup(os.chdir, original_directory)
        pathlib.Path("package.json").write_text(
            json.dumps({"publisher": "ms-python", "name": "isort", "l10n": "./l10n"}),
            encoding="utf-8",
        )
        pathlib.Path("package.nls.json").write_text(
            '{"description":"English source"}\n', encoding="utf-8"
        )
        self.translated = self.root / "translated output"
        self.translated.mkdir()
        (self.translated / "isort-new.xlf").write_text("<xliff/>", encoding="utf-8")
        self.handback = self.root / "handback"
        self.handback.mkdir()
        for locale in localization.LOCALES:
            for name, table in (
                (f"package.nls.{locale}.json", {"description": locale}),
                (f"bundle.l10n.{locale}.json", {"Open logs": locale}),
            ):
                (self.handback / name).write_text(json.dumps(table), encoding="utf-8")
        self.output = self.root / "generated output"
        self.real_cli = localization.run_cli
        patcher = mock.patch.object(localization, "run_cli", side_effect=self.cli)
        self.calls = patcher.start()
        self.addCleanup(patcher.stop)

    def cli(self, operation, _output_flag, output, *inputs):
        """Provide deterministic CLI output without installing npm dependencies."""
        output = pathlib.Path(output)
        if pathlib.Path("fail-cli").exists():
            raise subprocess.CalledProcessError(1, ["npx"])
        if operation == "export":
            if not pathlib.Path("missing-bundle").exists():
                bundle = (
                    {}
                    if pathlib.Path("empty-bundle").exists()
                    else {"Open logs": "Open logs"}
                )
                (output / "bundle.l10n.json").write_text(
                    json.dumps(bundle), encoding="utf-8"
                )
        elif operation == "generate-xlf":
            output.write_bytes(b"<xliff>\r\n</xliff>\r\n")
        elif operation == "import-xlf":
            for file in self.handback.glob("*.json"):
                shutil.copyfile(file, output / file.name)
        else:
            self.fail(f"Unexpected CLI operation: {operation}, {inputs}")

    def run_operation(self, operation):
        """Invoke the same argument parser used by CI."""
        localization.main(
            [
                "--operation",
                operation,
                "--output-directory",
                str(self.output),
                "--translations-path",
                str(self.translated),
            ]
        )

    def test_export(self):
        self.run_operation("export")
        self.assertEqual(
            self.calls.call_args_list[0].args[3:],
            ("./src", "./external/vscode-common-python-lsp/typescript/src"),
        )
        self.assertEqual(self.calls.call_args_list[1].args[-1], "package.nls.json")
        self.assertEqual(
            (self.output / "ms-python.isort-new.xlf").read_bytes(),
            b"<xliff>\n</xliff>\n",
        )

    def test_export_failures(self):
        for marker in ("missing-bundle", "empty-bundle", "fail-cli"):
            with self.subTest(marker=marker):
                pathlib.Path(marker).touch()
                with self.assertRaises(
                    (FileNotFoundError, ValueError, subprocess.CalledProcessError)
                ):
                    self.run_operation("export")
                self.assertFalse((self.output / "ms-python.isort-new.xlf").exists())
                shutil.rmtree(self.output)
                pathlib.Path(marker).unlink()

    def test_import(self):
        pathlib.Path("package.nls.de.json").write_text(
            '{"description":"stale"}', encoding="utf-8"
        )
        self.run_operation("import")
        self.assertEqual(
            pathlib.Path("package.nls.json").read_text(encoding="utf-8"),
            '{"description":"English source"}\n',
        )
        for locale in localization.LOCALES:
            self.assertEqual(
                localization.read_table(pathlib.Path(f"package.nls.{locale}.json")),
                {"description": locale},
            )
            self.assertEqual(
                localization.read_table(
                    pathlib.Path("l10n") / f"bundle.l10n.{locale}.json"
                ),
                {"Open logs": locale},
            )
        self.assertEqual(len(list(pathlib.Path("l10n").iterdir())), 14)

    def test_clean_import_is_ignored(self):
        shutil.copyfile(
            pathlib.Path(localization.__file__).parent.parent / ".gitignore",
            ".gitignore",
        )
        subprocess.run(["git", "init", "--quiet"], check=True)
        self.run_operation("import")
        generated = [
            name
            for locale in localization.LOCALES
            for name in (
                f"package.nls.{locale}.json",
                f"l10n/bundle.l10n.{locale}.json",
            )
        ]
        self.assertTrue(all(pathlib.Path(name).is_file() for name in generated))
        ignored = subprocess.run(
            ["git", "check-ignore", "-z", "--stdin"],
            input=("\0".join([*generated, "package.nls.json"]) + "\0").encode("utf-8"),
            check=True,
            capture_output=True,
        )
        self.assertEqual(
            set(ignored.stdout.decode("utf-8").rstrip("\0").split("\0")),
            set(generated),
        )

    def test_invalid_handbacks_preserve_existing_files(self):
        for invalid in (
            "missing-runtime",
            "missing-locale",
            "empty-table",
            "invalid-json",
        ):
            with self.subTest(invalid=invalid):
                files = list(self.handback.glob("bundle.l10n.*.json"))
                originals = {file: file.read_bytes() for file in files}
                file = self.handback / "bundle.l10n.zh-tw.json"
                if invalid == "missing-runtime":
                    for bundle in files:
                        bundle.unlink()
                elif invalid == "missing-locale":
                    file.unlink()
                else:
                    file.write_text(
                        "{}" if invalid == "empty-table" else "{", encoding="utf-8"
                    )
                original = '{"description":"keep existing translation"}'
                pathlib.Path("package.nls.de.json").write_text(
                    original, encoding="utf-8"
                )
                with self.assertRaises((FileNotFoundError, ValueError)):
                    self.run_operation("import")
                self.assertEqual(
                    pathlib.Path("package.nls.de.json").read_text(encoding="utf-8"),
                    original,
                )
                self.assertFalse(pathlib.Path("l10n").exists())
                shutil.rmtree(self.output)
                for file, content in originals.items():
                    file.write_bytes(content)

    def test_missing_handback(self):
        shutil.rmtree(self.translated)
        with self.assertRaisesRegex(
            FileNotFoundError, "Translated output is unavailable"
        ):
            self.run_operation("import")

    def test_existing_output_directory(self):
        self.output.mkdir()
        with self.assertRaises(FileExistsError):
            self.run_operation("import")

    def test_cli_pin(self):
        with mock.patch.object(localization.shutil, "which", return_value="npx.cmd"):
            with mock.patch.object(localization.subprocess, "run") as run:
                self.real_cli("export", "-o", "output")
        run.assert_called_once_with(
            ["npx.cmd", "--yes", "@vscode/l10n-dev@0.0.35", "export", "-o", "output"],
            check=True,
        )


if __name__ == "__main__":
    unittest.main()
