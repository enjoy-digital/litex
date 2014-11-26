from migen.fhdl.std import *
from migen.genlib.roundrobin import *
from migen.genlib.misc import optree
from migen.genlib.fsm import FSM, NextState
from migen.bank.description import AutoCSR

from misoclib.sdram.lasmicon.perf import Bandwidth

class CommandRequest:
	def __init__(self, a, ba):
		self.a = Signal(a)
		self.ba = Signal(ba)
		self.cas_n = Signal(reset=1)
		self.ras_n = Signal(reset=1)
		self.we_n = Signal(reset=1)

class CommandRequestRW(CommandRequest):
	def __init__(self, a, ba):
		CommandRequest.__init__(self, a, ba)
		self.stb = Signal()
		self.ack = Signal()
		self.is_cmd = Signal()
		self.is_read = Signal()
		self.is_write = Signal()

class _CommandChooser(Module):
	def __init__(self, requests):
		self.want_reads = Signal()
		self.want_writes = Signal()
		self.want_cmds = Signal()
		# NB: cas_n/ras_n/we_n are 1 when stb is inactive
		self.cmd = CommandRequestRW(flen(requests[0].a), flen(requests[0].ba))

		###

		rr = RoundRobin(len(requests), SP_CE)
		self.submodules += rr

		self.comb += [rr.request[i].eq(req.stb & ((req.is_cmd & self.want_cmds) | ((req.is_read == self.want_reads) | (req.is_write == self.want_writes))))
			for i, req in enumerate(requests)]

		stb = Signal()
		self.comb += stb.eq(Array(req.stb for req in requests)[rr.grant])
		for name in ["a", "ba", "is_read", "is_write", "is_cmd"]:
			choices = Array(getattr(req, name) for req in requests)
			self.comb += getattr(self.cmd, name).eq(choices[rr.grant])
		for name in ["cas_n", "ras_n", "we_n"]:
			# we should only assert those signals when stb is 1
			choices = Array(getattr(req, name) for req in requests)
			self.comb += If(self.cmd.stb, getattr(self.cmd, name).eq(choices[rr.grant]))
		self.comb += self.cmd.stb.eq(stb \
			& ((self.cmd.is_cmd & self.want_cmds) | ((self.cmd.is_read == self.want_reads) \
			& (self.cmd.is_write == self.want_writes))))

		self.comb += [If(self.cmd.stb & self.cmd.ack & (rr.grant == i), req.ack.eq(1))
			for i, req in enumerate(requests)]
		self.comb += rr.ce.eq(self.cmd.ack)

class _Steerer(Module):
	def __init__(self, commands, dfi):
		ncmd = len(commands)
		nph = len(dfi.phases)
		self.sel = [Signal(max=ncmd) for i in range(nph)]

		###

		def stb_and(cmd, attr):
			if not hasattr(cmd, "stb"):
				return 0
			else:
				return cmd.stb & getattr(cmd, attr)
		for phase, sel in zip(dfi.phases, self.sel):
			self.comb += [
				phase.cke.eq(1),
				phase.cs_n.eq(0)
			]
			if hasattr(phase, "odt"):
				self.comb += phase.odt.eq(1)
			if hasattr(phase, "reset_n"):
				self.comb += phase.reset_n.eq(1)
			self.sync += [
				phase.address.eq(Array(cmd.a for cmd in commands)[sel]),
				phase.bank.eq(Array(cmd.ba for cmd in commands)[sel]),
				phase.cas_n.eq(Array(cmd.cas_n for cmd in commands)[sel]),
				phase.ras_n.eq(Array(cmd.ras_n for cmd in commands)[sel]),
				phase.we_n.eq(Array(cmd.we_n for cmd in commands)[sel]),
				phase.rddata_en.eq(Array(stb_and(cmd, "is_read") for cmd in commands)[sel]),
				phase.wrdata_en.eq(Array(stb_and(cmd, "is_write") for cmd in commands)[sel])
			]

class Multiplexer(Module, AutoCSR):
	def __init__(self, phy_settings, geom_settings, timing_settings, bank_machines, refresher, dfi, lasmic):
		assert(phy_settings.nphases == len(dfi.phases))

		# Command choosing
		requests = [bm.cmd for bm in bank_machines]
		choose_cmd = _CommandChooser(requests)
		choose_req = _CommandChooser(requests)
		self.comb += [
			choose_cmd.want_reads.eq(0),
			choose_cmd.want_writes.eq(0)
		]
		if phy_settings.nphases == 1:
			self.comb += [
				choose_cmd.want_cmds.eq(1),
				choose_req.want_cmds.eq(1)
			]
		self.submodules += choose_cmd, choose_req

		# Command steering
		nop = CommandRequest(geom_settings.mux_a, geom_settings.bank_a)
		commands = [nop, choose_cmd.cmd, choose_req.cmd, refresher.cmd] # nop must be 1st
		(STEER_NOP, STEER_CMD, STEER_REQ, STEER_REFRESH) = range(4)
		steerer = _Steerer(commands, dfi)
		self.submodules += steerer

		# Read/write turnaround
		read_available = Signal()
		write_available = Signal()
		self.comb += [
			read_available.eq(optree("|", [req.stb & req.is_read for req in requests])),
			write_available.eq(optree("|", [req.stb & req.is_write for req in requests]))
		]

		def anti_starvation(timeout):
			en = Signal()
			max_time = Signal()
			if timeout:
				t = timeout - 1
				time = Signal(max=t+1)
				self.comb += max_time.eq(time == 0)
				self.sync += If(~en,
						time.eq(t)
					).Elif(~max_time,
						time.eq(time - 1)
					)
			else:
				self.comb += max_time.eq(0)
			return en, max_time
		read_time_en, max_read_time = anti_starvation(timing_settings.read_time)
		write_time_en, max_write_time = anti_starvation(timing_settings.write_time)

		# Refresh
		self.comb += [bm.refresh_req.eq(refresher.req) for bm in bank_machines]
		go_to_refresh = Signal()
		self.comb += go_to_refresh.eq(optree("&", [bm.refresh_gnt for bm in bank_machines]))

		# Datapath
		all_rddata = [p.rddata for p in dfi.phases]
		all_wrdata = [p.wrdata for p in dfi.phases]
		all_wrdata_mask = [p.wrdata_mask for p in dfi.phases]
		self.comb += [
			lasmic.dat_r.eq(Cat(*all_rddata)),
			Cat(*all_wrdata).eq(lasmic.dat_w),
			Cat(*all_wrdata_mask).eq(~lasmic.dat_we)
		]

		# Control FSM
		fsm = FSM()
		self.submodules += fsm

		def steerer_sel(steerer, phy_settings, r_w_n):
			r = []
			for i in range(phy_settings.nphases):
				s = steerer.sel[i].eq(STEER_NOP)
				if r_w_n == "read":
					if i == phy_settings.rdphase:
						s = steerer.sel[i].eq(STEER_REQ)
					elif i == phy_settings.rdcmdphase:
						s = steerer.sel[i].eq(STEER_CMD)
				elif r_w_n == "write":
					if i == phy_settings.wrphase:
						s = steerer.sel[i].eq(STEER_REQ)
					elif i == phy_settings.wrcmdphase:
						s = steerer.sel[i].eq(STEER_CMD)
				else:
					raise ValueError
				r.append(s)
			return r

		fsm.act("READ",
			read_time_en.eq(1),
			choose_req.want_reads.eq(1),
			choose_cmd.cmd.ack.eq(1),
			choose_req.cmd.ack.eq(1),
			steerer_sel(steerer, phy_settings, "read"),
			If(write_available,
				# TODO: switch only after several cycles of ~read_available?
				If(~read_available | max_read_time, NextState("RTW"))
			),
			If(go_to_refresh, NextState("REFRESH"))
		)
		fsm.act("WRITE",
			write_time_en.eq(1),
			choose_req.want_writes.eq(1),
			choose_cmd.cmd.ack.eq(1),
			choose_req.cmd.ack.eq(1),
			steerer_sel(steerer, phy_settings, "write"),
			If(read_available,
				If(~write_available | max_write_time, NextState("WTR"))
			),
			If(go_to_refresh, NextState("REFRESH"))
		)
		fsm.act("REFRESH",
			steerer.sel[0].eq(STEER_REFRESH),
			If(~refresher.req, NextState("READ"))
		)
		fsm.delayed_enter("RTW", "WRITE", phy_settings.read_latency-1) # FIXME: reduce this, actual limit is around (cl+1)/nphases
		fsm.delayed_enter("WTR", "READ", timing_settings.tWTR-1)
		# FIXME: workaround for zero-delay loop simulation problem with Icarus Verilog
		fsm.finalize()
		self.comb += refresher.ack.eq(fsm.state == fsm.encoding["REFRESH"])

		self.submodules.bandwidth = Bandwidth(choose_req.cmd)
