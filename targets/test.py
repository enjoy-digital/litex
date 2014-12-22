import os

from migen.fhdl.std import *
from migen.bank import csrgen
from migen.bus import wishbone, csr
from migen.bus import wishbone2csr
from migen.genlib.resetsync import AsyncResetSynchronizer
from migen.bank.description import *

from miscope import MiLa, Term, UART2Wishbone
from miscope.uart2wishbone import UART2Wishbone

from misoclib import identifier
from lib.sata.common import *
from lib.sata.phy import SATAPHY
from lib.sata import SATACON
from lib.sata.bist import SATABIST

from migen.genlib.cdc import *

class _CRG(Module):
	def __init__(self, platform):
		self.clock_domains.cd_sys = ClockDomain()
		self.clock_domains.cd_por = ClockDomain(reset_less=True)

		clk200 = platform.request("clk200")
		clk200_se = Signal()
		self.specials += Instance("IBUFDS", i_I=clk200.p, i_IB=clk200.n, o_O=clk200_se)

		pll_locked = Signal()
		pll_fb = Signal()
		pll_sys = Signal()
		self.specials += [
			Instance("PLLE2_BASE",
				p_STARTUP_WAIT="FALSE", o_LOCKED=pll_locked,

				# VCO @ 1GHz
				p_REF_JITTER1=0.01, p_CLKIN1_PERIOD=5.0,
				p_CLKFBOUT_MULT=5, p_DIVCLK_DIVIDE=1,
				i_CLKIN1=clk200_se, i_CLKFBIN=pll_fb, o_CLKFBOUT=pll_fb,

				# 100MHz
				p_CLKOUT0_DIVIDE=5, p_CLKOUT0_PHASE=0.0, o_CLKOUT0=pll_sys,

				p_CLKOUT1_DIVIDE=2, p_CLKOUT1_PHASE=0.0, #o_CLKOUT1=,

				p_CLKOUT2_DIVIDE=2, p_CLKOUT2_PHASE=0.0, #o_CLKOUT2=,

				p_CLKOUT3_DIVIDE=2, p_CLKOUT3_PHASE=0.0, #o_CLKOUT3=,

				p_CLKOUT4_DIVIDE=2, p_CLKOUT4_PHASE=0.0, #o_CLKOUT4=
			),
			Instance("BUFG", i_I=pll_sys, o_O=self.cd_sys.clk),
			AsyncResetSynchronizer(self.cd_sys, ~pll_locked | platform.request("cpu_reset")),
		]

class UART2WB(Module):
	csr_base = 0x00000000
	csr_data_width = 8
	csr_map = {
		"uart2wb":			0,
		"identifier":		2,
	}
	interrupt_map = {}
	cpu_type = None
	def __init__(self, platform, clk_freq):
		self.uart2wb = UART2Wishbone(platform.request("serial"), clk_freq, baud=921600)

		# CSR bridge   0x00000000 (shadow @0x00000000)
		self.wishbone2csr = wishbone2csr.WB2CSR(bus_csr=csr.Interface(self.csr_data_width))
		self._wb_masters = [self.uart2wb.wishbone]
		self._wb_slaves = [(lambda a: a[23:25] == 0, self.wishbone2csr.wishbone)]
		self.cpu_csr_regions = [] # list of (name, origin, busword, csr_list/Memory)


		# CSR
		self.identifier = identifier.Identifier(0, int(clk_freq), 0)

	def add_wb_master(self, wbm):
		if self.finalized:
			raise FinalizeError
		self._wb_masters.append(wbm)

	def add_wb_slave(self, address_decoder, interface):
		if self.finalized:
			raise FinalizeError
		self._wb_slaves.append((address_decoder, interface))

	def add_cpu_memory_region(self, name, origin, length):
		self.cpu_memory_regions.append((name, origin, length))

	def add_cpu_csr_region(self, name, origin, busword, obj):
		self.cpu_csr_regions.append((name, origin, busword, obj))

	def do_finalize(self):
		# Wishbone
		self.wishbonecon = wishbone.InterconnectShared(self._wb_masters,
			self._wb_slaves, register=True)

		# CSR
		self.csrbankarray = csrgen.BankArray(self,
			lambda name, memory: self.csr_map[name if memory is None else name + "_" + memory.name_override],
			data_width=self.csr_data_width)
		self.csrcon = csr.Interconnect(self.wishbone2csr.csr, self.csrbankarray.get_buses())
		for name, csrs, mapaddr, rmap in self.csrbankarray.banks:
			self.add_cpu_csr_region(name, 0xe0000000+0x800*mapaddr, flen(rmap.bus.dat_w), csrs)
		for name, memory, mapaddr, mmap in self.csrbankarray.srams:
			self.add_cpu_csr_region(name, 0xe0000000+0x800*mapaddr, flen(rmap.bus.dat_w), memory)

class SimDesign(UART2WB):
	default_platform = "kc705"

	def __init__(self, platform, export_mila=False):
		clk_freq = 200*1000000
		UART2WB.__init__(self, platform, clk_freq)
		self.crg = _CRG(platform)

		self.sata_phy_host = SATAPHY(platform.request("sata_host"), clk_freq, host=True)
		self.comb += [
			self.sata_phy_host.sink.stb.eq(1),
			self.sata_phy_host.sink.data.eq(primitives["SYNC"]),
			self.sata_phy_host.sink.charisk.eq(0b0001)
		]
		self.sata_phy_device = SATAPHY(platform.request("sata_device"), clk_freq, host=False)
		self.comb += [
			self.sata_phy_device.sink.stb.eq(1),
			self.sata_phy_device.sink.data.eq(primitives["SYNC"]),
			self.sata_phy_device.sink.charisk.eq(0b0001)
		]

class ClockLeds(Module):
	def __init__(self, platform):
		led_sata_rx = platform.request("user_led", 0)
		led_sata_tx = platform.request("user_led", 1)

		sata_rx_cnt = Signal(32)
		sata_tx_cnt = Signal(32)

		self.sync.sata_rx += \
			If(sata_rx_cnt == 0,
				led_sata_rx.eq(~led_sata_rx),
				sata_rx_cnt.eq(150*1000*1000//2)
			).Else(
				sata_rx_cnt.eq(sata_rx_cnt-1)
			)

		self.sync.sata_tx += \
			If(sata_tx_cnt == 0,
				led_sata_tx.eq(~led_sata_tx),
				sata_tx_cnt.eq(150*1000*1000//2)
			).Else(
				sata_tx_cnt.eq(sata_tx_cnt-1)
			)


class CommandGenerator(Module, AutoCSR):
	def __init__(self, sata_con, sector_size):
		self._write = CSR()
		self._read = CSR()
		self._identify = CSR()
		self._sector = CSRStorage(48)
		self._count = CSRStorage(4)
		self._data = CSRStorage(32) # Note: fixed data, add a fifo later

		self._sucess = CSRStatus()
		self._failed = CSRStatus()

		self.fsm = fsm = FSM(reset_state="IDLE")

		def new_command(csr):
			return csr.r & csr.re

		cnt = Signal(16)
		sector = self._sector.storage
		count = self._count.storage
		data = self._data.storage

		success = self._sucess.status
		failed = self._failed.status
		clr_status = Signal()
		set_success = Signal()
		set_failed = Signal()
		self.sync += [
			If(clr_status,
				success.eq(0),
				failed.eq(0),
			).Elif(set_success,
				success.eq(1)
			).Elif(set_failed,
				failed.eq(1)
			)
		]

		self.comb += sata_con.source.ack.eq(1)

		# FSM
		fsm.act("IDLE",
			clr_status.eq(1),
			If(new_command(self._write),
				NextState("SEND_WRITE_CMD")
			).Elif(new_command(self._read),
				NextState("SEND_READ_CMD")
			).Elif(new_command(self._identify),
				NextState("SEND_IDENTIFY_CMD")
			)
		)
		fsm.act("SEND_WRITE_CMD",
			sata_con.sink.stb.eq(1),
			sata_con.sink.sop.eq(cnt == 0),
			sata_con.sink.eop.eq(cnt == (count*sector_size-1)),
			sata_con.sink.write.eq(1),
			sata_con.sink.sector.eq(sector),
			sata_con.sink.count.eq(count),
			sata_con.sink.data.eq(data),
			If(sata_con.sink.eop & sata_con.sink.ack,
				NextState("WAIT_WRITE_ACK")
			)
		)
		self.sync += [
			If(fsm.ongoing("IDLE"),
				cnt.eq(0)
			).Elif(sata_con.sink.stb & sata_con.sink.stb,
				cnt.eq(cnt+1)
			)
		]
		fsm.act("WAIT_WRITE_ACK",
			# XXX: add check of success / failed
			If(sata_con.source.stb & sata_con.source.eop,
				set_success.eq(1),
				NextState("IDLE")
			)
		)
		fsm.act("SEND_READ_CMD",
			sata_con.sink.stb.eq(1),
			sata_con.sink.sop.eq(1),
			sata_con.sink.eop.eq(1),
			sata_con.sink.read.eq(1),
			sata_con.sink.sector.eq(sector),
			sata_con.sink.count.eq(count),
			If(sata_con.sink.ack,
				NextState("WAIT_READ_ACK_AND_DATA")
			)
		)
		fsm.act("WAIT_READ_ACK_AND_DATA",
			# XXX: add check of success / failed and receive data
			If(sata_con.source.stb & sata_con.source.eop,
				set_success.eq(1),
				NextState("IDLE")
			)
		)
		fsm.act("SEND_IDENTIFY_CMD",
			sata_con.sink.stb.eq(1),
			sata_con.sink.sop.eq(1),
			sata_con.sink.eop.eq(1),
			sata_con.sink.identify.eq(1),
			If(sata_con.sink.ack,
				NextState("WAIT_IDENTIFY_ACK_AND_DATA")
			)
		)
		fsm.act("WAIT_IDENTIFY_ACK_AND_DATA",
			# XXX: add check of success / failed and receive data
			If(sata_con.source.stb & sata_con.source.eop,
				set_success.eq(1),
				NextState("IDLE")
			)
		)

class BIST(Module, AutoCSR):
	def __init__(self, sata_con, sector_size):
		self._start = CSR()
		self._sector = CSRStorage(48)
		self._count = CSRStorage(4)
		self._done = CSRStatus()

		self._ctrl_errors = CSRStatus(32)
		self._data_errors = CSRStatus(32)

		###

		self.sata_bist = SATABIST(sector_size)
		self.comb += [
			Record.connect(self.sata_bist.source, sata_con.sink),
			Record.connect(sata_con.source, self.sata_bist.sink),

			self.sata_bist.start.eq(self._start.r & self._start.re),
			self.sata_bist.sector.eq(self._sector.storage),
			self.sata_bist.count.eq(self._count.storage),
			self._done.status.eq(self.sata_bist.done),

			self._ctrl_errors.status.eq(self.sata_bist.ctrl_errors),
			self._data_errors.status.eq(self.sata_bist.data_errors),
		]

class TestDesign(UART2WB, AutoCSR):
	default_platform = "kc705"
	csr_map = {
		"mila":					10,
		"command_generator":	11,
		"bist":					12
	}
	csr_map.update(UART2WB.csr_map)

	def __init__(self, platform, export_mila=False):
		clk_freq = 200*1000000
		UART2WB.__init__(self, platform, clk_freq)
		self.crg = _CRG(platform)

		self.sata_phy = SATAPHY(platform.request("sata_host"), clk_freq, host=True, speed="SATA2")
		self.sata_con = SATACON(self.sata_phy, sector_size=512, max_count=8)

		#self.command_generator = CommandGenerator(self.sata_con, sector_size=512)
		self.bist = BIST(self.sata_con, sector_size=512)

		self.clock_leds = ClockLeds(platform)

		self.comb += platform.request("user_led", 2).eq(self.sata_phy.crg.ready)
		self.comb += platform.request("user_led", 3).eq(self.sata_phy.ctrl.ready)

		ctrl = self.sata_phy.ctrl

		self.command_tx_fsm_state = Signal(4)
		self.transport_tx_fsm_state = Signal(4)
		self.link_tx_fsm_state = Signal(4)

		self.command_rx_fsm_state = Signal(4)
		self.command_rx_out_fsm_state = Signal(4)
		self.transport_rx_fsm_state = Signal(4)
		self.link_rx_fsm_state = Signal(4)

		debug = (
			ctrl.ready,
			ctrl.sink.data,
			ctrl.sink.charisk,

			self.sata_phy.source.stb,
			self.sata_phy.source.data,
			self.sata_phy.source.charisk,

			self.sata_phy.sink.stb,
			self.sata_phy.sink.data,
			self.sata_phy.sink.charisk,

			self.sata_con.sink.stb,
			self.sata_con.sink.sop,
			self.sata_con.sink.eop,
			self.sata_con.sink.ack,
			self.sata_con.sink.write,
			self.sata_con.sink.read,
			self.sata_con.sink.identify,

			self.sata_con.source.stb,
			self.sata_con.source.sop,
			self.sata_con.source.eop,
			self.sata_con.source.ack,
			self.sata_con.source.write,
			self.sata_con.source.read,
			self.sata_con.source.identify,
			self.sata_con.source.success,
			self.sata_con.source.failed,
			self.sata_con.source.data
		)

		self.mila = MiLa(depth=2048, dat=Cat(*debug))
		self.mila.add_port(Term)

		if export_mila:
			mila_filename = os.path.join(platform.soc_ext_path, "test", "mila.csv")
			self.mila.export(self, debug, mila_filename)

#default_subtarget = SimDesign
default_subtarget = TestDesign