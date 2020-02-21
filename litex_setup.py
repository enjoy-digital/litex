#!/usr/bin/env python3

import os
import sys
import argparse
from collections import OrderedDict

current_path = os.path.dirname(os.path.realpath(__file__))

# name,  (url, recursive clone, develop)
repos = [
    # HDL
    ("migen",      ("https://github.com/m-labs/",        True,  True)),

    # LiteX SoC builder
    ("litex",      ("https://github.com/enjoy-digital/", False,  True)),

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

    # LiteX boards support
    ("litex-boards",   ("https://github.com/litex-hub/", False, True)),
]
repos = OrderedDict(repos)

submodules = {
    # name,  recursive clone
    "litex-cpu-blackparrot":  False,
    "litex-cpu-lm32":         False,
    "litex-cpu-microwatt":    False,
    "litex-cpu-minerva":      False,
    "litex-cpu-mor1kx":       False,
    "litex-cpu-picorv32":     False,
    "litex-cpu-rocket":       False,
    "litex-cpu-vexriscv":     False,
    "litex-sim-tapcfg":       False,
    "litex-soft-compiler_rt": False,
}

parser = argparse.ArgumentParser()
parser.add_argument("--init",           action="store_true", help="Download and init LiteX repositories")
parser.add_argument("--update",         action="store_true", help="Update LiteX repositories")
parser.add_argument("--install",        action="store_true", help="Install LiteX repositories on the system (for all users)")
parser.add_argument("--install-user",   action="store_true", help="Install LiteX repositories on the system (for current user)")
parser.add_argument("--submodule-init", default=None,        help="Init Submodule(s) (all or {})".format(", ".join(submodules.keys())))
args = parser.parse_args()

if args.init:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # clone repo (recursive if needed)
        print("[cloning " + name + "]...")
        full_url = url + name
        opts = "--recursive" if need_recursive else ""
        os.system("git clone " + full_url + " " + opts)

if args.install or args.install_user:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # develop if needed
        print("[installing " + name + "]...")
        if need_develop:
            os.chdir(os.path.join(current_path, name))
            cmd = "python3 setup.py develop"
            if args.install_user:
                cmd += " --user"
            os.system(cmd)

if args.update:
    for name in repos.keys():
        # update
        print("[updating " + name + "]...")
        os.chdir(os.path.join(current_path, name))
        os.system("git pull")

if args.submodule_init is not None:
    submodules_init = []
    if args.submodule_init == "all":
        submodules_init = submodules.keys()
    else:
        submodules_init = [args.submodule_init]
    for name in submodules_init:
        os.system("cd litex && git submodule update --init --recursive third_party/{}".format(name.replace("-", "_")))
