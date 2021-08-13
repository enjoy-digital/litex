#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
import hashlib
from collections import OrderedDict

import urllib.request

current_path = os.path.abspath(os.curdir)
# Check location (is litex_setup.py executed inside a cloned LiteX repository or alongside?)
if os.path.exists(".gitignore"):
    current_path = os.path.join(current_path, "../")

# Repositories -------------------------------------------------------------------------------------

# name,  (url, recursive clone, develop, sha1)
repos = [
    # HDL
    ("migen",        ("https://github.com/m-labs/",        True,  True, None)),
    ("nmigen",       ("https://github.com/nmigen/",        True,  True, None)),

    # LiteX SoC builder
    ("pythondata-software-compiler_rt", ("https://github.com/litex-hub/",     False, True, None)),
    ("litex",                           ("https://github.com/enjoy-digital/", False, True, None)),

    # LiteX cores ecosystem
    ("liteeth",      ("https://github.com/enjoy-digital/", False, True, None)),
    ("litedram",     ("https://github.com/enjoy-digital/", False, True, None)),
    ("litepcie",     ("https://github.com/enjoy-digital/", False, True, None)),
    ("litesata",     ("https://github.com/enjoy-digital/", False, True, None)),
    ("litesdcard",   ("https://github.com/enjoy-digital/", False, True, None)),
    ("liteiclink",   ("https://github.com/enjoy-digital/", False, True, None)),
    ("litevideo",    ("https://github.com/enjoy-digital/", False, True, None)),
    ("litescope",    ("https://github.com/enjoy-digital/", False, True, None)),
    ("litejesd204b", ("https://github.com/enjoy-digital/", False, True, None)),
    ("litespi",      ("https://github.com/litex-hub/",     False, True, None)),
    ("litehyperbus", ("https://github.com/litex-hub/",     False, True, None)),

    # LiteX boards support
    ("litex-boards", ("https://github.com/litex-hub/",     False, True, None)),

    # Optional LiteX data
    ("pythondata-misc-tapcfg",     ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-misc-opentitan",  ("https://github.com/litex-hub/", False, True, 0xe43566c)),
    ("pythondata-misc-usb_ohci",   ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-lm32",        ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-mor1kx",      ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-picorv32",    ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-serv",        ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-vexriscv",    ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-vexriscv-smp",("https://github.com/litex-hub/", True,  True, None)),
    ("pythondata-cpu-rocket",      ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-minerva",     ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-microwatt",   ("https://github.com/litex-hub/", False, True, 0xf9807b6)),
    ("pythondata-cpu-blackparrot", ("https://github.com/litex-hub/", False, True, None)),
    ("pythondata-cpu-cv32e40p",    ("https://github.com/litex-hub/", True,  True, None)),
]

repos = OrderedDict(repos)

# RISC-V toolchain download ------------------------------------------------------------------------

def sifive_riscv_download():
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

# Setup --------------------------------------------------------------------------------------------

if len(sys.argv) < 2:
    print("Available commands:")
    print("- init")
    print("- update")
    print("- install (add --user to install to user directory)")
    print("- gcc")
    print("- dev (dev mode, disable automatic litex_setup.py update)")
    exit()

# Check/Update litex_setup.py

litex_setup_url = "https://raw.githubusercontent.com/enjoy-digital/litex/master/litex_setup.py"
current_sha1 = hashlib.sha1(open(os.path.realpath(__file__)).read().encode("utf-8")).hexdigest()
print("[checking litex_setup.py]...")
try:
    import requests
    r = requests.get(litex_setup_url)
    if r.status_code != 404:
        upstream_sha1 = hashlib.sha1(r.content).hexdigest()
        if current_sha1 != upstream_sha1:
            if "dev" not in sys.argv[1:]:
                print("[updating litex_setup.py]...")
                with open(os.path.realpath(__file__), "wb") as f:
                    f.write(r.content)
                os.execl(sys.executable, sys.executable, *sys.argv)
except:
    pass

# Repositories cloning
if "init" in sys.argv[1:]:
    for name in repos.keys():
        os.chdir(os.path.join(current_path))
        if not os.path.exists(name):
            url, need_recursive, need_develop, sha1 = repos[name]
            # clone repo (recursive if needed)
            print("[cloning " + name + "]...")
            full_url = url + name
            opts = "--recursive" if need_recursive else ""
            subprocess.check_call("git clone " + full_url + " " + opts, shell=True)
            if sha1 is not None:
                os.chdir(os.path.join(current_path, name))
                os.system("git checkout {:7x}".format(sha1))

# Repositories update
if "update" in sys.argv[1:]:
    for name in repos.keys():
        os.chdir(os.path.join(current_path))
        url, need_recursive, need_develop, sha1 = repos[name]
        print(url)
        if not os.path.exists(name):
            raise Exception("{} not initialized, please (re)-run init and install first.".format(name))
        # update
        print("[updating " + name + "]...")
        os.chdir(os.path.join(current_path, name))
        subprocess.check_call("git checkout master", shell=True)
        subprocess.check_call("git pull --ff-only", shell=True)
        if need_recursive:
            subprocess.check_call("git submodule update --init --recursive", shell=True)
        if sha1 is not None:
            os.chdir(os.path.join(current_path, name))
            os.system("git checkout {:7x}".format(sha1))

# Repositories installation
if "install" in sys.argv[1:]:
    for name in repos.keys():
        os.chdir(os.path.join(current_path))
        url, need_recursive, need_develop, sha1 = repos[name]
        # develop if needed
        print("[installing " + name + "]...")
        if need_develop:
            os.chdir(os.path.join(current_path, name))
            if "--user" in sys.argv[1:]:
                subprocess.check_call("python3 setup.py develop --user", shell=True)
            else:
                subprocess.check_call("python3 setup.py develop", shell=True)

    if "--user" in sys.argv[1:]:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print("Make sure that ~/.local/bin is in your PATH")
            print("export PATH=$PATH:~/.local/bin")

# RISC-V GCC installation
if "gcc" in sys.argv[1:]:
    os.chdir(os.path.join(current_path))
    sifive_riscv_download()
    if "riscv64" not in os.environ.get("PATH", ""):
        print("Make sure that the downloaded RISC-V compiler is in your $PATH.")
        print("export PATH=$PATH:$(echo $PWD/riscv64-*/bin/)")
