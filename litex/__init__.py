import sys

# Migen/Python 3.14+ patch -------------------------------------------------------------------------
try:
    import migen.fhdl.tracer
    if "LOAD_FAST_BORROW" not in migen.fhdl.tracer._load_build_opcodes:
        migen.fhdl.tracer._load_build_opcodes["LOAD_FAST_BORROW"] = migen.fhdl.tracer._bytecode_length_version_guard(3)
except ImportError:
    pass

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
