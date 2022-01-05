#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import hashlib
import argparse

import urllib.request

current_path = os.path.abspath(os.curdir)

# Git Repositories ---------------------------------------------------------------------------------

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
}

# Installs -----------------------------------------------------------------------------------------

# Minimal: Only Migen + LiteX.
minimal_repos = [
    "migen", "litex"
]

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

# Full: Migen + LiteX + Cores + Software + All CPUs.
full_repos = list(git_repos.keys())


# Installs:
install_configs = {
    "minimal"  : minimal_repos,
    "standard" : standard_repos,
    "full"     : full_repos,
}

# Script Location / Auto-Update --------------------------------------------------------------------

def litex_setup_location_check():
    # Check if script is executed inside a cloned LiteX repository or alongside?
    if os.path.exists(".gitignore"):
        global current_path
        current_path = os.path.join(current_path, "../")

def litex_setup_auto_update():
    litex_setup_url = "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py"
    current_sha1 = hashlib.sha1(open(os.path.realpath(__file__)).read().encode("utf-8")).hexdigest()
    print("[Checking litex_setup.py]...")
    try:
        import requests
        r = requests.get(litex_setup_url)
        if r.status_code != 404:
            upstream_sha1 = hashlib.sha1(r.content).hexdigest()
            if current_sha1 != upstream_sha1:
                print("[Updating litex_setup.py]...")
                with open(os.path.realpath(__file__), "wb") as f:
                    f.write(r.content)
                os.execl(sys.executable, sys.executable, *sys.argv)
    except:
        pass

# Repositories Initialization ----------------------------------------------------------------------

def litex_setup_init_repos(config="standard", dev_mode=False):
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        print(f"[Checking {name}]...")
        if not os.path.exists(name):
            # Clone Repo.
            print(f"[Cloning {name}]...")
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

# Repositories Update ------------------------------------------------------------------------------

def litex_setup_update_repos(config="standard"):
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        # Check if Repo is present.
        if not os.path.exists(name):
            raise Exception("{} not initialized, please (re)-run init and install first.".format(name))
        # Update Repo.
        print(f"[Updating {name}]...")
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

# Repositories Install -----------------------------------------------------------------------------

def litex_setup_install_repos(config="standard", user_mode=False):
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path))
        # Install Repo.
        if repo.develop:
            print(f"[Installing {name}]...")
            os.chdir(os.path.join(current_path, name))
            subprocess.check_call("python3 setup.py develop {options}".format(
                options="--user" if user_mode else "",
                ), shell=True)
    if user_mode:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print("Make sure that ~/.local/bin is in your PATH")
            print("export PATH=$PATH:~/.local/bin")

# GCC Toolchains Download --------------------------------------------------------------------------

def gcc_toolchain_download(url, filename):
    if not os.path.exists(filename):
        full_url = url + filename
        print(f"[Downloading {full_url} to {filename}]...")
        urllib.request.urlretrieve(full_url, filename)
    else:
        print("Using existing file {filename}.")

    print(f"[Extracting {filename}]...")
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
    parser = argparse.ArgumentParser(description="LiteX Setup utility.")

    # Git Repositories.
    parser.add_argument("--init",      action="store_true", help="Initialize Git Repositories.")
    parser.add_argument("--update",    action="store_true", help="Update Git Repositories.")
    parser.add_argument("--install",   action="store_true", help="Install Git Repositories.")
    parser.add_argument("--user",      action="store_true", help="Install in User-Mode.")
    parser.add_argument("--config",    default="standard",  help="Install config (minimal, standard, full).")

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
