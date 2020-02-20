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
    ("litex",      ("https://github.com/enjoy-digital/", True,  True)),

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

parser = argparse.ArgumentParser()
parser.add_argument("--init",    action="store_true")
parser.add_argument("--install", action="store_true")
parser.add_argument("--update",  action="store_true")
parser.add_argument("--user",    action="store_true")
args = parser.parse_args()

if args.init:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # clone repo (recursive if needed)
        print("[cloning " + name + "]...")
        full_url = url + name
        opts = "--recursive" if need_recursive else ""
        os.system("git clone " + full_url + " " + opts)

if args.install:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # develop if needed
        print("[installing " + name + "]...")
        if need_develop:
            os.chdir(os.path.join(current_path, name))
            if args.user:
                os.system("python3 setup.py develop --user")
            else:
                os.system("python3 setup.py develop")

if args.update:
    for name in repos.keys():
        # update
        print("[updating " + name + "]...")
        os.chdir(os.path.join(current_path, name))
        os.system("git pull")
