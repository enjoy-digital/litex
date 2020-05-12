#!/usr/bin/env python3

import os
import sys
import subprocess
import shutil
from collections import OrderedDict

import urllib.request

current_path = os.path.abspath(os.curdir)


# Repositories -------------------------------------------------------------------------------------

# name,  (url, recursive clone, develop)
repos = [
    # HDL
    ("migen",        ("https://github.com/m-labs/",        True,  True)),
    ("nmigen",       ("https://github.com/nmigen/",        True,  True)),

    # LiteX SoC builder
    ("pythondata-software-compiler_rt", ("https://github.com/litex-hub/",     False, True)),
    ("litex",                           ("https://github.com/enjoy-digital/", False, True)),

    # LiteX cores ecosystem
    ("liteeth",      ("https://github.com/enjoy-digital/", False, True)),
    ("litedram",     ("https://github.com/enjoy-digital/", False, True)),
    ("litepcie",     ("https://github.com/enjoy-digital/", False, True)),
    ("litesata",     ("https://github.com/enjoy-digital/", False, True)),
    ("litesdcard",   ("https://github.com/enjoy-digital/", False, True)),
    ("liteiclink",   ("https://github.com/enjoy-digital/", False, True)),
    ("litevideo",    ("https://github.com/enjoy-digital/", False, True)),
    ("litescope",    ("https://github.com/enjoy-digital/", False, True)),
    ("litejesd204b", ("https://github.com/enjoy-digital/", False, True)),
    ("litespi",      ("https://github.com/litex-hub/",     False, True)),

    # LiteX boards support
    ("litex-boards", ("https://github.com/litex-hub/",     False, True)),

    # Optional LiteX data
    ("pythondata-misc-tapcfg",     ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-lm32",        ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-mor1kx",      ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-picorv32",    ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-serv",        ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-vexriscv",    ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-rocket",      ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-minerva",     ("https://github.com/litex-hub/", False, True)),
    ("pythondata-cpu-microwatt",   ("https://github.com/litex-hub/", False, True)),
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

if os.environ.get("TRAVIS", "") == "true":
    # Ignore `ssl.SSLCertVerificationError` on CI.
    import ssl
    ssl._create_default_https_context = ssl._create_unverified_context

if len(sys.argv) < 2:
    print("Available commands:")
    print("- init")
    print("- install (add --user to install to user directory)")
    print("- update")
    print("- gcc")
    exit()

# Repositories cloning
if "init" in sys.argv[1:]:
    os.chdir(os.path.join(current_path))
    for name in repos.keys():
        if not os.path.exists(name):
            url, need_recursive, need_develop = repos[name]
            # clone repo (recursive if needed)
            print("[cloning " + name + "]...")
            full_url = url + name
            opts = "--recursive" if need_recursive else ""
            subprocess.check_call(
                "git clone " + full_url + " " + opts,
                shell=True)

# Repositories installation
if "install" in sys.argv[1:]:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # develop if needed
        print("[installing " + name + "]...")
        if need_develop:
            os.chdir(os.path.join(current_path, name))
            if "--user" in sys.argv[1:]:
                subprocess.check_call(
                    "python3 setup.py develop --user",
                    shell=True)
            else:
                subprocess.check_call(
                    "python3 setup.py develop",
                    shell=True)
            os.chdir(os.path.join(current_path))

    if "--user" in sys.argv[1:]:
        if ".local/bin" not in os.environ.get("PATH", ""):
            print("Make sure that ~/.local/bin is in your PATH")
            print("export PATH=$PATH:~/.local/bin")

# Repositories update
if "update" in sys.argv[1:]:
    for name in repos.keys():
        if not os.path.exists(name):
            raise Exception("{} not initialized, please (re)-run init and install first.".format(name))
        # update
        print("[updating " + name + "]...")
        os.chdir(os.path.join(current_path, name))
        subprocess.check_call(
            "git pull --ff-only",
            shell=True)
        os.chdir(os.path.join(current_path))

# RISC-V GCC installation
if "gcc" in sys.argv[1:]:
    sifive_riscv_download()
    if "riscv64" not in os.environ.get("PATH", ""):
        print("Make sure that the downloaded RISC-V compiler is in your $PATH.")
        print("export PATH=$PATH:$(echo $PWD/riscv64-*/bin/)")
