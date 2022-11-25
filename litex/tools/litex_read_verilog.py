#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2018-2019 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import json

from litex.build import tools

def main():
    if len(sys.argv) < 2:
        print("usage: litex_read_verilog verilog_file [module]")
        exit(1)

    verilog_file = sys.argv[1]
    json_file = verilog_file + ".json"
    module = None if len(sys.argv) < 3 else sys.argv[2]

    # use yosys to convert verilog to json
    yosys_v2j = "\n".join([
        "read_verilog -sv {}".format(verilog_file),
        "proc",
        "write_json {}.json".format(verilog_file)
    ])
    tools.write_to_file("yosys_v2j.ys", yosys_v2j)
    os.system("yosys -q yosys_v2j.ys")

    # load json and convert to migen module
    f = open(json_file, "r")
    j = json.load(f)

    # create list of modules
    modules = [module] if module is not None else j["modules"].keys()

    # create migen definitions
    for module in modules:
        migen_def = []
        migen_def.append("class {}(Module):".format(module))
        migen_def.append(" "*4 + "def __init__(self):")
        for name, info in j["modules"][module]["ports"].items():
            length = "" if len(info["bits"]) == 1 else len(info["bits"])
            migen_def.append(" " * 8 + "self.{} = Signal({})".format(name, length))
        migen_def.append("")
        migen_def.append(" "*8 + "# # #")
        migen_def.append("")
        migen_def.append(" "*8 + "self.specials += Instance(\"{}\",".format(module))
        for name, info in j["modules"][module]["ports"].items():
            io_prefix = {
                "input": "i",
                "output": "o",
                "inout": "io"
            }[info["direction"]]
            migen_def.append(" "*12 + "{}_{}=self.{},".format(io_prefix, name, name))
        migen_def.append(" "*8 + ")")
        migen_def.append("")
        print("\n".join(migen_def))

    # keep things clean after us
    os.system("rm yosys_v2j.ys")
    os.system("rm " + json_file)


if __name__ == "__main__":
    main()
