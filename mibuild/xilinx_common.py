import os
from distutils.version import StrictVersion

from migen.fhdl.std import *
from migen.fhdl.specials import SynthesisDirective
from migen.genlib.cdc import *
from migen.genlib.resetsync import AsyncResetSynchronizer
from mibuild.generic_platform import GenericPlatform
from mibuild import tools

def settings(path, ver=None, sub=None):
	vers = list(tools.versions(path))
	if ver is None:
		ver = max(vers)
	else:
		ver = StrictVersion(ver)
		assert ver in vers

	full = os.path.join(path, str(ver))
	if sub:
		full = os.path.join(full, sub)

	search = [64, 32]
	if tools.arch_bits() == 32:
		search.reverse()

	for b in search:
		settings = os.path.join(full, "settings{0}.sh".format(b))
		if os.path.exists(settings):
			return settings

	raise ValueError("no settings file found")

class CRG_DS(Module):
	def __init__(self, platform, clk_name, rst_name, rst_invert=False):
		reset_less = rst_name is None
		self.clock_domains.cd_sys = ClockDomain(reset_less=reset_less)
		self._clk = platform.request(clk_name)
		self.specials += Instance("IBUFGDS",
			Instance.Input("I", self._clk.p),
			Instance.Input("IB", self._clk.n),
			Instance.Output("O", self.cd_sys.clk)
		)
		if not reset_less:
			if rst_invert:
				self.comb += self.cd_sys.rst.eq(~platform.request(rst_name))
			else:
				self.comb += self.cd_sys.rst.eq(platform.request(rst_name))

class XilinxNoRetimingImpl(Module):
	def __init__(self, reg):
		self.specials += SynthesisDirective("attribute register_balancing of {r} is no", r=reg)

class XilinxNoRetiming:
	@staticmethod
	def lower(dr):
		return XilinxNoRetimingImpl(dr.reg)

class XilinxMultiRegImpl(MultiRegImpl):
	def __init__(self, *args, **kwargs):
		MultiRegImpl.__init__(self, *args, **kwargs)
		self.specials += [SynthesisDirective("attribute shreg_extract of {r} is no", r=r)
			for r in self.regs]

class XilinxMultiReg:
	@staticmethod
	def lower(dr):
		return XilinxMultiRegImpl(dr.i, dr.o, dr.odomain, dr.n)

class XilinxAsyncResetSynchronizerImpl(Module):
	def __init__(self, cd, async_reset):
		rst1 = Signal()
		self.specials += [
			Instance("FDPE", p_INIT=1, i_D=0, i_PRE=async_reset,
				i_CE=1, i_C=cd.clk, o_Q=rst1),
			Instance("FDPE", p_INIT=1, i_D=rst1, i_PRE=async_reset,
				i_CE=1, i_C=cd.clk, o_Q=cd.rst)
		]

class XilinxAsyncResetSynchronizer:
	staticmethod
	def lower(dr):
		return XilinxAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)

class XilinxGenericPlatform(GenericPlatform):
	bitstream_ext = ".bit"

	def get_verilog(self, *args, special_overrides=dict(), **kwargs):
		so = {
			NoRetiming:					XilinxNoRetiming,
			MultiReg:					XilinxMultiReg,
			AsyncResetSynchronizer:		XilinxAsyncResetSynchronizer
		}
		so.update(special_overrides)
		return GenericPlatform.get_verilog(self, *args, special_overrides=so, **kwargs)

	def get_edif(self, fragment, **kwargs):
		return GenericPlatform.get_edif(self, fragment, "UNISIMS", "Xilinx", self.device, **kwargs)
