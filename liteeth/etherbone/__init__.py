# This file is Copyright (c) 2014 Robert Jordens <jordens@gmail.com>
# License: BSD

import struct
from collections import namedtuple

from migen.fhdl.std import *
from migen.bus import wishbone
from migen.genlib.record import Record
from migen.genlib.fsm import FSM, NextState
from migen.genlib.fifo import SyncFIFO
from migen.genlib.misc import optree
from migen.actorlib.structuring import Cast, Pack, Unpack, pack_layout
from migen.actorlib.sim import SimActor
from migen.bus.transactions import TRead, TWrite
from migen.flow.transactions import Token
from migen.flow.actor import Source, Sink
from migen.flow.network import DataFlowGraph, CompositeActor


_eb_width = 32 # addr and data
_eb_queue_len = 32
_eb_magic = 0x4e6f
_eb_ver = 1
_eb_hdr = [
		("magic", 16),
		("ver", 4),
		("res1", 1),
		("no_response", 1),
		("probe_res", 1),
		("probe", 1),
		("addr_size", 4),
		("data_size", 4),
	][::-1] # big-endian

_eb_rec_hdr = [
		("bca_cfg", 1),
		("rca_cfg", 1),
		("rd_fifo", 1),
		("res1", 1),
		("drop_cyc", 1),
		("wca_cfg", 1),
		("wr_fifo", 1),
		("res2", 1),
		("sel", 8),
		("wr_cnt", 8),
		("rd_cnt", 8),
	][::-1] # big-endian

_eb_layout = [("data", _eb_width)]


class Config(Module):
	def __init__(self, sdb_addr):
		self.errreg = Signal(8*8)
		mach = Signal(4*8, reset=0xd15e)
		macl = Signal(4*8, reset=0xa5edbeef)
		self.mac = Signal(6*8)
		self.comb += self.mac.eq(Cat(macl, mach))
		self.ip = Signal(4*8, reset=0xc0a80064)
		self.port = Signal(4*8, reset=0xebd0)

		self.bus = bus = wishbone.Interface()
		self.submodules.fifo = SyncFIFO(3, _eb_queue_len)

		read_mux = Array([self.errreg[32:], self.errreg[:32], 0,
			sdb_addr, mach, macl, self.ip, self.port])
		write_mux = Array([mach, macl, self.ip, self.port])[bus.adr - 4]

		self.dout = read_mux[self.fifo.dout]
		self.comb += [
				bus.ack.eq(bus.cyc & bus.stb),
				bus.dat_r.eq(read_mux[bus.adr[:3]]),
				]
		self.sync += [
				If(bus.cyc & bus.stb & bus.we & optree("|",
						[bus.adr[:3] == i for i in (4, 5, 6, 7)]),
					write_mux.eq(bus.dat_w),
				)]

class WishboneMaster(Module):
	def __init__(self, timeout):
		self.bus = bus = wishbone.Interface()
		self.submodules.fifo = SyncFIFO(_eb_width + 1, _eb_queue_len)

		self.active = Signal()
		inflight = Signal(max=_eb_queue_len)
		queued = Signal(max=_eb_queue_len)
		self.sync += [
				inflight.eq(inflight + self.active - self.fifo.we),
				queued.eq(queued + self.active - self.fifo.re),
				]

		self.busy = Signal()
		self.full = Signal()
		self.comb += [
				self.busy.eq(inflight != 0),
				self.full.eq(queued == _eb_queue_len - 1),
				]

		kill_ack = Signal()
		time = Signal(max=timeout)
		self.comb += kill_ack.eq(time == timeout - 1)
		self.sync += [
				If(self.fifo.we | ~self.busy,
					time.eq(0),
				).Else(
					time.eq(time + 1),
				)]

		self.comb += [
				self.fifo.we.eq(bus.ack | bus.err | kill_ack),
				self.fifo.din.eq(Cat(bus.dat_r, ~bus.ack)),
				]

		self.errreg = Signal(64)
		self.sync += [
				If(self.fifo.re,
					self.errreg.eq(Cat(self.fifo.dout[-1], self.errreg)),
				)]

class Transmit(Module):
	def __init__(self, pas, cfg, wbm, tag, tags):
		self.tx = Source(_eb_layout)

		data = Signal(_eb_width)
		re = Signal(4)
		self.tx_cyc = Signal()
		self.tx_skip = Signal()
		last_tx_cyc = Signal()
		last_tx_skip = Signal()
		readable = Signal()

		self.sync += [
				last_tx_cyc.eq(self.tx_cyc),
				last_tx_skip.eq(self.tx_skip),
				]

		self.comb += [
				readable.eq(Cat(tag.readable, pas.readable,
					cfg.fifo.readable, wbm.readable) & re == re),
				self.tx.stb.eq(readable & (re[1:] != 0)),
				self.tx.payload.data.eq(data),
				Case(tag.dout, {
					tags["PASS_TX"]: [re.eq(0b0011), data.eq(pas.dout)],
					tags["PASS_ON"]: [re.eq(0b0011), data.eq(pas.dout)],
					tags["CFG_REQ"]: [re.eq(0b0101), data.eq(cfg.dout)],
					tags["CFG_IGN"]: [re.eq(0b0111), data.eq(pas.dout)],
					tags["WBM_REQ"]: [re.eq(0b1001), data.eq(wbm.dout)],
					tags["WBM_IGN"]: [re.eq(0b1011), data.eq(pas.dout)],
					"default": [re.eq(0b0001)],
					}),
				If(readable & (self.tx.ack | (re[1:] == 0)),
					Cat(tag.re, pas.re, cfg.fifo.re, wbm.re).eq(re),
				),
				If(tag.readable,
					If(tag.dout == tags["PASS_TX"],
						self.tx_cyc.eq(1),
						self.tx_skip.eq(0),
					).Elif(tag.dout == tags["SKIP_TX"],
						self.tx_cyc.eq(0),
						self.tx_skip.eq(1),
					).Elif(tag.dout == tags["DROP_TX"],
						self.tx_cyc.eq(0),
						self.tx_skip.eq(0),
					).Else(
						self.tx_cyc.eq(last_tx_cyc),
						self.tx_skip.eq(last_tx_skip),
					),
				).Else(
					self.tx_cyc.eq(last_tx_cyc),
					self.tx_skip.eq(last_tx_skip),
				),
				]

class Receive(Module):
	def __init__(self, pas, cfg, wbm, tag, tags):
		self.rx = Sink(_eb_layout)

		rx_rec_hdr = Record(_eb_rec_hdr)
		tx_rec_hdr = Record(_eb_rec_hdr)
		rx_eb_hdr = Record(_eb_hdr)
		tx_eb_hdr = Record(_eb_hdr)
		self.comb += [
				rx_eb_hdr.raw_bits().eq(self.rx.payload.data),
				tx_eb_hdr.magic.eq(rx_eb_hdr.magic),
				tx_eb_hdr.ver.eq(_eb_ver),
				tx_eb_hdr.no_response.eq(1),
				tx_eb_hdr.addr_size.eq(4),
				tx_eb_hdr.data_size.eq(4),
				tx_eb_hdr.probe_res.eq(rx_eb_hdr.probe),

				rx_rec_hdr.raw_bits().eq(self.rx.payload.data),
				tx_rec_hdr.wca_cfg.eq(rx_rec_hdr.bca_cfg),
				tx_rec_hdr.wr_fifo.eq(rx_rec_hdr.rd_fifo),
				tx_rec_hdr.wr_cnt.eq(rx_rec_hdr.rd_cnt),
				tx_rec_hdr.sel.eq(rx_rec_hdr.sel),
				tx_rec_hdr.drop_cyc.eq(rx_rec_hdr.drop_cyc),
				]

		do_rx = Signal()
		self.rx_cyc = Signal()
		self.comb += [
				wbm.bus.sel.eq(rx_rec_hdr.sel),
				do_rx.eq(tag.writable & # tag is always written/read
					self.rx_cyc & self.rx.stb & # have data
					(wbm.fifo.we | ~wbm.bus.stb) & # stb finished or idle
					(wbm.bus.cyc | ~wbm.busy)), # in-cycle or idle
				self.rx.ack.eq(do_rx),
				cfg.fifo.din.eq(wbm.bus.adr),
				# no eb-cfg write support yet
				#cfg.dat_w.eq(wbm.bus.dat_w),
				#cfg.we.eq(wbm.bus.we),
				cfg.errreg.eq(wbm.errreg),
				]

		cur_rx_rec_hdr = Record(_eb_rec_hdr)
		cur_tx_rec_hdr = Record(_eb_rec_hdr)
		do_rec = Signal()
		do_adr = Signal()
		do_write = Signal()
		do_read = Signal()
		wr_adr = Signal(flen(wbm.bus.adr))
		old_rx_cyc = Signal()
		self.sync += [
				wbm.bus.stb.eq(wbm.bus.stb & ~wbm.fifo.we),
				wbm.bus.cyc.eq(wbm.bus.cyc & (
					~cur_rx_rec_hdr.drop_cyc |
					(cur_rx_rec_hdr.wr_cnt > 0) |
					(cur_rx_rec_hdr.rd_cnt > 0))),
				If(do_rec,
					cur_rx_rec_hdr.eq(rx_rec_hdr),
					cur_tx_rec_hdr.eq(tx_rec_hdr),
				),
				If(do_adr,
					wr_adr.eq(self.rx.payload.data[2:]),
				),
				If(do_write,
					If(cur_rx_rec_hdr.wca_cfg,
						cfg.fifo.we.eq(1),
					).Else(
						wbm.bus.cyc.eq(1),
						wbm.bus.stb.eq(1),
					),
					wbm.bus.we.eq(1),
					wbm.bus.adr.eq(wr_adr),
					wbm.bus.dat_w.eq(self.rx.payload.data),
					If(~cur_rx_rec_hdr.wr_fifo,
						wr_adr.eq(wr_adr + 1),
					),
					cur_rx_rec_hdr.wr_cnt.eq(cur_rx_rec_hdr.wr_cnt - 1),
				),
				If(do_read,
					If(cur_rx_rec_hdr.rca_cfg,
						cfg.fifo.we.eq(1),
					).Else(
						wbm.bus.cyc.eq(1),
						wbm.bus.stb.eq(1),
					),
					wbm.bus.we.eq(0),
					wbm.bus.adr.eq(self.rx.payload.data[2:]),
					cur_rx_rec_hdr.rd_cnt.eq(cur_rx_rec_hdr.rd_cnt - 1),
				),
				If(~self.rx_cyc,
					wbm.bus.cyc.eq(0),
				),
				old_rx_cyc.eq(self.rx_cyc),
				]

		fsm = self.submodules.fsm = FSM()
		fsm.reset_state = "EB_HDR"
		fsm.act("EB_HDR",
				If(do_rx,
					tag.we.eq(1),
					If((rx_eb_hdr.magic != _eb_magic) |
							(rx_eb_hdr.ver !=_eb_ver),
						tag.din.eq(tags["SKIP_TX"]),
						NextState("DROP"),
					).Else(
						If(rx_eb_hdr.no_response,
							tag.din.eq(tags["SKIP_TX"]),
						).Else(
							tag.din.eq(tags["PASS_TX"]),
							pas.we.eq(1),
							pas.din.eq(tx_eb_hdr.raw_bits()),
						),
						If(rx_eb_hdr.probe,
							If(rx_eb_hdr.addr_size[2] &
									rx_eb_hdr.data_size[2],
								NextState("PROBE_ID"),
							).Else(
								NextState("PROBE_DROP"),
							),
						).Else(
							If((rx_eb_hdr.addr_size == 4) &
									(rx_eb_hdr.data_size == 4),
								NextState("CYC_HDR"),
							).Else(
								NextState("DROP"),
							),
						),
					),
				))
		fsm.act("PROBE_DROP",
				If(do_rx,
					tag.we.eq(1),
					tag.din.eq(tags["PASS_ON"]),
					pas.we.eq(1),
					pas.din.eq(self.rx.payload.data),
					NextState("DROP"),
				))
		fsm.act("PROBE_ID",
				If(do_rx,
					tag.we.eq(1),
					tag.din.eq(tags["PASS_ON"]),
					pas.we.eq(1),
					pas.din.eq(self.rx.payload.data),
					NextState("CYC_HDR"),
				))
		fsm.act("CYC_HDR",
				If(do_rx,
					do_rec.eq(1),
					tag.we.eq(1),
					tag.din.eq(tags["PASS_ON"]),
					pas.we.eq(1),
					If(rx_rec_hdr.wr_cnt != 0,
						NextState("WR_ADR"),
					).Else(
						pas.din.eq(tx_rec_hdr.raw_bits()),
						If(rx_rec_hdr.rd_cnt != 0,
							NextState("RD_ADR"),
						).Else(
							NextState("CYC_HDR"),
						),
					),
				))
		fsm.act("WR_ADR",
				If(do_rx,
					do_adr.eq(1),
					tag.we.eq(1),
					tag.din.eq(tags["PASS_ON"]),
					pas.we.eq(1),
					NextState("WRITE"),
				))
		fsm.act("WRITE",
				If(do_rx,
					do_write.eq(1),
					tag.we.eq(1),
					If(cur_rx_rec_hdr.wca_cfg,
						tag.din.eq(tags["CFG_IGN"]),
					).Else(
						wbm.active.eq(1),
						tag.din.eq(tags["WBM_IGN"]),
					),
					pas.we.eq(1),
					If(cur_rx_rec_hdr.wr_cnt == 1,
						pas.din.eq(cur_tx_rec_hdr.raw_bits()),
						If(cur_rx_rec_hdr.rd_cnt != 0,
							NextState("RD_ADR"),
						).Else(
							NextState("CYC_HDR"),
						),
					),
				))
		fsm.act("RD_ADR",
				If(do_rx,
					tag.we.eq(1),
					tag.din.eq(tags["PASS_ON"]),
					pas.we.eq(1),
					pas.din.eq(self.rx.payload.data),
					NextState("READ"),
				))
		fsm.act("READ",
				If(do_rx,
					do_read.eq(1),
					tag.we.eq(1),
					If(cur_rx_rec_hdr.rca_cfg,
						tag.din.eq(tags["CFG_REQ"]),
					).Else(
						wbm.active.eq(1),
						tag.din.eq(tags["WBM_REQ"]),
					),
					If(cur_rx_rec_hdr.rd_cnt == 1,
						NextState("CYC_HDR"),
					),
				))
		fsm.act("DROP",
				#If(do_rx,
				#	tag.we.eq(1),
				#	tag.din.eq(tags["PASS_ON"]),
				#	pas.we.eq(1),
				#)
				)
		for state in fsm.actions:
			fsm.act(state, If(~self.rx_cyc, NextState("EB_HDR")))
		self.comb += [
				If(~self.rx_cyc,
					Cat(do_rec, do_adr, do_write, do_read).eq(0),
					Cat(wbm.active, pas.we).eq(0),
					If(old_rx_cyc,
						tag.we.eq(1),
						tag.din.eq(tags["DROP_TX"]),
					),
				)]

class Slave(Module):
	def __init__(self, sdb_addr, timeout):
		tags = dict((k, i) for i, k in enumerate(
			"DROP_TX SKIP_TX PASS_TX PASS_ON CFG_REQ "
			"CFG_IGN WBM_REQ WBM_IGN".split()))
		tag_width = flen(Signal(max=len(tags)))

		self.submodules.pas = SyncFIFO(_eb_width, _eb_queue_len)
		self.submodules.cfg = Config(sdb_addr)
		self.submodules.wbm = WishboneMaster(timeout)
		self.submodules.tag = SyncFIFO(tag_width, _eb_queue_len)

		self.submodules.rxfsm = Receive(self.pas, self.cfg,
				self.wbm, self.tag, tags)
		self.rx = self.rxfsm.rx
		self.rx_cyc = self.rxfsm.rx_cyc
		self.submodules.txmux = Transmit(self.pas, self.cfg,
				self.wbm.fifo, self.tag, tags)
		self.tx = self.txmux.tx
		self.tx_skip = self.txmux.tx_skip
		self.tx_cyc = self.txmux.tx_cyc
		self.busy = self.wbm.busy

class Converter(Module):
	def __init__(self, raw_width, graph, **slave_kwargs):
		raw_layout = [("data", raw_width)]
		pack_factor = _eb_width//raw_width

		self.rx = Sink(raw_layout)
		rx_pack = Pack(raw_layout, pack_factor)
		rx_cast = Cast(pack_layout(raw_layout, pack_factor), _eb_layout)
		self.submodules.slave = Slave(**slave_kwargs)
		tx_cast = Cast(_eb_layout, pack_layout(raw_layout, pack_factor))
		tx_unpack = Unpack(pack_factor, raw_layout)
		self.tx = Source(raw_layout)

		graph.add_connection(self.rx, rx_pack)
		graph.add_connection(rx_pack, rx_cast)
		graph.add_connection(rx_cast, self.slave.rx)
		graph.add_connection(self.slave.tx, tx_cast)
		graph.add_connection(tx_cast, tx_unpack)
		graph.add_connection(tx_unpack, self.tx)

class SimTx(SimActor):
	def __init__(self, data):
		self.tx = Source(_eb_layout)
		SimActor.__init__(self, self.gen(data))

	def gen(self, data):
		for i in data:
			yield Token("tx", {"data": i})
			print("eb tx", hex(i))

class SimRx(SimActor):
	def __init__(self):
		self.rx = Sink(_eb_layout)
		self.recv = []
		SimActor.__init__(self, self.gen())

	def gen(self):
		while True:
			t = Token("rx")
			yield t
			print("eb rx", hex(t.value["data"]))
			self.recv.append(t.value["data"])

class TB(Module):
	def __init__(self, data):
		ebm_tx = SimTx(data)
		ebm_rx = SimRx()
		self.slave = Slave(0x200, 10)
		g = DataFlowGraph()
		g.add_connection(ebm_tx, self.slave)
		g.add_connection(self.slave, ebm_rx)
		self.submodules.graph = CompositeActor(g)
		self.submodules.cfg_master = wishbone.Initiator(self.gen_cfg_reads())
		self.submodules.cfg_tap = wishbone.Tap(self.slave.cfg.bus,
				lambda l: print("cfg", l))
		self.submodules.wbm_tap = wishbone.Tap(self.slave.wbm.bus,
				lambda l: print("wbm", l))
		self.submodules.xbar = wishbone.Crossbar(
				[self.cfg_master.bus, self.slave.wbm.bus],
				[
					(lambda a: a[6:] == 0x0, wishbone.Target(
						wishbone.TargetModel()).bus),
					(lambda a: a[6:] == 0x1, self.slave.cfg.bus),
				])

	def gen_cfg_reads(self):
		for a in range(0x40, 0x40+4):
			t = TRead(a)
			yield t

	def do_simulation(self, s):
		#s.interrupt = self.cfg_master.done
		s.wr(self.slave.rx_cyc, int(s.cycle_counter < 200))

class MyStruct(object):
	_data = None
	_fmt = "!"

	def __init__(self, **kwargs):
		self.data = self._data(**kwargs)

	def __bytes__(self):
		return struct.pack(self._fmt, *self.data)

class EbHeader(MyStruct):
	_data = namedtuple("eb_hdr", "magic ver size")
	_fmt = "!HBB"

	def __init__(self, probe_id=None, addr_size=4, data_size=4, records=[]):
		no_response = not any(r.read for r in records)
		probe = probe_id is not None
		probe_res = False
		MyStruct.__init__(self, magic=_eb_magic, ver=(_eb_ver<<4) |
				(no_response<<2) | (probe_res<<1) | (probe<<0),
				size=(addr_size<<4) | (data_size<<0))
		self.probe = struct.pack("!I", probe_id) if probe else b""
		self.records = records

	def __bytes__(self):
		return (MyStruct.__bytes__(self) + self.probe +
				b"".join(map(bytes, self.records)))

class EbRecord(MyStruct):
	_data = namedtuple("eb_rec", "flags sel wr_cnt rd_cnt")
	_fmt = "!BBBB"

	def __init__(self, sel=0xf, wr_adr=0, rd_adr=0, write=[], read=[],
			bca_cfg=False, rca_cfg=False, rd_fifo=False, drop_cyc=False,
			wca_cfg=False, wr_fifo=False):
		MyStruct.__init__(self, sel=sel, wr_cnt=len(write),
				rd_cnt=len(read), flags=(bca_cfg<<7) | (rca_cfg<<6) |
					(rd_fifo<<5) | (drop_cyc<<3) | (wca_cfg<<2) |
					(wr_fifo>>1))
		self.wr_adr = wr_adr
		self.write = write
		self.rd_adr = rd_adr
		self.read = read

	def __bytes__(self):
		b = MyStruct.__bytes__(self)
		if self.write:
			b += struct.pack("!I" + "I"*len(self.write), self.wr_adr,
					*self.write)
		if self.read:
			b += struct.pack("!I" + "I"*len(self.read), self.rd_adr,
					*self.read)
		return b

def main():
	from migen.sim.generic import Simulator, TopLevel

	#from migen.fhdl import verilog
	#s = Slave(0, 10)
	#print(verilog.convert(s, ios={s.rx.payload.data, s.tx.payload.data,
	#	s.rx.stb, s.rx.ack, s.tx.stb, s.tx.ack}))

	eb_pkt = EbHeader(records=[
				EbRecord(wr_adr=0x10, write=[0x20, 0x21],
					rd_adr=0x30, read=range(0, 8, 4)),
				EbRecord(rd_adr=0x40, read=range(0x100, 0x100+32, 4),
					drop_cyc=True),
				EbRecord(rca_cfg=True, bca_cfg=True, rd_adr=0x50,
					read=range(0, 0+8, 4), drop_cyc=True),
				])
	eb_pkt = bytes(eb_pkt)
	eb_pkt = struct.unpack("!" + "I"*(len(eb_pkt)//4), eb_pkt)
	tb = TB(eb_pkt)
	sim = Simulator(tb, TopLevel("etherbone.vcd"))
	sim.run(500)


if __name__ == "__main__":
	main()