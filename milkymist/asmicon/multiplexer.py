import math

from migen.fhdl.structure import *
from migen.corelogic.roundrobin import *
from migen.corelogic.misc import multimux, optree
from migen.corelogic.fsm import FSM

class CommandRequest:
	def __init__(self, a, ba):
		self.a = Signal(BV(a))
		self.ba = Signal(BV(ba))
		self.cas_n = Signal(reset=1)
		self.ras_n = Signal(reset=1)
		self.we_n = Signal(reset=1)

class CommandRequestRW(CommandRequest):
	def __init__(self, a, ba, tagbits):
		CommandRequest.__init__(self, a, ba)
		self.stb = Signal()
		self.ack = Signal()
		self.is_read = Signal()
		self.is_write = Signal()
		self.tag = Signal(BV(tagbits))

class _CommandChooser:
	def __init__(self, requests, tagbits):
		self.requests = requests
		
		self.want_reads = Signal()
		self.want_writes = Signal()
		# NB: cas_n/ras_n/we_n are 1 when stb is inactive
		self.cmd = CommandRequestRW(self.requests[0].a.bv.width, self.requests[0].ba.bv.width, tagbits)
	
	def get_fragment(self):
		comb = []
		sync = []
		
		rr = RoundRobin(len(self.requests), SP_CE)
		
		comb += [rr.request[i].eq(req.stb & ((req.is_read == self.want_reads) | (req.is_write == self.want_writes)))
			for i, req in enumerate(self.requests)]
		
		stb = Signal()
		inputs_perm = [[req.stb,
			req.a, req.ba,
			req.is_read, req.is_write, req.tag] for req in self.requests]
		outputs_perm = [stb,
			self.cmd.a, self.cmd.ba,
			self.cmd.is_read, self.cmd.is_write, self.cmd.tag]
		comb += multimux(rr.grant, inputs_perm, outputs_perm)
		
		inputs_filtered = [[req.cas_n, req.ras_n, req.we_n] for req in self.requests]
		outputs_filtered = [self.cmd.cas_n, self.cmd.ras_n, self.cmd.we_n]
		ms = multimux(rr.grant, inputs_filtered, outputs_filtered)
		comb += [
			self.cmd.stb.eq(stb & (self.cmd.is_read == self.want_reads) & (self.cmd.is_write == self.want_writes)),
			If(self.cmd.stb, *ms)
		]
		
		comb += [If(self.cmd.stb & self.cmd.ack & (rr.grant == i), req.ack.eq(1))
			for i, req in enumerate(self.requests)]
		comb.append(rr.ce.eq(self.cmd.ack))
		
		return Fragment(comb, sync) + rr.get_fragment()

class _Steerer:
	def __init__(self, commands, dfi):
		self.commands = commands
		self.dfi = dfi
		
		ncmd = len(self.commands)
		nph = len(self.dfi.phases)
		self.sel = [Signal(BV(bits_for(ncmd-1))) for i in range(nph)]
	
	def get_fragment(self):
		comb = []
		sync = []
		def stb_and(cmd, attr):
			if not hasattr(cmd, "stb"):
				return Constant(0)
			else:
				return cmd.stb & getattr(cmd, attr)
		inputs = [[cmd.a, cmd.ba,
			cmd.cas_n, cmd.ras_n,
			cmd.we_n, stb_and(cmd, "is_read"), stb_and(cmd, "is_write")]
			for cmd in self.commands]
		for phase, sel in zip(self.dfi.phases, self.sel):
			comb += [
				phase.cke.eq(1),
				phase.cs_n.eq(0)
			]
			outputs = [phase.address, phase.bank,
				phase.cas_n, phase.ras_n, phase.we_n,
				phase.rddata_en, phase.wrdata_en]
			sync += multimux(sel, inputs, outputs)
		return Fragment(comb, sync)

class _Datapath:
	def __init__(self, timing_settings, command, dfi, hub):
		self.timing_settings = timing_settings
		self.command = command
		self.dfi = dfi
		self.hub = hub
	
	def get_fragment(self):
		comb = []
		sync = []
		tagbits = self.hub.tag_call.bv.width
		
		rd_valid = Signal()
		rd_tag = Signal(BV(tagbits))
		wr_valid = Signal()
		wr_tag = Signal(BV(tagbits))
		comb += [
			self.hub.call.eq(rd_valid | wr_valid),
			If(wr_valid,
				self.hub.tag_call.eq(wr_tag)
			).Else(
				self.hub.tag_call.eq(rd_tag)
			)
		]
		
		rd_valid_d = [Signal() for i in range(self.timing_settings.rd_delay)]
		rd_tag_d = [Signal(BV(tagbits)) for i in range(self.timing_settings.rd_delay)]
		for i in range(self.timing_settings.rd_delay):
			if i:
				sync += [
					rd_valid_d[i].eq(rd_valid_d[i-1]),
					rd_tag_d[i].eq(rd_tag_d[i-1])
				]
			else:
				sync += [
					rd_valid_d[i].eq(self.command.stb & self.command.ack & self.command.is_read),
					rd_tag_d[i].eq(self.command.tag)
				]		
		comb += [
			rd_valid.eq(rd_valid_d[-1]),
			rd_tag.eq(rd_tag_d[-1]),
			wr_valid.eq(self.command.stb & self.command.ack & self.command.is_write),
			wr_tag.eq(self.command.tag),
		]
		
		all_rddata = [p.rddata for p in self.dfi.phases]
		all_wrdata = [p.wrdata for p in self.dfi.phases]
		all_wrdata_mask = [p.wrdata_mask for p in self.dfi.phases]
		comb += [
			self.hub.dat_r.eq(Cat(*all_rddata)),
			Cat(*all_wrdata).eq(self.hub.dat_w),
			Cat(*all_wrdata_mask).eq(self.hub.dat_wm)
		]
		
		return Fragment(comb, sync)

class Multiplexer:
	def __init__(self, phy_settings, geom_settings, timing_settings, bank_machines, refresher, dfi, hub):
		self.phy_settings = phy_settings
		self.geom_settings = geom_settings
		self.timing_settings = timing_settings
		self.bank_machines = bank_machines
		self.refresher = refresher
		self.dfi = dfi
		self.hub = hub
		
		assert(self.phy_settings.nphases == len(dfi.phases))
		if self.phy_settings.nphases != 2:
			raise NotImplementedError("TODO: multiplexer only supports 2 phases")
	
	def get_fragment(self):
		comb = []
		sync = []
		
		# Command choosing
		requests = [bm.cmd for bm in self.bank_machines]
		tagbits = self.hub.tag_call.bv.width
		choose_cmd = _CommandChooser(requests, tagbits)
		choose_req = _CommandChooser(requests, tagbits)
		comb += [
			choose_cmd.want_reads.eq(0),
			choose_cmd.want_writes.eq(0)
		]
		
		# Command steering
		nop = CommandRequest(self.geom_settings.mux_a, self.geom_settings.bank_a)
		commands = [nop, choose_cmd.cmd, choose_req.cmd, self.refresher.cmd] # nop must be 1st
		(STEER_NOP, STEER_CMD, STEER_REQ, STEER_REFRESH) = range(4)
		steerer = _Steerer(commands, self.dfi)
		
		# Read/write turnaround
		read_available = Signal()
		write_available = Signal()
		comb += [
			read_available.eq(optree("|", [req.stb & req.is_read for req in requests])),
			write_available.eq(optree("|", [req.stb & req.is_write for req in requests]))
		]
		
		def anti_starvation(timeout):
			en = Signal()
			max_time = Signal()
			if timeout:
				t = timeout - 1
				time = Signal(BV(bits_for(t)))
				comb.append(max_time.eq(time == 0))
				sync.append(
					If(~en,
						time.eq(t)
					).Elif(~max_time,
						time.eq(time - 1)
					)
				)
			else:
				comb.append(max_time.eq(0))
			return en, max_time
		read_time_en, max_read_time = anti_starvation(self.timing_settings.read_time)
		write_time_en, max_write_time = anti_starvation(self.timing_settings.write_time)
		
		# Refresh
		refresh_w_ok = Signal()
		t_unsafe_refresh = 2 + self.timing_settings.tWR - 1
		unsafe_refresh_count = Signal(BV(bits_for(t_unsafe_refresh)))
		comb.append(refresh_w_ok.eq(unsafe_refresh_count == 0))
		sync += [
			If(choose_req.cmd.stb & choose_req.cmd.ack & choose_req.cmd.is_write,
				unsafe_refresh_count.eq(t_unsafe_refresh)
			).Elif(~refresh_w_ok,
				unsafe_refresh_count.eq(unsafe_refresh_count-1)
			)
		]
		# Reads cannot conflict with refreshes, since we have one idle cycle
		# (all bank machines in refresh state) before the PRECHARGE ALL command
		# from the refresher.
		comb += [bm.refresh_req.eq(self.refresher.req)
			for bm in self.bank_machines]
		comb.append(
			self.refresher.ack.eq(optree("&",
				[bm.refresh_gnt for bm in self.bank_machines]) \
				& refresh_w_ok)
		)
		
		# Datapath
		datapath = _Datapath(self.timing_settings, choose_req.cmd, self.dfi, self.hub)
		
		# Control FSM
		fsm = FSM("READ", "WRITE", "REFRESH", delayed_enters=[
			("RTW", "WRITE", math.ceil((self.timing_settings.CL+1)/2)),
			("WTR", "READ", self.timing_settings.tWR)
		])
		fsm.act(fsm.READ,
			read_time_en.eq(1),
			choose_req.want_reads.eq(1),
			choose_cmd.cmd.ack.eq(1),
			choose_req.cmd.ack.eq(1),
			steerer.sel[1-self.phy_settings.rdphase].eq(STEER_CMD),
			steerer.sel[self.phy_settings.rdphase].eq(STEER_REQ),
			If(write_available,
				# TODO: switch only after several cycles of ~read_available?
				If(~read_available | max_read_time, fsm.next_state(fsm.RTW))
			),
			If(self.refresher.ack, fsm.next_state(fsm.REFRESH))
		)
		fsm.act(fsm.WRITE,
			write_time_en.eq(1),
			choose_req.want_writes.eq(1),
			choose_cmd.cmd.ack.eq(1),
			choose_req.cmd.ack.eq(1),
			steerer.sel[1-self.phy_settings.wrphase].eq(STEER_CMD),
			steerer.sel[self.phy_settings.wrphase].eq(STEER_REQ),
			If(read_available,
				If(~write_available | max_write_time, fsm.next_state(fsm.WTR))
			),
			If(self.refresher.ack, fsm.next_state(fsm.REFRESH))
		)
		fsm.act(fsm.REFRESH,
			steerer.sel[0].eq(STEER_REFRESH),
			If(~self.refresher.req, fsm.next_state(fsm.READ))
		)
		
		return Fragment(comb, sync) + \
			choose_cmd.get_fragment() + \
			choose_req.get_fragment() + \
			steerer.get_fragment() + \
			datapath.get_fragment() + \
			fsm.get_fragment()
