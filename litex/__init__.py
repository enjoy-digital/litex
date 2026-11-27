import sys

# Migen/Python 3.14+ Compatibility -----------------------------------------------------------------

# Migen's tracer.get_var_name, with the arguments given by EXTENDED_ARG: a name whose index is above
# 255 (ex: past the 256th name of a SoC __init__) is stored by EXTENDED_ARG + STORE_ATTR. Migen stops
# at the EXTENDED_ARG and returns None: the object is then named after its class, and its signals
# change names when names are added earlier in the function.
def _migen_get_var_name(frame):
    from opcode import opname
    from migen.fhdl import tracer

    code       = frame.f_code
    call_index = frame.f_lasti
    while call_index > 0 and opname[code.co_code[call_index]] == "CACHE":
        call_index -= 2
    while opname[code.co_code[call_index]] == "EXTENDED_ARG":
        call_index += 2
    call_opc = opname[code.co_code[call_index]]
    if call_opc not in tracer._call_opcodes:
        return None
    index        = call_index + tracer._call_opcodes[call_opc]
    extended_arg = 0
    while True:
        opc = opname[code.co_code[index]]
        arg = (extended_arg << 8) | code.co_code[index + 1]
        if opc == "EXTENDED_ARG":
            extended_arg = arg
            index       += 2
            continue
        extended_arg = 0
        if opc in ["STORE_NAME", "STORE_ATTR"]:
            return code.co_names[arg]
        elif opc == "STORE_FAST":
            return code.co_varnames[arg]
        elif opc == "STORE_DEREF":
            if arg < code.co_nlocals:
                return code.co_varnames[arg]
            arg -= code.co_nlocals
            if arg < len(code.co_cellvars):
                return code.co_cellvars[arg]
            arg -= len(code.co_cellvars)
            return code.co_freevars[arg]
        elif opc in tracer._load_build_opcodes:
            index += tracer._load_build_opcodes[opc]
        else:
            return None

def _migen_python_compat():
    try:
        from migen.fhdl import tracer
    except ImportError:
        return

    for opcode in ["LOAD_FAST_BORROW", "LOAD_FAST_CHECK"]:
        tracer._load_build_opcodes.setdefault(opcode, tracer._bytecode_length_version_guard(3))

    tracer.get_var_name = _migen_get_var_name


_migen_python_compat()

from litex.tools.litex_client import RemoteClient

# Python-Data Import Helper ------------------------------------------------------------------------

def get_data_mod(data_type, data_name):
    """Get the pythondata-{}-{} module or raise a useful error message."""
    imp = "import pythondata_{}_{} as dm".format(data_type, data_name)
    try:
        l = {}
        exec(imp, {}, l)
        dm = l['dm']
        return dm
    except ImportError as e:
        raise ImportError("""\
pythondata-{dt}-{dn} module not installed! Unable to use {dn} {dt}.
{e}

You can install this by running;
 pip3 install git+https://github.com/litex-hub/pythondata-{dt}-{dn}.git
""".format(dt=data_type, dn=data_name, e=e)) from None
