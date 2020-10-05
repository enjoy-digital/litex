#
# This file is part of LiteX.
#
# Copyright (c) 2020 Pepijn de Vos <pepijndevos@gmail.com>
# Copyright (c) 2015-2018 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import subprocess

from migen.fhdl.structure import _Fragment

from litex.build.generic_platform import Pins, IOStandard, Misc
from litex.build import tools

def _build_cst(named_sc, named_pc):
    lines = []

    flat_sc = []
    for name, pins, other, resource in named_sc:
        if len(pins) > 1:
            for i, p in enumerate(pins):
                flat_sc.append((f"{name}[{i}]", p, other))
        else:
            flat_sc.append((name, pins[0], other))

    for name, pin, other in flat_sc:
        lines.append(f"IO_LOC \"{name}\" {pin};")
    
        for c in other:
            if isinstance(c, IOStandard):
                lines.append(f"IO_PORT \"{name}\" IO_TYPE={c.name};")
            elif isinstance(c, Misc):
                lines.append(f"IO_PORT \"{name}\" {c.misc};")

    if named_pc:
        lines.extend(named_pc)

    cst = "\n".join(lines)
    with open("top.cst", "w") as f:
        f.write(cst)

def _build_script(name, partnumber, files, options):
    lines = [
        f"set_device -name {name} {partnumber}",
        "add_file top.cst",
    ]

    for f, typ, lib in files:
        lines.append(f"add_file {f}")

    for opt, val in options.items():
        lines.append(f"set_option -{opt} {val}")

    lines.append("run all")

    tcl = "\n".join(lines)
    with open("run.tcl", "w") as f:
        f.write(tcl)

class GowinToolchain():

    attr_translate = {
        "keep":             None,
        "no_retiming":      None,
        "async_reg":        None,
        "mr_ff":            None,
        "mr_false_path":    None,
        "ars_ff1":          None,
        "ars_ff2":          None,
        "ars_false_path":   None,
        "no_shreg_extract": None
    }

    def __init__(self):
        self.options = {}

    def build(self, platform, fragment,
        build_dir      = "build",
        build_name     = "top",
        run            = True,
        **kwargs):

        # Create build directory
        cwd = os.getcwd()
        os.makedirs(build_dir, exist_ok=True)
        os.chdir(build_dir)

        # Finalize design
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        platform.finalize(fragment)

        # Generate verilog
        v_output = platform.get_verilog(fragment, name=build_name, **kwargs)
        named_sc, named_pc = platform.resolve_signals(v_output.ns)
        v_file = build_name + ".v"
        v_output.write(v_file)
        platform.add_source(v_file)
        
        if platform.verilog_include_paths:
            self.options['include_path'] = '{' + ';'.join(platform.verilog_include_paths) + '}'

        # Generate constraints file (.cst)
        _build_cst(
            named_sc                = named_sc,
            named_pc                = named_pc)

        # Generate TCL build script
        script = _build_script(
            name                    = platform.devicename,
            partnumber              = platform.device,
            files                   = platform.sources,
            options                 = self.options)

        # Run
        if run:
            subprocess.run(["gw_sh", "run.tcl"])

        os.chdir(cwd)

        return v_output.ns
