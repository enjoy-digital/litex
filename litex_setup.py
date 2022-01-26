#!/usr/bin/env python3

import os
import sys
import time
import subprocess
import shutil
import hashlib
import argparse

import urllib.request

start_time   = time.time()
current_path = os.path.abspath(os.curdir)
python3      = sys.executable

# Helpers ------------------------------------------------------------------------------------------

def colorer(s, color="bright"): # FIXME: Move colorer to litex.common?
    header  = {
        "bright"    : "\x1b[1m",
        "green"     : "\x1b[1m\x1b[32m",
        "cyan"      : "\x1b[1m\x1b[36m",
        "red"       : "\x1b[1m\x1b[31m",
        "yellow"    : "\x1b[1m\x1b[33m",
        "underline" : "\x1b[1m\x1b[4m"}[color]
    trailer = "\x1b[0m"
    return header + str(s) + trailer

def print_banner():
    b  = []
    b.append("          __   _ __      _  __         ")
    b.append("         / /  (_) /____ | |/_/         ")
    b.append("        / /__/ / __/ -_)>  <           ")
    b.append("       /____/_/\\__/\\__/_/|_|         ")
    b.append("     Build your hardware, easily!      ")
    b.append("          LiteX Setup utility.         ")
    b.append("")
    print("\n".join(b))

def print_status(status, underline=False):
    exec_time = (time.time() - start_time)
    print(colorer(f"[{exec_time:8.3f}]", color="green") + " " + colorer(status))
    if underline:
        print(colorer(f"[{exec_time:8.3f}]", color="green") + " " + colorer("-"*len(status)))

def print_error(status):
    exec_time = (time.time() - start_time)
    print(colorer(f"[{exec_time:8.3f}]", color="red") + " " + colorer(status))

class SetupError(Exception):
    def __init__(self):
        sys.stderr = None # Error already described, avoid traceback/exception.

# Git repositories ---------------------------------------------------------------------------------

# Get SHA1: git rev-parse --short=7 HEAD

class GitRepo:
    def __init__(self, url, clone="regular", develop=True, sha1=None, branch="master"):
        assert clone in ["regular", "recursive"]
        self.url     = url
        self.clone   = clone
        self.develop = develop
        self.sha1    = sha1
        self.branch  = branch

git_repos = {
    # HDL.
    "migen":    GitRepo(url="https://github.com/m-labs/", clone="recursive"),
    "amaranth": GitRepo(url="https://github.com/amaranth-lang/", branch="main"),

    # LiteX SoC builder
    "pythondata-software-picolibc":    GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-software-compiler_rt": GitRepo(url="https://github.com/litex-hub/"),
    "litex":                           GitRepo(url="https://github.com/enjoy-digital/"),

    # LiteX Cores Ecosystem.
    "liteeth":      GitRepo(url="https://github.com/enjoy-digital/"),
    "litedram":     GitRepo(url="https://github.com/enjoy-digital/"),
    "litepcie":     GitRepo(url="https://github.com/enjoy-digital/"),
    "litesata":     GitRepo(url="https://github.com/enjoy-digital/"),
    "litesdcard":   GitRepo(url="https://github.com/enjoy-digital/"),
    "liteiclink":   GitRepo(url="https://github.com/enjoy-digital/"),
    "litescope":    GitRepo(url="https://github.com/enjoy-digital/"),
    "litejesd204b": GitRepo(url="https://github.com/enjoy-digital/"),
    "litespi":      GitRepo(url="https://github.com/litex-hub/"),
    "litehyperbus": GitRepo(url="https://github.com/litex-hub/"),

    # LiteX Boards.
    "litex-boards": GitRepo(url="https://github.com/litex-hub/", clone="regular"),

    # LiteX pythondata.
    "pythondata-misc-tapcfg":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-misc-usb_ohci":    GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-lm32":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-mor1kx":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-picorv32":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-serv":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexriscv":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexriscv-smp": GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-rocket":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-minerva":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-microwatt":    GitRepo(url="https://github.com/litex-hub/", sha1=0xdad611c),
    "pythondata-cpu-blackparrot":  GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-cv32e40p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-ibex":         GitRepo(url="https://github.com/litex-hub/", clone="recursive", sha1=0xd3d53df),
    "pythondata-cpu-marocchino":   GitRepo(url="https://github.com/litex-hub/"),
}

# Installs -----------------------------------------------------------------------------------------

# Minimal: Only Migen + LiteX.
minimal_repos = ["migen", "litex"]

# Standard: Migen + LiteX + Cores + Software + Popular CPUs (LM32, Mor1kx, SERV, VexRiscv).
standard_repos = list(git_repos.keys())
standard_repos.remove("amaranth")
standard_repos.remove("pythondata-cpu-picorv32")
standard_repos.remove("pythondata-cpu-rocket")
standard_repos.remove("pythondata-cpu-minerva")
standard_repos.remove("pythondata-cpu-microwatt")
standard_repos.remove("pythondata-cpu-blackparrot")
standard_repos.remove("pythondata-cpu-cv32e40p")
standard_repos.remove("pythondata-cpu-ibex")
standard_repos.remove("pythondata-cpu-marocchino")

# Full: Migen + LiteX + Cores + Software + All CPUs.
full_repos = list(git_repos.keys())


# Installs:
install_configs = {
    "minimal"  : minimal_repos,
    "standard" : standard_repos,
    "full"     : full_repos,
}

# Script location / auto-update --------------------------------------------------------------------

def litex_setup_location_check():
    # Check if script is executed inside a cloned LiteX repository or alongside?
    if os.path.exists(".gitignore"):
        global current_path
        current_path = os.path.join(current_path, "../")

def litex_setup_auto_update():
    litex_setup_url = "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py"
    current_sha1 = hashlib.sha1(open(os.path.realpath(__file__)).read().encode("utf-8")).hexdigest()
    print_status("LiteX Setup auto-update...")
    try:
        import requests
        r = requests.get(litex_setup_url)
        if r.status_code != 404:
            upstream_sha1 = hashlib.sha1(r.content).hexdigest()
            if current_sha1 != upstream_sha1:
                print_status("LiteX Setup is obsolete, updating.")
                with open(os.path.realpath(__file__), "wb") as f:
                    f.write(r.content)
                os.execl(python3, python3, *sys.argv)
            else:
                print_status("LiteX Setup is up to date.")
    except:
        pass

# Git repositories initialization ------------------------------------------------------------------

def litex_setup_init_repos(config="standard", dev_mode=False):
    print_status("Initializing Git repositories...", underline=True)
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        if not os.path.exists(name):
            # Clone Repo.
            print_status(f"Cloning {name} Git repository...")
            repo_url = repo.url
            if dev_mode:
                repo_url = repo_url.replace("https://github.com/", "git@github.com:")
            subprocess.check_call("git clone {url} {options}".format(
                url     = repo_url + name + ".git",
                options = "--recursive" if repo.clone == "recursive" else ""
                ), shell=True)
            # Use specific SHA1 (Optional).
            if repo.sha1 is not None:
                os.chdir(os.path.join(current_path, name))
                os.system(f"git checkout {repo.sha1:07x}")
        else:
            print_status(f"{name} Git Repo already present.")

# Git repositories update --------------------------------------------------------------------------

def litex_setup_update_repos(config="standard"):
    print_status("Updating Git repositories...", underline=True)
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        # Check if Repo is present.
        if not os.path.exists(name):
            print_error(f"{name} Git repository is not initialized, please run --init first.")
            raise SetupError
        # Update Repo.
        print_status(f"Updating {name} Git repository...")
        os.chdir(os.path.join(current_path, name))
        subprocess.check_call("git checkout " + repo.branch, shell=True)
        subprocess.check_call("git pull --ff-only", shell=True)
        # Recursive Update (Optional).
        if repo.clone == "recursive":
            subprocess.check_call("git submodule update --init --recursive", shell=True)
        # Use specific SHA1 (Optional).
        if repo.sha1 is not None:
            os.chdir(os.path.join(current_path, name))
            os.system(f"git checkout {repo.sha1:07x}")

# Git repositories install -------------------------------------------------------------------------

def litex_setup_install_repos(config="standard", user_mode=False):
    print_status("Installing Git repositories...", underline=True)
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        # Install Repo.
        if repo.develop:
            print_status(f"Installing {name} Git repository...")
            os.chdir(os.path.join(current_path, name))
            subprocess.check_call("{python3} setup.py develop {options}".format(
                python3 = sys.executable,
                options = "--user" if user_mode else "",
                ), shell=True)
    if user_mode:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print_status("Make sure that ~/.local/bin is in your PATH")
            print_status("export PATH=$PATH:~/.local/bin")

# Git repositories status --------------------------------------------------------------------------

def litex_setup_status_repos(config="standard"):
    print_status("Getting status of Git repositories...", underline=True)
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path, name))
        git_sha1_cmd = ["git", "rev-parse", "--short=7", "HEAD"]
        git_sha1     = subprocess.check_output(git_sha1_cmd).decode("UTF-8")
        print(f"{name}: sha1=0x{git_sha1}", end="")

# GCC toolchains download --------------------------------------------------------------------------

def gcc_toolchain_download(url, filename):
    print_status("Downloading GCC toolchain...", underline=True)
    if not os.path.exists(filename):
        full_url = url + filename
        print_status(f"Downloading {full_url} to {filename}...")
        urllib.request.urlretrieve(full_url, filename)
    else:
        print_status(f"Using existing file {filename}.")

    print_status(f"Extracting {filename}...")
    shutil.unpack_archive(filename)

# RISC-V toolchain.
# -----------------

def riscv_gcc_toolchain_download():
    base_url  = "https://static.dev.sifive.com/dev-tools/"
    base_file = "riscv64-unknown-elf-gcc-8.3.0-2019.08.0-x86_64-"

    # Windows
    if (sys.platform.startswith("win") or sys.platform.startswith("cygwin")):
        end_file = "w64-mingw32.zip"
    # Linux
    elif sys.platform.startswith("linux"):
        os_release = (open("/etc/os-release").read()).lower()
        if "fedora" in os_release:
            end_file = "linux-centos6.tar.gz"
        else:
            end_file = "linux-ubuntu14.tar.gz"

    # Mac OS
    elif sys.platform.startswith("darwin"):
        end_file = "apple-darwin.tar.gz"
    else:
        raise NotImplementedError(sys.platform)

    # Download/Extract.
    gcc_toolchain_download(url=base_url, filename=base_file + end_file)

# PowerPC toolchain download.
# ---------------------------

def powerpc_gcc_toolchain_download():
    base_url  = "https://toolchains.bootlin.com/downloads/releases/toolchains/powerpc64le-power8/tarballs/"
    base_file = "powerpc64le-power8--musl--stable-2020.08-1.tar.bz2"

    # Download/Extract.
    gcc_toolchain_download(url=base_url, filename=base_file)

# OpenRISC toolchain download.
# ----------------------------

def openrisc_gcc_toolchain_download():
    base_url  = "https://toolchains.bootlin.com/downloads/releases/toolchains/openrisc/tarballs/"
    base_file = "openrisc--musl--stable-2020.08-1.tar.bz2"

    # Download/Extract.
    gcc_toolchain_download(url=base_url, filename=base_file)

# LM32 toolchain download.

def lm32_gcc_toolchain_download():
    base_url  = ""
    base_file = ""

    raise NotImplementedError

# Run ----------------------------------------------------------------------------------------------

def main():
    print_banner()
    parser = argparse.ArgumentParser()

    # Git Repositories.
    parser.add_argument("--init",      action="store_true", help="Initialize Git repositories.")
    parser.add_argument("--update",    action="store_true", help="Update Git repositories.")
    parser.add_argument("--install",   action="store_true", help="Install Git repositories.")
    parser.add_argument("--user",      action="store_true", help="Install in User-Mode.")
    parser.add_argument("--config",    default="standard",  help="Install config (minimal, standard, full).")
    parser.add_argument("--status",    action="store_true", help="Display Git status of repositories.")

    # GCC toolchains.
    parser.add_argument("--gcc", default=None, help="Download/Extract GCC Toolchain (riscv, powerpc, openrisc or lm32).")

    # Development mode.
    parser.add_argument("--dev", action="store_true", help="Development-Mode (no Auto-Update of litex_setup.py / Switch to git@github.com URLs).")

    # Retro-compatibility.
    parser.add_argument("compat_args", nargs="*", help="Retro-Compatibility arguments (init, update, install or gcc).")
    args = parser.parse_args()

    # Handle compat_args.
    if args.compat_args is not None:
        for arg in args.compat_args:
            if arg in ["init", "update", "install"]:
                setattr(args, arg, True)
            if arg in ["gcc"]:
                args.gcc = "riscv"

    # Location/Auto-Update.
    litex_setup_location_check()
    if not args.dev:
        litex_setup_auto_update()

    # Init.
    if args.init:
        litex_setup_init_repos(config=args.config, dev_mode=args.dev)

    # Update.
    if args.update:
        litex_setup_update_repos(config=args.config)

    # Install.
    if args.install:
        litex_setup_install_repos(config=args.config, user_mode=args.user)

    # Status.
    if args.status:
        litex_setup_status_repos(config=args.config)

    # GCC.
    os.chdir(os.path.join(current_path))
    if args.gcc == "riscv":
        riscv_gcc_toolchain_download()
    if args.gcc == "powerpc":
        powerpc_gcc_toolchain_download()
    if args.gcc == "openrisc":
        openrisc_gcc_toolchain_download()
    if args.gcc == "lm32":
        lm32_gcc_toolchain_download()

if __name__ == "__main__":
    main()
