#!/usr/bin/env python3

import os
import sys
from collections import OrderedDict


# This is needed for eg: when you are installing from a fork
LITEX_ROOT_URL = os.genev("LITEX_URL", "http://github.com/enjoy-digital/")

current_path = os.path.dirname(os.path.realpath(__file__))

# name,  (url, recursive clone, develop)
repos = [
    ("migen",      ("http://github.com/m-labs/",        True,  True)),
    ("litex",      (LITEX_ROOT_URL, True,  True)),
    ("liteeth",    (LITEX_ROOT_URL, False, True)),
    ("liteusb",    (LITEX_ROOT_URL, False, True)),
    ("litedram",   (LITEX_ROOT_URL, False, True)),
    ("litepcie",   (LITEX_ROOT_URL, False, True)),
    ("litesdcard", (LITEX_ROOT_URL, False, True)),
    ("liteiclink", (LITEX_ROOT_URL, False, True)),
    ("litevideo",  (LITEX_ROOT_URL, False, True)),
    ("litescope",  (LITEX_ROOT_URL, False, True)),
]
repos = OrderedDict(repos)

if len(sys.argv) < 2:
    print("Available commands:")
    print("- init")
    print("- install")
    print("- update")
    exit()

if "init" in sys.argv[1:]:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # clone repo (recursive if needed)
        print("[cloning " + name + "]...")
        full_url = url + name
        opts = "--recursive" if need_recursive else ""
        os.system("git clone " + full_url + " " + opts)

if "install" in sys.argv[1:]:
    for name in repos.keys():
        url, need_recursive, need_develop = repos[name]
        # develop if needed
        print("[installing " + name + "]...")
        if need_develop:
            os.chdir(os.path.join(current_path, name))
            os.system("python3 setup.py develop")

if "update" in sys.argv[1:]:
    for name in repos.keys():
        # update
        print("[updating " + name + "]...")
        os.chdir(os.path.join(current_path, name))
        os.system("git pull")
