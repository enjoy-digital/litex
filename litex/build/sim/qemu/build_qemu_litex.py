#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import shutil
import tarfile
import argparse
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path


QEMU_REF     = "v8.2.4"
QEMU_REPO    = "https://gitlab.com/qemu-project/qemu.git"
QEMU_TARGETS = "riscv32-softmmu,riscv64-softmmu"


def repo_root():
    return Path(__file__).resolve().parents[4]


def run(cmd, cwd=None, env=None):
    print("+ {}".format(" ".join(str(c) for c in cmd)), flush=True)
    subprocess.run([str(c) for c in cmd], cwd=cwd, check=True, env=env)


def git_env(src_dir):
    # Keep `git apply` from discovering a repository that *contains* the QEMU
    # source tree. When QEMU is extracted under build/ inside the LiteX checkout
    # (the default with --source=archive, which has no .git of its own), git
    # would otherwise resolve the patch's a/ b/ paths against the *outer* LiteX
    # repo root and silently "Skip" every file (and --check still returns 0, so
    # the patch looks applied while litex_sim.c is never created). Capping the
    # ceiling at src_dir's parent blocks discovery of any enclosing repo while
    # still letting --source=git use the QEMU checkout's own .git in src_dir.
    env     = os.environ.copy()
    ceiling = str(Path(src_dir).resolve().parent)
    current = env.get("GIT_CEILING_DIRECTORIES")
    env["GIT_CEILING_DIRECTORIES"] = ceiling if not current else ceiling + os.pathsep + current
    return env


def qemu_version(qemu_ref):
    return qemu_ref[1:] if qemu_ref.startswith("v") else qemu_ref


def qemu_archive_url(qemu_ref):
    return "https://download.qemu.org/qemu-{}.tar.xz".format(qemu_version(qemu_ref))


def is_qemu_source(src_dir):
    return (src_dir / "configure").exists() and (src_dir / "hw" / "riscv").exists()


def download_file(url, path):
    tmp_path = path.with_name(path.name + ".tmp")
    if tmp_path.exists():
        tmp_path.unlink()

    try:
        if shutil.which("curl"):
            run([
                "curl",
                "--silent",
                "--show-error",
                "--fail",
                "--location",
                "--retry", "5",
                "--retry-delay", "5",
                "--connect-timeout", "20",
                "--output", tmp_path,
                url,
            ])
        elif shutil.which("wget"):
            run([
                "wget",
                "--tries=5",
                "--timeout=20",
                "--output-document", tmp_path,
                url,
            ])
        else:
            request = urllib.request.Request(
                url,
                headers={"User-Agent": "LiteX-QEMU-CoSim/1.0"},
            )
            with urllib.request.urlopen(request, timeout=60) as response:
                with tmp_path.open("wb") as archive:
                    shutil.copyfileobj(response, archive)
        tmp_path.replace(path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink()
        raise


def download_archive(args):
    archive_path = args.archive_path
    if archive_path is None:
        archive_name = Path(urllib.parse.urlparse(args.archive_url).path).name
        if not archive_name:
            archive_name = "qemu-{}.tar.xz".format(qemu_version(args.qemu_ref))
        archive_path = args.install_dir / "downloads" / archive_name

    archive_path.parent.mkdir(parents=True, exist_ok=True)
    if not archive_path.exists():
        print("Downloading {} to {}.".format(args.archive_url, archive_path), flush=True)
        download_file(args.archive_url, archive_path)
    return archive_path.resolve()


def extract_archive(args, archive_path):
    tmp_dir = args.src_dir.parent / "{}-extract".format(args.src_dir.name)
    if tmp_dir.exists():
        shutil.rmtree(tmp_dir)
    tmp_dir.mkdir(parents=True)

    try:
        with tarfile.open(archive_path) as archive:
            members = archive.getmembers()
            for member in members:
                member_path = Path(member.name)
                if member_path.is_absolute() or ".." in member_path.parts:
                    raise SystemExit("{} contains unsafe path {}.".format(archive_path, member.name))
            archive.extractall(tmp_dir, members=members)

        roots = [path for path in tmp_dir.iterdir() if path.is_dir()]
        if len(roots) != 1:
            raise SystemExit("{} did not extract to a single source directory.".format(archive_path))
        shutil.move(str(roots[0]), args.src_dir)
    finally:
        if tmp_dir.exists():
            shutil.rmtree(tmp_dir)


def ensure_git_source(args):
    src_dir = args.src_dir
    if src_dir.exists():
        if not is_qemu_source(src_dir):
            raise SystemExit("{} exists but does not look like a QEMU source tree.".format(src_dir))
        if (src_dir / ".git").exists():
            if not args.no_update:
                run(["git", "fetch", "--tags", "--depth", "1", "origin", args.qemu_ref], cwd=src_dir)
            run(["git", "checkout", args.qemu_ref], cwd=src_dir)
            return
        else:
            raise SystemExit("{} exists but is not a git checkout.".format(src_dir))

    if args.no_clone:
        raise SystemExit("{} does not exist and --no-clone was used.".format(src_dir))

    src_dir.parent.mkdir(parents=True, exist_ok=True)
    run([
        "git", "clone",
        "--branch", args.qemu_ref,
        "--depth", "1",
        args.repo_url,
        src_dir,
    ])


def ensure_archive_source(args):
    src_dir = args.src_dir
    if src_dir.exists():
        if not is_qemu_source(src_dir):
            raise SystemExit("{} exists but does not look like a QEMU source tree.".format(src_dir))
        return

    if args.no_clone:
        raise SystemExit("{} does not exist and --no-clone was used.".format(src_dir))

    src_dir.parent.mkdir(parents=True, exist_ok=True)
    extract_archive(args, download_archive(args))


def ensure_source(args):
    if args.source == "archive":
        ensure_archive_source(args)
    else:
        ensure_git_source(args)


def apply_patch(args):
    if args.no_patch:
        return

    env = git_env(args.src_dir)
    check_cmd = ["git", "apply", "--check", args.patch]
    reverse_check_cmd = ["git", "apply", "--reverse", "--check", args.patch]
    check = subprocess.run(
        [str(c) for c in check_cmd],
        cwd=args.src_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    if check.returncode == 0:
        run(["git", "apply", args.patch], cwd=args.src_dir, env=env)
        return

    reverse_check = subprocess.run(
        [str(c) for c in reverse_check_cmd],
        cwd=args.src_dir,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if reverse_check.returncode == 0:
        print("{} is already applied.".format(args.patch))
        return

    raise SystemExit(
        "Could not apply {}; QEMU tree is not at the expected state.\n{}\n{}".format(
            args.patch,
            check.stderr,
            reverse_check.stderr,
        )
    )


def configure_qemu(args, build_dir):
    build_dir.mkdir(parents=True, exist_ok=True)

    configure = args.src_dir / "configure"
    targets = [target.strip() for target in args.targets.split(",") if target.strip()]
    cmd = [
        configure,
        "--target-list={}".format(args.targets),
        "--prefix={}".format(args.install_dir),
        "--disable-werror",
        "--disable-docs",
        "--disable-tools",
        "--disable-gtk",
        "--disable-sdl",
        "--disable-vnc",
        "--disable-curses",
        "--disable-slirp",
        "--disable-guest-agent",
        "--disable-strip",
    ]
    if args.minimal_devices:
        cmd.append("--without-default-devices")
        for target in targets:
            arch = target.removesuffix("-softmmu")
            if arch.startswith("riscv"):
                cmd.append("--with-devices-{}=litex-sim".format(arch))
    if args.system_fdt:
        cmd.append("--enable-fdt=system")
    if args.disable_download:
        cmd.append("--disable-download")
    run(cmd, cwd=build_dir)


def build_qemu(args):
    build_dir = args.src_dir / "build-litex-sim"
    if args.reconfigure or not (build_dir / "build.ninja").exists():
        configure_qemu(args, build_dir)
    if args.no_build:
        return

    targets = [target.strip() for target in args.targets.split(",") if target.strip()]
    binaries = ["qemu-system-{}".format(target.removesuffix("-softmmu")) for target in targets]

    run(["ninja", "-C", build_dir, "-j{}".format(args.jobs), *binaries])

    bin_dir = args.install_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    for binary in binaries:
        src = build_dir / binary
        if not src.exists():
            raise SystemExit("{} was not built.".format(src))
        dst = bin_dir / binary
        shutil.copy2(src, dst)
        dst.chmod(dst.stat().st_mode | 0o111)
        print("Installed {}".format(dst))


def main():
    root = repo_root()
    qemu_dir = root / "build" / "qemu-litex"
    parser = argparse.ArgumentParser(description="Build QEMU with LiteX SIM co-simulation support.")
    parser.add_argument("--src-dir",     type=Path, default=qemu_dir / "src", help="QEMU source checkout.")
    parser.add_argument("--install-dir", type=Path, default=qemu_dir,         help="Install/copy destination.")
    parser.add_argument("--source",      default="git", choices=["git", "archive"], help="QEMU source provider.")
    parser.add_argument("--repo-url",    default=QEMU_REPO,                   help="QEMU git repository URL.")
    parser.add_argument("--qemu-ref",    default=QEMU_REF,                    help="QEMU branch/tag/commit to checkout.")
    parser.add_argument("--archive-url", default=None,                        help="QEMU source archive URL.")
    parser.add_argument("--archive-path", type=Path, default=None,            help="Local QEMU source archive.")
    parser.add_argument("--patch",       type=Path, default=Path(__file__).with_name("qemu-litex-sim-v8.2.4.patch"))
    parser.add_argument("--targets",     default=QEMU_TARGETS,                help="Comma-separated QEMU target list.")
    parser.add_argument("--jobs",        default=os.cpu_count() or 1, type=int, help="Parallel build jobs.")
    parser.add_argument("--no-clone",    action="store_true", help="Require --src-dir to already exist.")
    parser.add_argument("--no-update",   action="store_true", help="Do not fetch updates when --src-dir exists.")
    parser.add_argument("--no-patch",    action="store_true", help="Skip applying the LiteX QEMU patch.")
    parser.add_argument("--no-build",    action="store_true", help="Configure/patch only; do not run ninja.")
    parser.add_argument("--reconfigure", action="store_true", help="Run QEMU configure even if build.ninja exists.")
    parser.add_argument("--minimal-devices", action="store_true", help="Configure QEMU without default devices.")
    parser.add_argument("--system-fdt",  action="store_true", help="Require the system libfdt dependency.")
    parser.add_argument("--disable-download", action="store_true", help="Disable QEMU subproject downloads.")
    args = parser.parse_args()

    args.src_dir = args.src_dir.resolve()
    args.install_dir = args.install_dir.resolve()
    args.patch = args.patch.resolve()
    if args.archive_url is None:
        args.archive_url = qemu_archive_url(args.qemu_ref)
    if args.archive_path is not None:
        args.archive_path = args.archive_path.resolve()

    ensure_source(args)
    apply_patch(args)
    build_qemu(args)


if __name__ == "__main__":
    main()
