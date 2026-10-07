"""Reproduce the member-3 host-boundary checks from the LiteX repository root.

Run with PYTHONUTF8=1 and an environment containing the fixed LiteX/Migen
dependencies. This probes the current host, not a simulated HarmonyOS host.
Serial enumeration is read-only; no serial port is opened.
"""

import contextlib
import importlib.metadata
import io
import json
import locale
import os
from pathlib import Path
import platform
import sys
import tempfile
import traceback

ROOT = Path.cwd().resolve()
if not (ROOT / "litex" / "__init__.py").is_file():
    raise SystemExit("Run this script from the LiteX repository root.")
sys.path.insert(0, str(ROOT))

import litex
import migen
from migen import Signal
from litex.build.tools import subprocess_call_filtered, write_to_file
from litex.gen.sim.vcd import VCDWriter
from litex.soc.integration.builder import Builder

results = []


def check(name, fn, required=True):
    try:
        detail = fn()
        results.append(dict(name=name, status="PASS", required=required, detail=detail))
    except Exception:
        results.append(dict(name=name, status="FAIL" if required else "OPTIONAL_FAIL",
                            required=required, traceback=traceback.format_exc()))


def vcd_files():
    cwd = Path.cwd()
    paths = []
    with tempfile.TemporaryDirectory(prefix="litex-core-vcd-") as directory:
        try:
            os.chdir(directory)
            for filename in (Path("relative.vcd"), Path(directory) / "中文 空格" / "trace.vcd"):
                filename.parent.mkdir(parents=True, exist_ok=True)
                signal = Signal(name_override="probe")
                writer = VCDWriter(str(filename))
                try:
                    writer.init([signal])
                    writer.set(signal, 1)
                    writer.delay(3)
                finally:
                    writer.close()
                text = filename.read_text(encoding="utf-8")
                assert "$var wire 1 ! probe $end" in text and "1!" in text and "#3" in text
                assert writer.buffer_file.closed and writer.out_file.closed
                filename.unlink()
                paths.append(str(filename))
        finally:
            os.chdir(cwd)
    assert not Path(directory).exists()
    return dict(paths=paths, temp_root=tempfile.gettempdir(), handles_closed=True, cleanup=True)


def text_paths():
    with tempfile.TemporaryDirectory(prefix="litex-core-text-") as directory:
        target = Path(directory) / "中文 空格" / "csr.txt"
        Builder._export_write(str(target), "鸿蒙 CSR\n")
        assert target.read_text(encoding="utf-8") == "鸿蒙 CSR\n"
        before = target.stat().st_mtime_ns
        write_to_file(str(target), "鸿蒙 CSR\n")
        assert target.stat().st_mtime_ns == before
        target.unlink()
    return dict(nested_unicode_path=True, utf8_roundtrip=True, unchanged_file_not_rewritten=True)


def denied_write():
    if os.name != "posix" or os.geteuid() == 0:
        return dict(exercised=False, reason="Requires an unprivileged POSIX process")
    with tempfile.TemporaryDirectory(prefix="litex-core-permissions-") as directory:
        readonly = Path(directory) / "readonly"
        readonly.mkdir()
        readonly.chmod(0o500)
        try:
            try:
                Builder._export_write(str(readonly / "csr.json"), "{}")
            except PermissionError:
                return dict(exercised=True, permission_error_propagated=True)
            raise AssertionError("Expected PermissionError for the read-only output directory")
        finally:
            readonly.chmod(0o700)


def child_process():
    capture = io.StringIO()
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    with contextlib.redirect_stdout(capture):
        code = subprocess_call_filtered(
            [sys.executable, "-c", "import sys; print(sys.argv[1]); sys.exit(7)", "鸿蒙 空格"],
            [], env=env,
        )
    assert code == 7 and capture.getvalue().strip() == "鸿蒙 空格"
    return dict(argv_preserved=True, unicode_stdout=True, child_returncode=code)


def serial_enumeration():
    from serial.tools import list_ports
    ports = list(list_ports.comports())
    return dict(backend=list_ports.comports.__module__, count=len(ports), port_opened=False)


check("vcd_tempfile_and_cleanup", vcd_files)
check("builder_unicode_path_and_encoding", text_paths)
check("builder_write_permission", denied_write)
check("filtered_subprocess_argv_and_exit", child_process)
check("serial_enumeration_only", serial_enumeration, required=False)
report = dict(
    platform=platform.platform(), system=platform.system(), sys_platform=sys.platform,
    os_name=os.name, python=sys.version, executable=sys.executable,
    locale_encoding=locale.getpreferredencoding(False), utf8_mode=sys.flags.utf8_mode,
    temp_directory=tempfile.gettempdir(), litex_source=litex.__file__, migen_source=migen.__file__,
    packages={name: importlib.metadata.version(name) for name in ("litex", "migen", "pyserial")},
    checks=results,
)
print(json.dumps(report, indent=2, ensure_ascii=False))
raise SystemExit(any(item["status"] == "FAIL" for item in results))
