from liteeth.common import *
from liteeth.generic.depacketizer import LiteEthDepacketizer
from liteeth.generic.packetizer import LiteEthPacketizer
from liteeth.generic.crossbar import LiteEthCrossbar

class LiteEthIPV4Depacketizer(LiteEthDepacketizer):
	def __init__(self):
		LiteEthDepacketizer.__init__(self,
			eth_mac_description(8),
			eth_ipv4_description(8),
			ipv4_header,
			ipv4_header_len)

class LiteEthIPV4Packetizer(LiteEthPacketizer):
	def __init__(self):
		LiteEthPacketizer.__init__(self,
			eth_ipv4_description(8),
			eth_mac_description(8),
			ipv4_header,
			ipv4_header_len)

class LiteEthIPV4MasterPort:
	def __init__(self, dw):
		self.dw = dw
		self.source = Source(eth_ipv4_user_description(dw))
		self.sink = Sink(eth_ipv4_user_description(dw))

class LiteEthIPV4SlavePort:
	def __init__(self, dw):
		self.dw = dw
		self.sink = Sink(eth_ipv4_user_description(dw))
		self.source = Source(eth_ipv4_user_description(dw))

class LiteEthIPV4UserPort(LiteEthIPV4SlavePort):
	def __init__(self, dw):
		LiteEthIPV4SlavePort.__init__(self, dw)

class LiteEthIPV4Crossbar(LiteEthCrossbar):
	def __init__(self):
		LiteEthCrossbar.__init__(self, LiteEthIPV4MasterPort, "protocol")

	def get_port(self, protocol):
		if protocol in self.users.keys():
			raise ValueError("Protocol {0:#x} already assigned".format(protocol))
		port = LiteEthIPV4UserPort(8)
		self.users[protocol] = port
		return port

class LiteEthIPV4Checksum(Module):
	def __init__(self, words_per_clock_cycle=1, skip_checksum=False):
		self.reset = Signal() # XXX FIXME InsertReset generates incorrect verilog
		self.ce = Signal()    # XXX FIXME InsertCE generates incorrect verilog
		self.header = Signal(ipv4_header_len*8)
		self.value = Signal(16)
		self.done = Signal()
		###
		s = Signal(17)
		r = Signal(17)
		n_cycles = 0
		for i in range(ipv4_header_len//2):
			if skip_checksum and (i == ipv4_header["checksum"].byte//2):
				pass
			else:
				s_next = Signal(17)
				r_next = Signal(17)
				self.comb += s_next.eq(r + self.header[i*16:(i+1)*16])
				r_next_eq = r_next.eq(Cat(s_next[:16]+s_next[16], Signal()))
				if (i%words_per_clock_cycle) != 0:
					self.comb += r_next_eq
				else:
					self.sync += \
						If(self.reset,
							r_next.eq(0)
						).Elif(self.ce & ~self.done,
							r_next_eq
						)
					n_cycles += 1
				s, r = s_next, r_next
		self.comb += self.value.eq(~Cat(r[8:16], r[:8]))

		if not skip_checksum:
			n_cycles += 1
		self.submodules.counter = counter = Counter(max=n_cycles+1)
		self.comb += [
			counter.reset.eq(self.reset),
			counter.ce.eq(self.ce & ~self.done),
			self.done.eq(counter.value == n_cycles)
		]
