import sys
from litex.tools.litex_client import RemoteClient

# retro-compat 2019-09-29
from litex.soc.integration import export
sys.modules["litex.soc.integration.cpu_interface"] = export