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
    def __init__(self, url, clone="regular", develop=True, sha1=None, branch="master", tag=None):
        assert clone in ["regular", "recursive"]
        self.url     = url
        self.clone   = clone
        self.develop = develop
        self.sha1    = sha1
        self.branch  = branch
        self.tag     = tag


git_repos = {
    # HDL.
    # ----
    "migen":    GitRepo(url="https://github.com/m-labs/", clone="recursive"),

    # LiteX SoC builder.
    # ------------------
    "pythondata-software-picolibc":    GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-software-compiler_rt": GitRepo(url="https://github.com/litex-hub/"),
    "litex":                           GitRepo(url="https://github.com/enjoy-digital/", tag=True),

    # LiteX Cores Ecosystem.
    # ----------------------
    "liteeth":      GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litedram":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litepcie":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litesata":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litesdcard":   GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "liteiclink":   GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litescope":    GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litejesd204b": GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litespi":      GitRepo(url="https://github.com/litex-hub/",     tag=True),

    # LiteX Misc Cores.
    # -----------------
    "valentyusb":         GitRepo(url="https://github.com/litex-hub/", branch="hw_cdc_eptri"),

    # LiteX Boards.
    # -------------
    "litex-boards": GitRepo(url="https://github.com/litex-hub/", clone="regular", tag=True),

    # LiteX pythondata.
    # -----------------
    # Generic.
    "pythondata-misc-tapcfg":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-misc-usb_ohci":    GitRepo(url="https://github.com/litex-hub/"),

    # LM32 CPU(s).
    "pythondata-cpu-lm32":         GitRepo(url="https://github.com/litex-hub/"),

    # OpenRISC CPU(s).
    "pythondata-cpu-mor1kx":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-marocchino":   GitRepo(url="https://github.com/litex-hub/"),

    # OpenPower CPU(s).
    "pythondata-cpu-microwatt":    GitRepo(url="https://github.com/litex-hub/", sha1=0xb940b55acff),

    # RISC-V CPU(s).
    "pythondata-cpu-blackparrot":  GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-cv32e40p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cv32e41p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cva5":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-cva6":         GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-ibex":         GitRepo(url="https://github.com/litex-hub/", clone="recursive", sha1=0xd3d53df),
    "pythondata-cpu-minerva":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-naxriscv":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-picorv32":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-rocket":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-serv":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexriscv":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexriscv-smp": GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
}

# Installs -----------------------------------------------------------------------------------------

# Minimal: Only Migen + LiteX.
minimal_repos = ["migen", "litex"]

# Standard: Migen + LiteX + Cores + Software + Popular CPUs (LM32, Mor1kx, SERV, VexRiscv).
standard_repos = list(git_repos.keys())
standard_repos.remove("pythondata-cpu-blackparrot")
standard_repos.remove("pythondata-cpu-cv32e40p")
standard_repos.remove("pythondata-cpu-cv32e41p")
standard_repos.remove("pythondata-cpu-cva5")
standard_repos.remove("pythondata-cpu-cva6")
standard_repos.remove("pythondata-cpu-ibex")
standard_repos.remove("pythondata-cpu-marocchino")
standard_repos.remove("pythondata-cpu-minerva")
standard_repos.remove("pythondata-cpu-microwatt")
standard_repos.remove("pythondata-cpu-picorv32")
standard_repos.remove("pythondata-cpu-rocket")

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

# Git helpers --------------------------------------------------------------------------------------

def git_checkout(sha1=None, tag=None):
    assert not ((sha1 is None) and (tag is None))
    if sha1 is not None:
        os.system(f"git checkout {sha1:07x}")
    if tag is not None:
        sha1_tag_cmd = ["git", "rev-list", "-n 1", tag]
        sha1_tag     = subprocess.check_output(sha1_tag_cmd).decode("UTF-8")[:-1]
        os.system(f"git checkout {sha1_tag}")

# Git repositories initialization ------------------------------------------------------------------

def litex_setup_init_repos(config="standard", tag=None, dev_mode=False):
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
            os.chdir(os.path.join(current_path, name))
            # Use specific Branch.
            subprocess.check_call("git checkout " + repo.branch, shell=True)
            # Use specific Tag (Optional).
            if repo.tag is not None:
                # Priority to passed tag (if specified).
                if tag is not None:
                    git_checkout(tag=tag)
                    continue
                # Else fallback to repo tag (if specified).
                if isinstance(repo.tag, str):
                    git_checkout(tag=tag)
                    continue
            # Use specific SHA1 (Optional).
            if repo.sha1 is not None:
                git_checkout(sha1=repo.sha1)
        else:
            print_status(f"{name} Git Repo already present.")

# Git repositories update --------------------------------------------------------------------------

def litex_setup_update_repos(config="standard", tag=None):
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
        # Use specific Tag (Optional).
        if repo.tag is not None:
            # Priority to passed tag (if specified).
            if tag is not None:
                git_checkout(tag=tag)
                continue
            # Else fallback to repo tag (if specified).
            if isinstance(repo.tag, str):
                git_checkout(tag=tag)
                continue
        # Use specific SHA1 (Optional).
        if repo.sha1 is not None:
            git_checkout(sha1=repo.sha1)

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
            subprocess.check_call("\"{python3}\" -m pip install --editable . {options}".format(
                python3 = sys.executable,
                options = "--user" if user_mode else "",
                ), shell=True)
    if user_mode:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print_status("Make sure that ~/.local/bin is in your PATH")
            print_status("export PATH=$PATH:~/.local/bin")

# Git repositories freeze --------------------------------------------------------------------------

def litex_setup_freeze_repos(config="standard"):
    print_status("Freezing config of Git repositories...", underline=True)
    r = "git_repos = {\n"
    for name in install_configs[config]:
        repo = git_repos[name]
        os.chdir(os.path.join(current_path, name))
        git_sha1_cmd = ["git", "rev-parse", "--short=7", "HEAD"]
        git_sha1     = subprocess.check_output(git_sha1_cmd).decode("UTF-8")[:-1]
        git_url_cmd  = ["git", "remote", "get-url", "origin"]
        git_url      = subprocess.check_output(git_url_cmd).decode("UTF-8")[:-1]
        git_url      = git_url.replace(f"{name}.git", "")
        r += " "*4
        r += f'"{name}" : GitRepo(url="{git_url}",\n'
        r += f'{" "*8}clone   = "{repo.clone}",\n'
        r += f'{" "*8}develop = {repo.develop},\n'
        r += f'{" "*8}sha1    = 0x{git_sha1},\n'
        r += f'{" "*8}branch  = "{repo.branch}"'
        r += f'\n{" "*4}),\n'
    r += "}\n"
    print(r)

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
    base_url  = "https://static.dev.sifive.com/dev-tools/freedom-tools/v2020.08/"
    base_file = "riscv64-unknown-elf-gcc-10.1.0-2020.08.2-x86_64-"

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
    parser.add_argument("--tag",       default=None,        help="Use version from release tag.")
    parser.add_argument("--freeze",    action="store_true", help="Freeze and display current config.")


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
        litex_setup_init_repos(config=args.config, tag=args.tag, dev_mode=args.dev)

    # Update.
    if args.update:
        litex_setup_update_repos(config=args.config, tag=args.tag)

    # Install.
    if args.install:
        litex_setup_install_repos(config=args.config, user_mode=args.user)

    # Freeze.
    if args.freeze:
        litex_setup_freeze_repos(config=args.config)

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
