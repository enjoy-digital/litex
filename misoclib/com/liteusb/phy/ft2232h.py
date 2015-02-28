from migen.fhdl.std import *
from migen.flow.actor import *
from migen.actorlib.fifo import AsyncFIFO
from migen.fhdl.specials import *

from liteusb.ftdi.std import *

class FtdiPHY(Module):
	def __init__(self, pads, fifo_depth=32, read_time=16, write_time=16):
		dw = flen(pads.data)

		#
		# Read / Write Fifos
		#

		# Read Fifo (Ftdi --> SoC)
		read_fifo = RenameClockDomains(AsyncFIFO(phy_layout, fifo_depth),
			{"write":"ftdi", "read":"sys"})
		read_buffer = RenameClockDomains(SyncFIFO(phy_layout, 4),
			{"sys":"ftdi"})
		self.comb += read_buffer.source.connect(read_fifo.sink)

		# Write Fifo (SoC --> Ftdi)
		write_fifo = RenameClockDomains(AsyncFIFO(phy_layout, fifo_depth),
			{"write":"sys", "read":"ftdi"})

		self.submodules += read_fifo, read_buffer, write_fifo

		#
		# Sink / Source interfaces
		#
		self.sink = write_fifo.sink
		self.source = read_fifo.source

		#
		# Read / Write Arbitration
		#
		wants_write = Signal()
		wants_read = Signal()

		txe_n = Signal()
		rxf_n = Signal()

		self.comb += [
			txe_n.eq(pads.txe_n),
			rxf_n.eq(pads.rxf_n),
			wants_write.eq(~txe_n & write_fifo.source.stb),
			wants_read.eq(~rxf_n & read_fifo.sink.ack),
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

		read_time_en, max_read_time = anti_starvation(read_time)
		write_time_en, max_write_time = anti_starvation(write_time)

		data_w_accepted  = Signal(reset=1)

		fsm = FSM()
		self.submodules += RenameClockDomains(fsm, {"sys": "ftdi"})

		fsm.act("READ",
			read_time_en.eq(1),
			If(wants_write,
				If(~wants_read | max_read_time, NextState("RTW"))
			)
		)
		fsm.act("RTW",
			NextState("WRITE")
		)
		fsm.act("WRITE",
			write_time_en.eq(1),
			If(wants_read,
				If(~wants_write | max_write_time, NextState("WTR"))
			),
			write_fifo.source.ack.eq(wants_write & data_w_accepted)
		)
		fsm.act("WTR",
			NextState("READ")
		)

		#
		# Read / Write Actions
		#

		data_w  = Signal(dw)
		data_r  = Signal(dw)
		data_oe = Signal()

		pads.oe_n.reset = 1
		pads.rd_n.reset = 1
		pads.wr_n.reset = 1

		self.sync.ftdi += [
			If(fsm.ongoing("READ"),
				data_oe.eq(0),

				pads.oe_n.eq(0),
				pads.rd_n.eq(~wants_read),
				pads.wr_n.eq(1)

			).Elif(fsm.ongoing("WRITE"),
				data_oe.eq(1),

				pads.oe_n.eq(1),
				pads.rd_n.eq(1),
				pads.wr_n.eq(~wants_write),

				data_w_accepted.eq(~txe_n)

			).Else(
				data_oe.eq(1),

				pads.oe_n.eq(~fsm.ongoing("WTR")),
				pads.rd_n.eq(1),
				pads.wr_n.eq(1)
			),
				read_buffer.sink.stb.eq(~pads.rd_n & ~rxf_n),
				read_buffer.sink.d.eq(data_r),
				If(~txe_n & data_w_accepted,
					data_w.eq(write_fifo.source.d)
				)
		]

		#
		# Databus Tristate
		#
		self.specials += Tristate(pads.data, data_w, data_oe, data_r)

		self.debug = Signal(8)
		self.comb += self.debug.eq(data_r)


#
# TB
#
class FtdiModel(Module, RandRun):
	def __init__(self, rd_data):
		RandRun.__init__(self, 50)
		self.rd_data = [0] + rd_data
		self.rd_idx = 0

		# pads
		self.data = Signal(8)
		self.rxf_n = Signal(reset=1)
		self.txe_n = Signal(reset=1)
		self.rd_n = Signal(reset=1)
		self.wr_n = Signal(reset=1)
		self.oe_n = Signal(reset=1)
		self.siwua = Signal()
		self.pwren_n = Signal(reset=1)

		self.init = True
		self.wr_data = []
		self.wait_wr_n = False
		self.rd_done = 0

	def wr_sim(self, selfp):
		if not selfp.wr_n and not selfp.txe_n:
			self.wr_data.append(selfp.data)
			self.wait_wr_n = False

		if not self.wait_wr_n:
			if self.run:
				selfp.txe_n = 1
			else:
				if selfp.txe_n:
					self.wait_wr_n = True
				selfp.txe_n = 0

	def rd_sim(self, selfp):
		rxf_n = selfp.rxf_n
		if self.run:
			if self.rd_idx < len(self.rd_data)-1:
				self.rd_done = selfp.rxf_n
				selfp.rxf_n = 0
			else:
				selfp.rxf_n = self.rd_done
		else:
			selfp.rxf_n = self.rd_done

		if not selfp.rd_n and not selfp.oe_n:
			if self.rd_idx < len(self.rd_data)-1:
				self.rd_idx += not rxf_n
			selfp.data = self.rd_data[self.rd_idx]
			self.rd_done = 1

	def do_simulation(self, selfp):
		RandRun.do_simulation(self, selfp)
		if self.init:
			selfp.rxf_n =  0
			self.wr_data = []
			self.init = False
		self.wr_sim(selfp)
		self.rd_sim(selfp)

class UserModel(Module, RandRun):
	def __init__(self, wr_data):
		RandRun.__init__(self, 50)
		self.wr_data = wr_data
		self.wr_data_idx = 0

		self.sink = Sink(phy_layout)
		self.source = Source(phy_layout)

		self.rd_data = []

	def wr_sim(self, selfp):
		auth = True
		if selfp.source.stb and not selfp.source.ack:
			auth = False
		if auth:
			if self.wr_data_idx < len(self.wr_data):
				if self.run:
					selfp.source.d = self.wr_data[self.wr_data_idx]
					selfp.source.stb = 1
					self.wr_data_idx += 1
				else:
					selfp.source.stb = 0
			else:
				self.source.stb = 0

	def rd_sim(self, selfp):
		if self.run:
			selfp.sink.ack = 1
		else:
			selfp.sink.ack = 0
		if selfp.sink.stb & selfp.sink.ack:
			self.rd_data.append(selfp.sink.d)

	def do_simulation(self, selfp):
		RandRun.do_simulation(self, selfp)
		self.wr_sim(selfp)
		self.rd_sim(selfp)


LENGTH = 512
model_rd_data = [i%256 for i in range(LENGTH)][::-1]
user_wr_data  = [i%256 for i in range(LENGTH)]

class TB(Module):
	def __init__(self):
		self.submodules.model = FtdiModel(model_rd_data)
		self.submodules.phy = FtdiPHY(self.model)

		self.submodules.user = UserModel(user_wr_data)

		self.comb += [
			self.user.source.connect(self.phy.sink),
			self.phy.source.connect(self.user.sink)
		]

		# Use sys_clk as ftdi_clk in simulation
		self.comb += [
			ClockSignal("ftdi").eq(ClockSignal()),
			ResetSignal("ftdi").eq(ResetSignal())
		]

def print_results(s, l1, l2):
	def comp(l1, l2):
		r = True
		try:
			for i, val in enumerate(l1):
				if val != l2[i]:
					print(s + " : val : %02X, exp : %02X" %(val, l2[i]))
					r = False
		except:
			return r
		return r

	c = comp(l1, l2)
	r = s + " "
	if c:
		r += "[OK]"
	else:
		r += "[KO]"
	print(r)

def main():
	from migen.sim.generic import run_simulation
	tb = TB()
	run_simulation(tb, ncycles=8000, vcd_name="tb_phy.vcd")

	###
	#print(tb.user.rd_data)
	#print(tb.model.wr_data)
	#print(len(tb.user.rd_data))
	#print(len(tb.model.wr_data))

	print_results("FtdiModel --> UserModel", model_rd_data, tb.user.rd_data)
	print_results("UserModel --> FtdiModel", user_wr_data,  tb.model.wr_data)

if __name__ == "__main__":
	main()
