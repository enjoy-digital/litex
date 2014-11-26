from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus import dfi as dfibus
from migen.genlib.fsm import FSM, NextState

class _AddressSlicer:
	def __init__(self, col_a, bank_a, row_a, address_align):
		self.col_a = col_a
		self.bank_a = bank_a
		self.row_a = row_a
		self.max_a = col_a + row_a + bank_a
		self.address_align = address_align

	def row(self, address):
		split = self.bank_a + self.col_a
		if isinstance(address, int):
			return address >> split
		else:
			return address[split:self.max_a]

	def bank(self, address):
		mask = 2**(self.bank_a + self.col_a) - 1
		shift = self.col_a
		if isinstance(address, int):
			return (address & mask) >> shift
		else:
			return address[self.col_a:self.col_a+self.bank_a]

	def col(self, address):
		split = self.col_a
		if isinstance(address, int):
			return (address & (2**split - 1)) << self.address_align
		else:
			return Cat(Replicate(0, self.address_align), address[:split])

class Minicon(Module):
	def __init__(self, phy_settings, geom_settings, timing_settings):
		if phy_settings.memtype in ["SDR"]:
			burst_length = phy_settings.nphases*1 # command multiplication*SDR
		elif phy_settings.memtype in ["DDR", "LPDDR", "DDR2", "DDR3"]:
			burst_length = phy_settings.nphases*2 # command multiplication*DDR
		address_align = log2_int(burst_length)

		nbanks = range(2**geom_settings.bank_a)
		A10_ENABLED = 0
		COLUMN      = 1
		ROW         = 2
		rdphase = phy_settings.rdphase
		wrphase = phy_settings.wrphase
		rdcmdphase = phy_settings.rdcmdphase
		wrcmdphase = phy_settings.wrcmdphase

		self.dfi = dfi = dfibus.Interface(geom_settings.mux_a,
				geom_settings.bank_a,
				phy_settings.dfi_d,
				phy_settings.nphases)

		self.bus = bus = wishbone.Interface(data_width=phy_settings.nphases*flen(dfi.phases[rdphase].rddata))
		slicer = _AddressSlicer(geom_settings.col_a, geom_settings.bank_a, geom_settings.row_a, address_align)
		req_addr = Signal(geom_settings.col_a + geom_settings.bank_a + geom_settings.row_a)
		refresh_req = Signal()
		refresh_ack = Signal()
		wb_access = Signal()
		refresh_counter = Signal(max=timing_settings.tREFI+1)
		hit = Signal()
		row_open = Signal()
		row_closeall = Signal()
		addr_sel = Signal(max=3, reset=A10_ENABLED)
		has_curbank_openrow = Signal()
		cl_counter = Signal(max=phy_settings.cl+1)

		# Extra bit means row is active when asserted
		self.openrow = openrow = Array(Signal(geom_settings.row_a + 1) for b in nbanks)

		self.comb += [
			hit.eq(openrow[slicer.bank(bus.adr)] == Cat(slicer.row(bus.adr), 1)),
			has_curbank_openrow.eq(openrow[slicer.bank(bus.adr)][-1]),
			wb_access.eq(bus.stb & bus.cyc),
			bus.dat_r.eq(Cat([phase.rddata for phase in dfi.phases])),
			Cat([phase.wrdata for phase in dfi.phases]).eq(bus.dat_w),
			Cat([phase.wrdata_mask for phase in dfi.phases]).eq(~bus.sel),
		]

		for phase in dfi.phases:
			self.comb += [
				phase.cke.eq(1),
				phase.address.eq(Array([2**10, slicer.col(bus.adr), slicer.row(bus.adr)])[addr_sel]),
				If(wb_access,
					phase.bank.eq(slicer.bank(bus.adr))
				)
			]
			phase.cs_n.reset = 0
			phase.ras_n.reset = 1
			phase.cas_n.reset = 1
			phase.we_n.reset = 1

		for b in nbanks:
			self.sync += [
				If(row_open & (b == slicer.bank(bus.adr)),
					openrow[b].eq(Cat(slicer.row(bus.adr), 1)),
				),
				If(row_closeall,
					openrow[b][-1].eq(0)
				)
			]

		self.sync += [
			If(refresh_ack,
				refresh_req.eq(0)
			),
			If(refresh_counter == 0,
				refresh_counter.eq(timing_settings.tREFI),
				refresh_req.eq(1)
			).Else(
				refresh_counter.eq(refresh_counter - 1)
			)
		]

		fsm = FSM()
		self.submodules += fsm
		fsm.act("IDLE",
			If(refresh_req,
				NextState("PRECHARGEALL")
			).Elif(wb_access,
                                If(hit & bus.we,
                                        NextState("WRITE"),
                                ),
                                If(hit & ~bus.we,
                                        NextState("READ"),
                                ),
                                If(has_curbank_openrow & ~hit,
                                        NextState("PRECHARGE")
                                ),
                                If(~has_curbank_openrow,
                                        NextState("ACTIVATE")
                                ),
                        )
		)
		fsm.act("READ",
			# We output Column bits at address pins so that A10 is 0
			# to disable row Auto-Precharge
			dfi.phases[rdcmdphase].ras_n.eq(1),
			dfi.phases[rdcmdphase].cas_n.eq(0),
			dfi.phases[rdcmdphase].we_n.eq(1),
			dfi.phases[rdphase].rddata_en.eq(1),
			addr_sel.eq(COLUMN),
			NextState("READ-WAIT-ACK"),
		)
		fsm.act("READ-WAIT-ACK",
			If(dfi.phases[rdphase].rddata_valid,
				NextState("IDLE"),
				bus.ack.eq(1)
			).Else(
				NextState("READ-WAIT-ACK")
			)
		)
		fsm.act("WRITE",
			dfi.phases[wrcmdphase].ras_n.eq(1),
			dfi.phases[wrcmdphase].cas_n.eq(0),
			dfi.phases[wrcmdphase].we_n.eq(0),
			dfi.phases[wrphase].wrdata_en.eq(1),
			addr_sel.eq(COLUMN),
			bus.ack.eq(1),
			NextState("IDLE")
		)
		fsm.act("PRECHARGEALL",
			row_closeall.eq(1),
			dfi.phases[rdphase].ras_n.eq(0),
			dfi.phases[rdphase].cas_n.eq(1),
			dfi.phases[rdphase].we_n.eq(0),
			addr_sel.eq(A10_ENABLED),
			NextState("PRE-REFRESH")
		)
		fsm.act("PRECHARGE",
			# Notes:
			# 1. we are presenting the column address so that A10 is low
			# 2. since we always go to the ACTIVATE state, we do not need
			# to assert row_close because it will be reopen right after.
			NextState("TRP"),
			addr_sel.eq(COLUMN),
			dfi.phases[rdphase].ras_n.eq(0),
			dfi.phases[rdphase].cas_n.eq(1),
			dfi.phases[rdphase].we_n.eq(0)
		)
		fsm.act("ACTIVATE",
			row_open.eq(1),
			NextState("TRCD"),
			dfi.phases[rdphase].ras_n.eq(0),
			dfi.phases[rdphase].cas_n.eq(1),
			dfi.phases[rdphase].we_n.eq(1),
			addr_sel.eq(ROW)
		)
		fsm.act("REFRESH",
			refresh_ack.eq(1),
			dfi.phases[rdphase].ras_n.eq(0),
			dfi.phases[rdphase].cas_n.eq(0),
			dfi.phases[rdphase].we_n.eq(1),
			NextState("POST-REFRESH")
		)
		fsm.delayed_enter("TRP", "ACTIVATE", timing_settings.tRP-1)
		fsm.delayed_enter("PRE-REFRESH", "REFRESH", timing_settings.tRP-1)
		fsm.delayed_enter("TRCD", "IDLE", timing_settings.tRCD-1)
		fsm.delayed_enter("POST-REFRESH", "IDLE", timing_settings.tRFC-1)
