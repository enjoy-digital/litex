#!/usr/bin/env python3

import argparse
import importlib.metadata
import json
import os
import platform
import shlex
import subprocess
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def command_text(command):
    return shlex.join(str(part) for part in command)


def package_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return None


def git_value(*args):
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return result.stdout.strip() if result.returncode == 0 else None


def write_environment(output_dir):
    report = {
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": sys.version,
        "python_executable": sys.executable,
        "default_encoding": sys.getdefaultencoding(),
        "filesystem_encoding": sys.getfilesystemencoding(),
        "litex_version": package_version("litex"),
        "migen_version": package_version("migen"),
        "git_branch": git_value("branch", "--show-current"),
        "git_commit": git_value("rev-parse", "HEAD"),
    }
    path = output_dir / "environment.json"
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


def run_step(name, command, log_dir, required=True):
    print(f"\n== {name} ==")
    print(command_text(command))
    started = time.monotonic()
    result = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=os.environ.copy(),
    )
    duration = time.monotonic() - started
    log_path = log_dir / f"{name}.log"
    log_path.write_text(result.stdout, encoding="utf-8")
    if result.returncode == 0:
        status = "PASS"
    elif required:
        status = "FAIL"
    else:
        status = "OPTIONAL_FAIL"
    print(f"{status} ({duration:.2f}s), log: {log_path}")
    if result.returncode != 0:
        tail = result.stdout.splitlines()[-20:]
        if tail:
            print("\n".join(tail))
    return {
        "name": name,
        "command": command,
        "returncode": result.returncode,
        "duration_seconds": round(duration, 3),
        "log": str(log_path),
        "status": status,
        "required": required,
    }


def parse_args():
    parser = argparse.ArgumentParser(
        description="Run the LiteX core porting acceptance checks."
    )
    parser.add_argument(
        "--skip-pip-check",
        action="store_true",
        help="Skip pip dependency validation in constrained test environments.",
    )
    parser.add_argument(
        "--output-dir",
        default="build/acceptance",
        help="Directory for logs, generated artifacts, and JSON reports.",
    )
    parser.add_argument(
        "--skip-core-tests",
        action="store_true",
        help="Skip the 24-test portable core baseline.",
    )
    parser.add_argument(
        "--skip-minimal-soc",
        action="store_true",
        help="Skip export-only minimal SoC generation.",
    )
    return parser.parse_args()


def main():
    args = parse_args()
    output_dir = Path(args.output_dir).resolve()
    log_dir = output_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    environment = write_environment(output_dir)
    print(json.dumps(environment, indent=2))

    python = sys.executable
    steps = [
        (
            "imports",
            [python, "-c", "import litex, migen; print('LiteX and Migen import OK')"],
            True,
        ),
        ("litex-cli-help", [python, "-m", "litex.tools.litex_client", "--help"], True),
        # litex_sim imports optional ecosystem packages such as LiteEth. Keep
        # this visible in the report without making it a core-port blocker.
        ("litex-sim-help", [python, "-m", "litex.tools.litex_sim", "--help"], False),
    ]
    if not args.skip_pip_check:
        steps.insert(0, ("pip-check", [python, "-m", "pip", "check"], True))
    if not args.skip_core_tests:
        steps.append((
            "portable-core-tests",
            [
                python,
                "-m",
                "unittest",
                "-v",
                "test.cores.test_code_8b10b",
                "test.cores.test_ecc",
                "test.soc.test_export",
            ],
            True,
        ))
    if not args.skip_minimal_soc:
        steps.append((
            "minimal-soc",
            [
                python,
                str(ROOT / "examples" / "minimal_soc_baseline.py"),
                "--output-dir",
                str(output_dir / "minimal-soc"),
                "--clean",
            ],
            True,
        ))

    results = [
        run_step(name, command, log_dir, required=required)
        for name, command, required in steps
    ]
    passed = sum(result["status"] == "PASS" for result in results)
    required_results = [result for result in results if result["required"]]
    required_passed = sum(result["status"] == "PASS" for result in required_results)
    report = {
        "status": "PASS" if required_passed == len(required_results) else "FAIL",
        "passed": passed,
        "total": len(results),
        "required_passed": required_passed,
        "required_total": len(required_results),
        "environment": environment,
        "steps": results,
    }
    report_path = output_dir / "acceptance-report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(
        f"\nAcceptance: {report['status']} "
        f"({required_passed}/{len(required_results)} required steps passed; "
        f"{passed}/{len(results)} total steps passed)"
    )
    print(f"Report: {report_path}")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
