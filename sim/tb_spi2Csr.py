from migen.fhdl.structure import *
from migen.fhdl import verilog, autofragment

import sys
sys.path.append("../")
import spi2Csr


spi2csr0 = spi2Csr.Spi2Csr(16,8)
