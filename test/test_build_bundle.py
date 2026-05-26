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
from unittest.mock import patch

from litex.build.bundle import BuildBundle, remap_path
from litex.build.generic_platform import GenericPlatform
from litex.tools.litex_build_bundle import create_bundle, run_local
from litex.tools.litex_remote_build import _remote_shell_path
from litex.tools.litex_remote_build import main as remote_build_main


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

    def test_bundle_records_directory_inputs_for_replay_mapping(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_dir = os.path.join(tmp_dir, "build")
            source_dir = os.path.join(tmp_dir, "sources")
            os.makedirs(source_dir)
            source = os.path.join(source_dir, "source.v")
            with open(source, "w", encoding="utf-8") as f:
                f.write("module source(); endmodule\n")

            bundle = BuildBundle(output_dir=output_dir)
            bundle.add_path(source_dir, role="gateware_source")
            bundle.add_path(source_dir, role="bundle_include")
            result = bundle.create()

            with open(result["manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(len(manifest["input_dirs"]), 1)
            self.assertEqual(manifest["input_dirs"][0]["path"], source_dir)
            self.assertEqual(manifest["input_dirs"][0]["roles"], ["bundle_include", "gateware_source"])

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
                output             = None,
                output_dir         = os.path.join(tmp_dir, "build"),
                root               = [project],
                include            = [],
                pythonpath_root    = [],
                no_auto_pythonpath = True,
                env                = [],
                strict             = "warn",
                command            = [sys.executable, script],
            )
            result = create_bundle(args)

            self.assertEqual(run_local(result["archive"], work_dir=replay), 0)

            with open(result["manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            root_extract = os.path.join(replay, "src", manifest["roots"][0]["archive_path"])
            self.assertTrue(os.path.exists(os.path.join(root_extract, "ran.txt")))

    def test_bundle_utility_replays_standalone_command_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            replay = os.path.join(tmp_dir, "replay")
            script = os.path.join(tmp_dir, "target.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write("open('ran.txt', 'w').write('ok')\n")

            bundle = BuildBundle(output_dir=os.path.join(tmp_dir, "build"), command=[sys.executable, script])
            bundle.add_path(script, role="command")
            result = bundle.create()

            self.assertEqual(run_local(result["archive"], work_dir=replay), 0)
            self.assertTrue(os.path.exists(os.path.join(replay, "src", "ran.txt")))

    def test_bundle_utility_replays_pythonpath_roots(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project = os.path.join(tmp_dir, "project")
            deps    = os.path.join(tmp_dir, "deps")
            replay  = os.path.join(tmp_dir, "replay")
            os.makedirs(project)
            os.makedirs(os.path.join(deps, "helper"))
            with open(os.path.join(deps, "helper", "__init__.py"), "w", encoding="utf-8") as f:
                f.write("VALUE = 'imported'\n")
            script = os.path.join(project, "target.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write("import os\n")
                f.write("from helper import VALUE\n")
                f.write("open('result.txt', 'w').write(VALUE + ':' + os.environ['LITEX_BUILD_BUNDLE_REPLAY'])\n")

            args = SimpleNamespace(
                output             = None,
                output_dir         = os.path.join(tmp_dir, "build"),
                root               = [project],
                include            = [],
                pythonpath_root    = [deps],
                no_auto_pythonpath = True,
                env                = [],
                strict             = "warn",
                command            = [sys.executable, script],
            )
            result = create_bundle(args)

            self.assertEqual(run_local(result["archive"], work_dir=replay), 0)

            with open(result["manifest"], encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual([root["path"] for root in manifest["pythonpath"]], [deps])
            root_extract = os.path.join(replay, "src", manifest["roots"][0]["archive_path"])
            with open(os.path.join(root_extract, "result.txt"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "imported:1")

    def test_replay_path_map_remaps_platform_sources(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            source_root = os.path.join(tmp_dir, "source")
            mapped_root = os.path.join(tmp_dir, "mapped")
            standalone  = os.path.join(tmp_dir, "external.v")
            mapped_file = os.path.join(tmp_dir, "files", "external.v")
            os.makedirs(os.path.join(source_root, "include"))
            os.makedirs(mapped_root)
            path_map = [
                {
                    "kind"  : "root",
                    "path"  : source_root,
                    "mapped": mapped_root,
                },
                {
                    "kind"  : "file",
                    "path"  : standalone,
                    "mapped": mapped_file,
                },
            ]

            with patch.dict(os.environ, {"LITEX_BUILD_BUNDLE_PATH_MAP": json.dumps(path_map)}):
                platform = GenericPlatform("", [])
                platform.add_source(os.path.join(source_root, "rtl.v"))
                platform.add_source(standalone)
                platform.add_verilog_include_path(os.path.join(source_root, "include"))

            self.assertEqual(platform.sources[0][0], os.path.join(mapped_root, "rtl.v"))
            self.assertEqual(platform.sources[1][0], mapped_file)
            self.assertEqual(platform.verilog_include_paths[0], os.path.join(mapped_root, "include"))
            self.assertEqual(remap_path("relative.v"), "relative.v")

    def test_remote_shell_path_preserves_home_expansion(self):
        self.assertEqual(_remote_shell_path("~"), "~")
        self.assertEqual(_remote_shell_path("~/.cache/litex"), "~/.cache/litex")
        self.assertEqual(_remote_shell_path("~/remote build/job"), "~/'remote build/job'")
        self.assertEqual(_remote_shell_path("/tmp/remote build/job"), "'/tmp/remote build/job'")
        self.assertEqual(_remote_shell_path("~user/remote-builds"), "'~user/remote-builds'")

    def test_remote_build_works_with_local_fake_transport(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            project     = os.path.join(tmp_dir, "project")
            deps        = os.path.join(tmp_dir, "deps")
            remote_root = "~/remote build"
            fake_ssh    = os.path.join(tmp_dir, "fake_ssh.py")
            fake_scp    = os.path.join(tmp_dir, "fake_scp.py")
            os.makedirs(project)
            os.makedirs(os.path.join(deps, "helper"))
            with open(os.path.join(deps, "helper", "__init__.py"), "w", encoding="utf-8") as f:
                f.write("VALUE = 'remote-ok'\n")

            script = os.path.join(project, "target.py")
            with open(script, "w", encoding="utf-8") as f:
                f.write("import os\n")
                f.write("from helper import VALUE\n")
                f.write("os.makedirs('build', exist_ok=True)\n")
                f.write("open('build/remote.txt', 'w').write(VALUE)\n")

            with open(fake_ssh, "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("import os\n")
                f.write("import subprocess\n")
                f.write("import sys\n")
                f.write("args = sys.argv[1:]\n")
                f.write("if args and args[0] in ['-t', '-T']:\n")
                f.write("    args = args[1:]\n")
                f.write("env = os.environ.copy()\n")
                f.write("env.pop('PYTHONPATH', None)\n")
                f.write("sys.exit(subprocess.call(args[-1], shell=True, env=env))\n")
            os.chmod(fake_ssh, 0o755)

            with open(fake_scp, "w", encoding="utf-8") as f:
                f.write("#!/usr/bin/env python3\n")
                f.write("import os\n")
                f.write("import shutil\n")
                f.write("import sys\n")
                f.write("args = [arg for arg in sys.argv[1:] if arg != '-r']\n")
                f.write("src, dst = args[-2:]\n")
                f.write("def path(value):\n")
                f.write("    return value.split(':', 1)[1] if ':' in value and not value.startswith('/') else value\n")
                f.write("src = os.path.expanduser(path(src))\n")
                f.write("dst = os.path.expanduser(path(dst))\n")
                f.write("if os.path.isdir(src):\n")
                f.write("    if os.path.exists(dst):\n")
                f.write("        shutil.rmtree(dst)\n")
                f.write("    shutil.copytree(src, dst)\n")
                f.write("else:\n")
                f.write("    os.makedirs(os.path.dirname(dst), exist_ok=True)\n")
                f.write("    shutil.copy2(src, dst)\n")
            os.chmod(fake_scp, 0o755)

            argv = [
                "litex_remote_build",
                "--host", "fake",
                "--remote-root", remote_root,
                "--output-dir", os.path.join(project, "build"),
                "--root", project,
                "--pythonpath-root", deps,
                "--no-auto-pythonpath",
                "--ssh-cmd", fake_ssh,
                "--scp-cmd", fake_scp,
                "--",
                sys.executable,
                script,
            ]

            cwd = os.getcwd()
            os.chdir(project)
            try:
                with patch.dict(os.environ, {"HOME": tmp_dir}):
                    with patch.object(sys, "argv", argv):
                        with self.assertRaises(SystemExit) as cm:
                            remote_build_main()
            finally:
                os.chdir(cwd)

            self.assertEqual(cm.exception.code, 0)
            with open(os.path.join(project, "build", "remote.txt"), encoding="utf-8") as f:
                self.assertEqual(f.read(), "remote-ok")


if __name__ == "__main__":
    unittest.main()
