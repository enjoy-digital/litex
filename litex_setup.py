#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import hashlib

import urllib.request

current_path = os.path.abspath(os.curdir)

# Git Repositories ---------------------------------------------------------------------------------

# Get SHA1: git rev-parse --short=7 HEAD

class GitRepo:
    def __init__(self, url, clone="regular", develop=True, sha1=None):
        assert clone in ["regular", "recursive"]
        self.url     = url
        self.clone   = clone
        self.develop = develop
        self.sha1    = sha1

git_repos = {
    # HDL.
    "migen":  GitRepo(url="https://github.com/m-labs/", clone="recursive"),
    "nmigen": GitRepo(url="https://github.com/nmigen/", clone="recursive"),

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
    "pythondata-cpu-ibex":         GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
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

def litex_setup_init_repos():
    for name, repo in git_repos.items():
        os.chdir(os.path.join(current_path))
        print(f"[Checking {name}]...")
        if not os.path.exists(name):
            # Clone Repo.
            print(f"[Cloning {name}]...")
            subprocess.check_call("git clone {url} {options}".format(
                url     = repo.url + name,
                options = "--recursive" if repo.clone == "recursive" else ""
                ), shell=True)
            # Use specific SHA1 (Optional).
            if repo.sha1 is not None:
                os.chdir(os.path.join(current_path, name))
                os.system(f"git checkout {repo.sha1:07x}")

# Repositories Update ------------------------------------------------------------------------------

def litex_setup_update_repos():
    for name, repo in git_repos.items():
        os.chdir(os.path.join(current_path))
        # Check if Repo is present.
        if not os.path.exists(name):
            raise Exception("{} not initialized, please (re)-run init and install first.".format(name))
        # Update Repo.
        print(f"[Updating {name}]...")
        os.chdir(os.path.join(current_path, name))
        subprocess.check_call("git checkout master", shell=True)
        subprocess.check_call("git pull --ff-only", shell=True)
        # Recursive Update (Optional).
        if repo.clone == "recursive":
            subprocess.check_call("git submodule update --init --recursive", shell=True)
        # Use specific SHA1 (Optional).
        if repo.sha1 is not None:
            os.chdir(os.path.join(current_path, name))
            os.system(f"git checkout {repo.sha1:07x}")

# Repositories Install -----------------------------------------------------------------------------

def litex_setup_install_repos(user_mode=False):
    for name, repo in git_repos.items():
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
        end_file = "linux-ubuntu14.tar.gz"
    # Mac OS
    elif sys.platform.startswith("darwin"):
        end_file = "apple-darwin.tar.gz"
    else:
        raise NotImplementedError(sys.platform)
    fn = base_file + end_file

    if not os.path.exists(fn):
        url = base_url + fn
        print("Downloading", url, "to", fn)
        urllib.request.urlretrieve(url, fn)
    else:
        print("Using existing file", fn)

    print("Extracting", fn)
    shutil.unpack_archive(fn)

# PowerPC toolchain download.
# ---------------------------

def powerpc_gcc_toolchain_download():
    base_url  = "https://toolchains.bootlin.com/downloads/releases/toolchains/powerpc64le-power8/tarballs/"
    base_file = "powerpc64le-power8--musl--stable-2020.08-1.tar.bz2"

    # TODO

# OpenRISC toolchain download.
# ----------------------------

def openrisc_gcc_toolchain_download():
    base_url  = "https://toolchains.bootlin.com/downloads/releases/toolchains/openrisc/tarballs/"
    base_file = "openrisc--musl--stable-2020.08-1.tar.bz2"

    # TODO

# LM32 toolchain download.

def lm32_gcc_toolchain_download():
    base_url  = ""
    base_file = ""

    # TODO

# Run ----------------------------------------------------------------------------------------------

if len(sys.argv) < 2:
    print("Available commands:")
    print("- init")
    print("- update")
    print("- install (add --user to install to user directory)")
    print("- gcc")
    print("- dev (dev mode, disable automatic litex_setup.py update)")
    exit()

litex_setup_location_check()
if "dev" not in sys.argv[1:]:
    litex_setup_auto_update()

if "init" in sys.argv[1:]:
    litex_setup_init_repos()

if "update" in sys.argv[1:]:
    litex_setup_update_repos()

if "install" in sys.argv[1:]:
    litex_setup_install_repos(user_mode="--user" in sys.argv[1:])

if "gcc" in sys.argv[1:]:
    os.chdir(os.path.join(current_path))
    riscv_gcc_toolchain_download()
    if "riscv64" not in os.environ.get("PATH", ""):
        print("Make sure that the downloaded RISC-V compiler is in your $PATH.")
        print("export PATH=$PATH:$(echo $PWD/riscv64-*/bin/)")
