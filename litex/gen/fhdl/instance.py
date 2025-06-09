#
# This file is part of LiteX (Adapted from Migen for LiteX usage).
#
# This file is Copyright (c) 2013-2014 Sebastien Bourdeauducq <sb@m-labs.hk>
# This file is Copyright (c) 2023 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen.fhdl.structure import *
from migen.fhdl.specials  import *

from litex.gen.fhdl.expression import _generate_expression

# Helpers ------------------------------------------------------------------------------------------

def get_max_name_length(ios):
    r = 0
    for io in ios:
        if len(io.name) > r:
            r = len(io.name)
    return r

# LiteX Instance Verilog Generation ----------------------------------------------------------------

def _instance_generate_verilog(instance, ns, add_data_file):
    r = ""

    # Instance Description.
    # ---------------------
    r += "//" + "-"*78 + "\n"
    r += f"// Instance {ns.get_name(instance)} of {instance.of} Module.\n"
    r += "//" + "-"*78 + "\n"

    # Instance Name.
    # --------------
    r += instance.of + " "

    # Instance Parameters.
    # --------------------
    parameters = list(filter(lambda i: isinstance(i, Instance.Parameter), instance.items))
    ident      = get_max_name_length(parameters)
    if parameters:
        r += "#(\n"
        first = True
        r += "\t// Parameters.\n"
        for p in parameters:
            if not first:
                r += ",\n"
            first = False
            r += f"\t.{p.name}{' '*(ident-len(p.name))} ("
            # Constant.
            if isinstance(p.value, Constant):
                r += _generate_expression(ns, p.value)[0]
            # Float.
            elif isinstance(p.value, float):
                r += str(p.value)
            # Preformatted.
            elif isinstance(p.value, Instance.PreformattedParam):
                r += p.value
            # String.
            elif isinstance(p.value, str):
                r += f"\"{p.value}\""
            else:
                raise TypeError
            r += ")"
        r += "\n) "

    # Instance IOs.
    # -------------
    r += ns.get_name(instance)
    if parameters:
        r += " "
    r += "("
    inputs  = list(filter(lambda i: isinstance(i, Instance.Input),  instance.items))
    outputs = list(filter(lambda i: isinstance(i, Instance.Output), instance.items))
    inouts  = list(filter(lambda i: isinstance(i, Instance.InOut),  instance.items))
    first   = True
    ident   = get_max_name_length(inputs + outputs + inouts)
    for io in (inputs + outputs + inouts):
        if not first:
            r += ",\n"
        if len(inputs) and (io is inputs[0]):
            r += "\n\t// Inputs.\n"
        if len(outputs) and (io is outputs[0]):
            r += "\n\t// Outputs.\n"
        if len(inouts) and (io is inouts[0]):
            r += "\n\t// InOuts.\n"
        name_inst   = io.name
        # Check if we need special handling for sliced signals with _reg mappings
        if hasattr(ns, '_reg_signal_mappings'):
            from litex.gen.fhdl.verilog import _resolve_instance_expression
            name_design = _resolve_instance_expression(ns, io.expr)[0]
        else:
            name_design = _generate_expression(ns, io.expr)[0]
        first = False
        r += f"\t.{name_inst}{' '*(ident-len(name_inst))} ({name_design})"
    if not first:
        r += "\n"

    # Instance Synthesis Directive.
    # -----------------------------
    if instance.synthesis_directive is not None:
        synthesis_directive = f"/* synthesis {instance.synthesis_directive} */"
        r += f"){synthesis_directive};\n"
    else:
        r += ");\n"

    r += "\n"

    return r
