#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.structure import *
from migen.fhdl.verilog   import _printexpr as verilog_printexpr
from migen.fhdl.specials  import *

# LiteX Instance Verilog Generation ----------------------------------------------------------------

def _instance_generate_verilog(instance, ns, add_data_file):
    r = instance.of + " "

    # Instance Parameters.
    # --------------------
    parameters = list(filter(lambda i: isinstance(i, Instance.Parameter), instance.items))
    if parameters:
        r += "#(\n"
        first = True
        for p in parameters:
            if not first:
                r += ",\n"
            first = False
            r += "\t." + p.name + "("
            # Constant.
            if isinstance(p.value, Constant):
                r += verilog_printexpr(ns, p.value)[0]
            # Float.
            elif isinstance(p.value, float):
                r += str(p.value)
            # Preformatted.
            elif isinstance(p.value, Instance.PreformattedParam):
                r += p.value
            # String.
            elif isinstance(p.value, str):
                r += "\"" + p.value + "\""
            else:
                raise TypeError
            r += ")"
        r += "\n) "

    # Instance IOs.
    # -------------
    r += ns.get_name(instance)
    if parameters:
        r += " "
    r += "(\n"
    first = True
    for io in instance.items:
        if isinstance(io, Instance._IO):
            name_inst   = io.name
            name_design = verilog_printexpr(ns, io.expr)[0]
            if not first:
                r += ",\n"
            first = False
            r += "\t." + name_inst + "(" + name_design + ")"
    if not first:
        r += "\n"

    # Instance Synthesis Directive.
    # -----------------------------
    if instance.synthesis_directive is not None:
        synthesis_directive = f"/* synthesis {instance.synthesis_directive} */"
        r += ")" + synthesis_directive + ";\n"
    else:
        r += ");\n"

    r += "\n"

    return r
