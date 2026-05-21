#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import json
import tarfile
import tempfile
import unittest
from types import SimpleNamespace

from litex.build.bundle import BuildBundle
from litex.tools.litex_build_bundle import create_bundle, run_local


class TestBuildBundle(unittest.TestCase):
    def test_bundle_archives_roots_and_sidecar_manifest(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = os.path.join(tmp_dir, "project")
            out  = os.path.join(root, "build")
            os.makedirs(os.path.join(root, "rtl"))
            os.makedirs(os.path.join(root, "__pycache__"))
            os.makedirs(out)
            src = os.path.join(root, "rtl", "top.v")
            skipped_cache = os.path.join(root, "__pycache__", "top.pyc")
            skipped_out   = os.path.join(out, "product.bit")
            with open(src, "w", encoding="utf-8") as f:
                f.write("module top(); endmodule\n")
            with open(skipped_cache, "w", encoding="utf-8") as f:
                f.write("cache")
            with open(skipped_out, "w", encoding="utf-8") as f:
                f.write("output")

            bundle = BuildBundle(output_dir=out, command=["target.py", "--build"])
            bundle.add_root(root, role="project")
            result = bundle.create()

            self.assertTrue(os.path.exists(result["archive"]))
            self.assertTrue(os.path.exists(result["manifest"]))

            with open(result["manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["format"], "litex-build-bundle-v1")
            self.assertEqual(manifest["command"], ["target.py", "--build"])

            paths = {entry["path"] for entry in manifest["files"]}
            self.assertIn(src, paths)
            self.assertNotIn(skipped_cache, paths)
            self.assertNotIn(skipped_out, paths)

            by_path = {entry["path"]: entry for entry in manifest["files"]}
            with tarfile.open(result["archive"], "r:gz") as archive:
                names = archive.getnames()
            self.assertIn("manifest.json", names)
            self.assertIn(by_path[src]["archive_path"], names)

    def test_bundle_records_standalone_files_and_roles(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = os.path.join(tmp_dir, "build")
            source = os.path.join(tmp_dir, "source.v")
            with open(source, "w", encoding="utf-8") as f:
                f.write("module source(); endmodule\n")

            bundle = BuildBundle(output_dir=output_dir)
            bundle.add_path(source, role="gateware_source")
            bundle.add_path(source, role="bundle_include")
            result = bundle.create()

            with open(result["manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(len(manifest["files"]), 1)
            self.assertEqual(manifest["files"][0]["roles"], ["bundle_include", "gateware_source"])

    def test_bundle_strict_mode_rejects_missing_inputs(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            bundle = BuildBundle(output_dir=os.path.join(tmp_dir, "build"), strict="error")
            bundle.add_path(os.path.join(tmp_dir, "missing.v"), role="gateware_source")

            with self.assertRaisesRegex(OSError, "Missing build bundle input"):
                bundle.create()

    def test_bundle_utility_replays_command_from_archive(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = os.path.join(tmp_dir, "project")
            replay  = os.path.join(tmp_dir, "replay")
            os.makedirs(project)
            script = os.path.join(project, "target.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write("open('ran.txt', 'w').write('ok')\n")

            args = SimpleNamespace(
                output     = None,
                output_dir = os.path.join(tmp_dir, "build"),
                root       = [project],
                include    = [],
                env        = [],
                strict     = "warn",
                command    = [sys.executable, script],
            )
            result = create_bundle(args)

            self.assertEqual(run_local(result["archive"], work_dir=replay), 0)

            with open(result["manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            root_extract = os.path.join(replay, "src", manifest["roots"][0]["archive_path"])
            self.assertTrue(os.path.exists(os.path.join(root_extract, "ran.txt")))


if __name__ == "__main__":
    unittest.main()
