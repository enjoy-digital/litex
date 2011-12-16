from migen.fhdl import structure as f
from migen.bus import csr

class Inst:
	def __init__(self, csr_addr, clk_freq, baud=115200, break_en_default=f.Constant(0)):
		self.bus = csr.Slave("uart")
		f.declare_signal(self, "tx")
		f.declare_signal(self, "rx")
		f.declare_signal(self, "irq")
		f.declare_signal(self, "brk")
		self._inst = f.Instance("uart",
			[("csr_do", self.bus.d_o),
			("uart_tx", self.tx),
			("irq", self.irq),
			("break", self.brk)],
			[("csr_a", self.bus.a_i),
			("csr_we", self.bus.we_i),
			("csr_di", self.bus.d_i),
			("uart_rx", self.rx)],
			[("csr_addr", f.Constant(csr_addr, f.BV(4))),
			("clk_freq", clk_freq),
			("baud", baud),
			("break_en_default", break_en_default)],
			"sys_clk",
			"sys_rst")
	
	def get_fragment(self):
		return f.Fragment(instances=[self._inst], pads={self.tx, self.rx})
