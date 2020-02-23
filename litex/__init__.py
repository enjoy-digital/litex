# https://packaging.python.org/guides/packaging-namespace-packages/#pkgutil-style-namespace-packages
__path__ = __import__('pkgutil').extend_path(__path__, __name__)

import sys

# retro-compat 2019-09-30
from litex.soc.interconnect import packet
sys.modules["litex.soc.interconnect.stream_packet"] = packet

# retro-compat 2019-09-29
from litex.soc.integration import export
sys.modules["litex.soc.integration.cpu_interface"] = export

from litex.tools.litex_client import RemoteClient
