#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.structure    import *
from migen.fhdl.verilog      import _printexpr as verilog_printexpr
from migen.fhdl.specials     import *

# LiteX Instance Verilog Generation ----------------------------------------------------------------

def _instance_generate_verilog(instance, ns, add_data_file):
    r = instance.of + " "
    parameters = list(filter(lambda i: isinstance(i, Instance.Parameter), instance.items))
    if parameters:
        r += "#(\n"
        firstp = True
        for p in parameters:
            if not firstp:
                r += ",\n"
            firstp = False
            r += "\t." + p.name + "("
            if isinstance(p.value, Constant):
                r += verilog_printexpr(ns, p.value)[0]
            elif isinstance(p.value, float):
                r += str(p.value)
            elif isinstance(p.value, Instance.PreformattedParam):
                r += p.value
            elif isinstance(p.value, str):
                r += "\"" + p.value + "\""
            else:
                raise TypeError
            r += ")"
        r += "\n) "
    r += ns.get_name(instance)
    if parameters: r += " "
    r += "(\n"
    firstp = True
    for p in instance.items:
        if isinstance(p, Instance._IO):
            name_inst = p.name
            name_design = verilog_printexpr(ns, p.expr)[0]
            if not firstp:
                r += ",\n"
            firstp = False
            r += "\t." + name_inst + "(" + name_design + ")"
    if not firstp:
        r += "\n"
    if instance.synthesis_directive is not None:
        synthesis_directive = "/* synthesis {} */".format(instance.synthesis_directive)
        r += ")" + synthesis_directive + ";\n\n"
    else:
        r += ");\n\n"
    return r
