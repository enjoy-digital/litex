#!/usr/bin/env python3

import os
import re
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

def colorer(s, color="bright"):
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
    def __init__(self, url, clone="regular", develop=True, editable=True, sha1=None, branch="master", tag=None):
        assert clone in ["regular", "recursive"]
        self.url      = url
        self.clone    = clone
        self.develop  = develop
        self.editable = editable
        self.sha1     = sha1
        self.branch   = branch
        self.tag      = tag


git_repos = {
    # HDL.
    # ----
    "migen":    GitRepo(url="https://github.com/m-labs/", clone="recursive", editable=False, sha1=0x4c2ae8dfeea37f235b52acb8166f12acaaae4f7c),

    # LiteX SoC builder.
    # ------------------
    "pythondata-software-picolibc":    GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-software-compiler_rt": GitRepo(url="https://github.com/litex-hub/"),
    "litex":                           GitRepo(url="https://github.com/enjoy-digital/", tag=True),

    # LiteX Cores Ecosystem.
    # ----------------------
    "liteiclink":   GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "liteeth":      GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litedram":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litepcie":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litesata":     GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litesdcard":   GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litescope":    GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litejesd204b": GitRepo(url="https://github.com/enjoy-digital/", tag=True),
    "litespi":      GitRepo(url="https://github.com/litex-hub/",     tag=True),
    "litei2c":      GitRepo(url="https://github.com/litex-hub/",     tag=True, branch="main"),

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
    "pythondata-misc-usb_ohci":    GitRepo(url="https://github.com/litex-hub/", clone="recursive"),

    # LM32 CPU(s).
    "pythondata-cpu-lm32":         GitRepo(url="https://github.com/litex-hub/"),

    # OpenRISC CPU(s).
    "pythondata-cpu-mor1kx":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-marocchino":   GitRepo(url="https://github.com/litex-hub/"),

    # OpenPower CPU(s).
    "pythondata-cpu-microwatt":    GitRepo(url="https://github.com/litex-hub/", sha1=0xc69953aff92),

    # RISC-V CPU(s).
    "pythondata-cpu-blackparrot":  GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-coreblocks":   GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cv32e40p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cv32e41p":     GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-cva5":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-cva6":         GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-ibex":         GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
    "pythondata-cpu-minerva":      GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-naxriscv":     GitRepo(url="https://github.com/litex-hub/", branch="smp"),
    "pythondata-cpu-openc906":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-picorv32":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-rocket":       GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-sentinel":     GitRepo(url="https://github.com/litex-hub/", branch="main"),
    "pythondata-cpu-serv":         GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexiiriscv":   GitRepo(url="https://github.com/litex-hub/", branch="main"),
    "pythondata-cpu-vexriscv":     GitRepo(url="https://github.com/litex-hub/"),
    "pythondata-cpu-vexriscv-smp": GitRepo(url="https://github.com/litex-hub/", clone="recursive"),
}

# Installs -----------------------------------------------------------------------------------------

# Minimal: Only Migen + LiteX.
minimal_repos = ["migen", "litex"]

# Standard: Migen + LiteX + Cores + Software + Popular CPUs (LM32, Mor1kx, SERV, VexRiscv).
standard_repos = list(git_repos.keys())
standard_repos.remove("pythondata-cpu-blackparrot")
standard_repos.remove("pythondata-cpu-coreblocks")
standard_repos.remove("pythondata-cpu-cv32e40p")
standard_repos.remove("pythondata-cpu-cv32e41p")
standard_repos.remove("pythondata-cpu-cva5")
standard_repos.remove("pythondata-cpu-cva6")
standard_repos.remove("pythondata-cpu-ibex")
standard_repos.remove("pythondata-cpu-openc906")
standard_repos.remove("pythondata-cpu-marocchino")
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

def git_tag(tag=None):
    assert tag is not None
    os.system(f"git tag {tag}")
    os.system(f"git push --tags")

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
            subprocess.check_call("\"{python3}\" -m pip install {editable} . {options}".format(
                python3  = sys.executable,
                editable = "--editable" if repo.editable else "",
                options  = "--user"     if user_mode else "",
                ), shell=True)
    if user_mode:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print_status("Make sure that ~/.local/bin is in your PATH")
            print_status("export PATH=$PATH:~/.local/bin # temporary (limited to the current terminal)")
            print_status("or add the previous line into your ~/.bashrc to permanently update PATH")

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

# Git repositories release -------------------------------------------------------------------------

def get_current_tag(repo_path):
    try:
        cmd = ["git", "describe", "--tags", "--abbrev=0"]
        result = subprocess.check_output(cmd, cwd=repo_path).decode("UTF-8").strip()
        return result
    except subprocess.CalledProcessError:
        return "No tags"

def get_setup_version(setup_path):
    try:
        with open(setup_path, "r", encoding="utf-8") as f:
            content = f.read()
        match = re.search(r'version\s*=\s*["\']([^"\']+)["\']', content)
        if match:
            return match.group(1)
        return "No version found"
    except FileNotFoundError:
        return "No setup.py"

def litex_setup_release_check_repos():
    print_status("Checking repositories for release...", underline=True)
    print(colorer("Repo".ljust(35) + "Last Tag".ljust(17) + "Setup Version"))
    print("-" * 80)
    for name in install_configs["full"]:
        if name in ["migen"]:
            continue
        repo_path = os.path.join(current_path, name)
        if not os.path.exists(repo_path):
            last_tag = "Not initialized"
            setup_version = "Not initialized"
        else:
            last_tag = get_current_tag(repo_path)
            setup_version = get_setup_version(os.path.join(repo_path, "setup.py"))
        print(f"{name:<35} {last_tag:<15} {setup_version}")

def litex_setup_release_repos(tag):
    litex_setup_release_check_repos()
    print_status(f"Making release {tag}...", underline=True)
    confirm = input("Please confirm by pressing Y:")
    if confirm.upper() != "Y":
        print_status("Not confirmed, exiting.")
        return
    for name in install_configs["full"]:
        if name in ["migen"]:
            continue
        repo      = git_repos[name]
        repo_path = os.path.join(current_path, name)
        if not os.path.exists(repo_path):
            print_error(f"{name} Git repository is not initialized.")
            continue
        os.chdir(repo_path)
        setup_path = os.path.join(repo_path, "setup.py")
        bumped     = False
        if os.path.exists(setup_path):
            current_version = get_setup_version(setup_path)
            if current_version == "No version found":
                print_status(f"No version in {name} setup.py, skipping bump.")
            elif current_version != tag:
                print_status(f"Bumping version in {name} setup.py from {current_version} to {tag}...")
                with open(setup_path, "r", encoding="utf-8") as f:
                    content = f.read()
                new_content = re.sub(r'version\s*=\s*["\'][^"\']+["\']', f'version = "{tag}"', content)
                with open(setup_path, "w", encoding="utf-8") as f:
                    f.write(new_content)
                subprocess.check_call(f'git add {setup_path}', shell=True)
                commit_msg = f'Bump to version {tag}'
                subprocess.check_call(f'git commit -m "{commit_msg}"', shell=True)
                subprocess.check_call('git push', shell=True)
                bumped = True
            else:
                print_status(f"Version in {name} already at {tag}, skipping bump.")
        # Tag Repo.
        print_status(f"Tagging {name} Git repository as {tag}...")
        git_tag(tag=tag)

# GCC toolchains install ---------------------------------------------------------------------------

# RISC-V toolchain.
# -----------------

def riscv_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = (open("/etc/os-release").read()).lower()
        # Fedora.
        if "fedora" in os_release:
            os.system("dnf install gcc-riscv64-linux-gnu")
        # Arch.
        elif "arch" in os_release:
            os.system("pacman -S riscv64-linux-gnu-gcc")
        # Alpine.
        elif "alpine" in os_release:
            os.system("apk add gcc-cross-embedded")
        # Ubuntu.
        else:
            os.system("apt install gcc-riscv64-unknown-elf")

    # Mac OS.
    # -------
    elif sys.platform.startswith("darwin"):
        os.system("brew install riscv-tools")

    # Manual installation.
    # --------------------
    else:
        NotImplementedError(f"RISC-V GCC requires manual installation on {sys.platform}.")

# PowerPC toolchain.
# -----------------

def powerpc_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = (open("/etc/os-release").read()).lower()
        # Fedora.
        if "fedora" in os_release:
            os.system("dnf install gcc-powerpc64le-linux-gnu") # FIXME: binutils-multiarch?
        # Arch (AUR repository).
        elif "arch" in os_release:
            os.system("yay -S powerpc64le-linux-gnu-gcc")
        # Alpine.
        elif "alpine" in os_release:
            os.system("apk add gcc binutils-ppc64le")
        # Ubuntu.
        else:
            os.system("apt install gcc-powerpc64le-linux-gnu binutils-multiarch")

    # Manual installation.
    # --------------------
    else:
        NotImplementedError(f"PowerPC GCC requires manual installation on {sys.platform}.")

# OpenRISC toolchain.
# -------------------

def openrisc_gcc_install():
    # Linux.
    # ------
    if sys.platform.startswith("linux"):
        os_release = (open("/etc/os-release").read()).lower()
        # Fedora.
        if "fedora" in os_release:
            os.system("dnf install gcc-or1k-elf")
        # Arch.
        elif "arch" in os_release:
            os.system("pacman -S or1k-elf-gcc")
        # Alpine.
        elif "alpine" in os_release:
            os.system("apk add gcc-cross-embedded")
        # Ubuntu.
        else:
            os.system("apt install gcc-or1k-elf")

    # Manual installation.
    # --------------------
    else:
        NotImplementedError(f"OpenRISC GCC requires manual installation on {sys.platform}.")

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

    # GCC toolchains.
    parser.add_argument("--gcc", default=None, help="Install GCC Toolchain (riscv, powerpc or openrisc).")

    # Development mode.
    parser.add_argument("--dev",            action="store_true", help="Development-Mode (no Auto-Update of litex_setup.py / Switch to git@github.com URLs).")
    parser.add_argument("--freeze",         action="store_true", help="Freeze and display current config.")
    parser.add_argument("--release-check",  action="store_true", help="Check repositories before release.")
    parser.add_argument("--release",        default=None,        help="Make release.")

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
        ci_run   = (os.environ.get("GITHUB_ACTIONS") == "true")
        dev_mode = args.dev and (not ci_run)
        litex_setup_init_repos(config=args.config, tag=args.tag, dev_mode=dev_mode)

    # Update.
    if args.update:
        litex_setup_update_repos(config=args.config, tag=args.tag)

    # Install.
    if args.install:
        litex_setup_install_repos(config=args.config, user_mode=args.user)

    # Freeze.
    if args.freeze:
        litex_setup_freeze_repos(config=args.config)

    # Release Check.
    if args.release_check:
        litex_setup_release_check_repos()

    # Release.
    if args.release:
        litex_setup_release_repos(tag=args.release)

    # GCC.
    os.chdir(os.path.join(current_path))
    if args.gcc == "riscv":
        riscv_gcc_install()
    if args.gcc == "powerpc":
        powerpc_gcc_install()
    if args.gcc == "openrisc":
        openrisc_gcc_install()

if __name__ == "__main__":
    main()

