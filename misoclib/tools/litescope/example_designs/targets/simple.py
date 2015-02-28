from migen.bank.description import *

from misoclib.soc import SoC
from misoclib.tools.litescope.common import *
from misoclib.tools.litescope.bridge.uart2wb import LiteScopeUART2WB
from misoclib.tools.litescope.frontend.io import LiteScopeIO
from misoclib.tools.litescope.frontend.la import LiteScopeLA
from misoclib.tools.litescope.core.port import LiteScopeTerm

class _CRG(Module):
	def __init__(self, clk_in):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_por = ClockDomain(reset_less=True)

		# Power on Reset (vendor agnostic)
		rst_n = Signal()
		self.sync.por += rst_n.eq(1)
		self.comb += [
			self.cd_sys.clk.eq(clk_in),
			self.cd_por.clk.eq(clk_in),
			self.cd_sys.rst.eq(~rst_n)
		]

class LiteScopeSoC(SoC, AutoCSR):
	csr_map = {
		"io":	16,
		"la":	17
	}
	csr_map.update(SoC.csr_map)
	def __init__(self, platform):
		clk_freq = int((1/(platform.default_clk_period))*1000000000)
		self.submodules.uart2wb = LiteScopeUART2WB(platform.request("serial"), clk_freq, baud=115200)
		SoC.__init__(self, platform, clk_freq, self.uart2wb,
			with_cpu=False,
			with_csr=True, csr_data_width=32,
			with_uart=False,
			with_identifier=True,
			with_timer=False
		)
		self.submodules.crg = _CRG(platform.request(platform.default_clk_name))

		self.submodules.io = LiteScopeIO(8)
		for i in range(8):
			try:
				self.comb += platform.request("user_led", i).eq(self.io.o[i])
			except:
				pass

		self.submodules.counter0 = counter0 = Counter(bits_sign=8)
		self.submodules.counter1 = counter1 = Counter(bits_sign=8)
		self.comb += [
			counter0.ce.eq(1),
			If(counter0.value == 16,
				counter0.reset.eq(1),
				counter1.ce.eq(1)
			)
		]

		self.debug = (
			counter1.value
		)
		self.submodules.la = LiteScopeLA(self.debug, 512, with_rle=True, with_subsampler=True)
		self.la.trigger.add_port(LiteScopeTerm(self.la.dw))

	def do_exit(self, vns):
		self.la.export(vns, "test/la.csv")

default_subtarget = LiteScopeSoC
