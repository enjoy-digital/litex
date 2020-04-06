import sys

# retro-compat 2019-09-30
from litex.soc.interconnect import packet
sys.modules["litex.soc.interconnect.stream_packet"] = packet

# retro-compat 2019-09-29
from litex.soc.integration import export
sys.modules["litex.soc.integration.cpu_interface"] = export

from litex.tools.litex_client import RemoteClient

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
 pip install git+https://github.com/litex-hub/pythondata-{dt}-{dn}.git
""".format(dt=data_type, dn=data_name, e=e))
