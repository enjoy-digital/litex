from migen.fhdl.std import *
from migen.bus.transactions import *
from migen.bus import wishbone
from migen.genlib.misc import timeline
from migen.genlib.record import Record
from migen.bank.description import AutoCSR, CSRStorage, CSRStatus

_FAST_READ = 0x0b
_DIOFR = 0xbb
_QIOFR = 0xeb

def _format_cmd(cmd, spi_width):
	"""
	`cmd` is the read instruction. Since everything is transmitted on all
	dq lines (cmd, adr and data), extend/interleave cmd to full pads.dq
	width even if dq1-dq3 are don't care during the command phase:
	For example, for N25Q128, 0xeb is the quad i/o fast read, and
	extended to 4 bits (dq1,dq2,dq3 high) is: 0xfffefeff
	"""
	c = 2**(8*spi_width)-1
	for b in range(8):
		if not (cmd>>b)%2:
			c &= ~(1<<(b*spi_width))
	return c

class SpiFlash(Module, AutoCSR):
	def __init__(self, pads, dummy=15, div=2, with_bitbang=True):
		"""
		Simple SPI flash, e.g. N25Q128 on the LX9 Microboard.

		Supports multi-bit pseudo-parallel reads (aka Dual or Quad I/O Fast
		Read). Only supports mode0 (cpol=0, cpha=0).
		Optional supports software bitbanging (for write, erase, or other commands).
		"""
		self.bus = bus = wishbone.Interface()
		spi_width = flen(pads.dq)
		if with_bitbang:
			self.bitbang = CSRStorage(4)
			self.miso = CSRStatus()
			self.bitbang_en = CSRStorage()

		##

		cs_n = Signal(reset=1)
		clk = Signal()
		dq_oe = Signal()
		wbone_width = flen(bus.dat_r)


		read_cmd_params = {
			4: (_format_cmd(_QIOFR, 4), 4*8),
			2: (_format_cmd(_DIOFR, 2), 2*8),
			1: (_format_cmd(_FAST_READ, 1), 1*8)
		}
		read_cmd, cmd_width = read_cmd_params[spi_width]
		addr_width = 24

		pads.cs_n.reset = 1

		dq = TSTriple(spi_width)
		self.specials.dq = dq.get_tristate(pads.dq)

		sr = Signal(max(cmd_width, addr_width, wbone_width))
		dqs = Replicate(1, spi_width-1)

		self.comb += bus.dat_r.eq(sr)

		hw_read_logic = [
			pads.clk.eq(clk),
			pads.cs_n.eq(cs_n),
			dq.o.eq(sr[-spi_width:]),
			dq.oe.eq(dq_oe)
		]

		if with_bitbang:
			bitbang_logic = [
				pads.clk.eq(self.bitbang.storage[1]),
				pads.cs_n.eq(self.bitbang.storage[2]),
				dq.o.eq(Cat(self.bitbang.storage[0], dqs)),
				If(self.bitbang.storage[3],
					dq.oe.eq(0)
				).Else(
					dq.oe.eq(1)
				),
				If(self.bitbang.storage[1],
					self.miso.status.eq(dq.i[-1])
				)
			]

			self.comb += \
				If(self.bitbang_en.storage,
					bitbang_logic
				).Else(
					hw_read_logic
				)
		else:
			self.comb += hw_read_logic

		if div < 2:
			raise ValueError("Unsupported value \'{}\' for div parameter for SpiFlash core".format(div))
		else:
			i = Signal(max=div)
			dqi = Signal(spi_width)
			self.sync += [
				If(i == div//2 - 1,
					clk.eq(1),
					dqi.eq(dq.i),
				),
				If(i == div - 1,
					i.eq(0),
					clk.eq(0),
					sr.eq(Cat(dqi, sr[:-spi_width]))
				).Else(
					i.eq(i + 1),
				),
			]

		# spi is byte-addressed, prefix by zeros
		z = Replicate(0, log2_int(wbone_width//8))

		seq = [
			(cmd_width//spi_width*div,
				[dq_oe.eq(1), cs_n.eq(0), sr[-cmd_width:].eq(read_cmd)]),
			(addr_width//spi_width*div,
				[sr[-addr_width:].eq(Cat(z, bus.adr))]),
			((dummy + wbone_width//spi_width)*div,
				[dq_oe.eq(0)]),
			(1,
				[bus.ack.eq(1), cs_n.eq(1)]),
			(div, # tSHSL!
				[bus.ack.eq(0)]),
			(0,
				[]),
		]

		# accumulate timeline deltas
		t, tseq = 0, []
		for dt, a in seq:
			tseq.append((t, a))
			t += dt

		self.sync += timeline(bus.cyc & bus.stb & (i == div - 1), tseq)

class SpiFlashTB(Module):
	def __init__(self):
		self.submodules.master = wishbone.Initiator(self.gen_reads())
		self.pads = Record([("cs_n", 1), ("clk", 1), ("dq", 4)])
		self.submodules.slave = SpiFlash(self.pads)
		self.submodules.tap = wishbone.Tap(self.slave.bus)
		self.submodules.intercon = wishbone.InterconnectPointToPoint(
				self.master.bus, self.slave.bus)
		self.cycle = 0

	def gen_reads(self):
		for a in range(10):
			t = TRead(a)
			yield t
			print("read {} in {} cycles(s)".format(t.data, t.latency))

	def do_simulation(self, selfp):
		if selfp.pads.cs_n:
			self.cycle = 0
		else:
			self.cycle += 1
			if not selfp.slave.dq.oe:
				selfp.slave.dq.i = self.cycle & 0xf
	do_simulation.passive = True

if __name__ == "__main__":
	from migen.sim.generic import run_simulation
	from migen.fhdl import verilog

	pads = Record([("cs_n", 1), ("clk", 1), ("dq", 4)])
	s = SpiFlash(pads)
	print(verilog.convert(s, ios={pads.clk, pads.cs_n, pads.dq, s.bus.adr,
		s.bus.dat_r, s.bus.cyc, s.bus.ack, s.bus.stb}))

	run_simulation(SpiFlashTB(), vcd_name="spiflash.vcd")
