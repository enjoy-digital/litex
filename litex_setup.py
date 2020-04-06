#!/usr/bin/env python3

import os
import sys
import subprocess
from collections import OrderedDict

import urllib.request

current_path = os.path.dirname(os.path.realpath(__file__))

# name,  (url, recursive clone, develop)
repos = [
    # HDL
    ("migen",        ("https://github.com/m-labs/",        True,  True)),

    # LiteX SoC builder
    ("litex",        ("https://github.com/enjoy-digital/", True,  True)),

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
]
repos = OrderedDict(repos)


def sifive_riscv_download():
    base_url = "https://static.dev.sifive.com/dev-tools/"
    base_file = "riscv64-unknown-elf-gcc-8.3.0-2019.08.0-x86_64-"

    is_windows = (
        sys.platform.startswith('win') or sys.platform.startswith('cygwin'))
    if is_windows:
        end_file = 'w64-mingw32.zip'
    elif sys.platform.startswith('linux'):
        end_file = 'linux-ubuntu14.tar.gz'
    elif sys.platform.startswith('darwin'):
        end_file = 'apple-darwin.tar.gz'
    else:
        raise NotImplementedError(sys.platform)
    fn = base_file + end_file

    if not os.path.exists(fn):
        url = base_url+fn
        print("Downloading", url, "to", fn)
        urllib.request.urlretrieve(url, fn)
    else:
        print("Using existing file", fn)

    print("Extracting", fn)
    if fn.endswith(".tar.gz"):
        import tarfile
        with tarfile.open(fn) as t:
            t.extractall()
    elif fn.endswith(".zip"):
        import zipfile
        with zipfile.open(fn) as z:
            z.extractall()

    if "--user" in sys.argv[1:] and not is_windows:
        print("Linking compiler into ~/.local/bin")
        local_bin_dir = os.path.join(
            base_file + end_file.split('.', 1)[0], "bin")
        assert os.path.exists(local_bin_dir), local_bin_dir
        user_bin_dir = os.path.abspath(os.path.expanduser("~/.local/bin"))
        if not os.path.exists(user_bin_dir):
            os.makedirs(user_bin_dir)
        for f in os.listdir(local_bin_dir):
            src = os.path.abspath(os.path.join(local_bin_dir, f))
            dst = os.path.join(user_bin_dir, f)
            assert os.path.exists(src), src
            if os.path.exists(dst):
                os.unlink(dst)
            assert not os.path.exists(dst), dst
            os.symlink(src, dst)


if len(sys.argv) < 2:
    print("Available commands:")
    print("- init")
    print("- install (add --user to install to user directory)")
    print("- update")
    print("- gcc")
    exit()

if "init" in sys.argv[1:]:
    os.chdir(os.path.join(current_path))
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # clone repo (recursive if needed)
        print("[cloning " + name + "]...")
        full_url = url + name
        opts = "--recursive" if need_recursive else ""
        subprocess.check_call(
            "git clone " + full_url + " " + opts,
            shell=True)

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

if "gcc" in sys.argv[1:]:
    sifive_riscv_download()

if "update" in sys.argv[1:]:
    for name in repos.keys():
        # update
        print("[updating " + name + "]...")
        os.chdir(os.path.join(current_path, name))
        subprocess.check_call(
            "git pull",
            shell=True)
        os.chdir(os.path.join(current_path))

if "--user" in sys.argv[1:]:
    if ".local/bin" not in os.environ.get("PATH", ""):
        print("Make sure that ~/.local/bin is in your PATH")
elif "gcc" in sys.argv[1:]:
    print("Make sure that the download RISC-V compiler is in your $PATH.")
