# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.sim.ipc import *

class TopLevel:
	def __init__(self, vcd_name=None, vcd_level=1,
	  top_name="top", dut_type="dut", dut_name="dut",
	  clk_name="sys_clk", clk_period=10, rst_name="sys_rst"):
		self.vcd_name = vcd_name
		self.vcd_level = vcd_level
		self.top_name = top_name
		self.dut_type = dut_type
		self.dut_name = dut_name
		self.clk_name = clk_name
		self.clk_period = clk_period
		self.rst_name = rst_name
	
	def get(self, sockaddr):
		template1 = """`timescale 1ns / 1ps

module {top_name}();

reg {clk_name};
reg {rst_name};

initial begin
	{rst_name} <= 1'b1;
	@(posedge {clk_name});
	{rst_name} <= 1'b0;
end

always begin
	{clk_name} <= 1'b0;
	#{hclk_period};
	{clk_name} <= 1'b1;
	#{hclk_period};
end

{dut_type} {dut_name}(
	.{rst_name}({rst_name}),
	.{clk_name}({clk_name})
);

initial $migensim_connect("{sockaddr}");
always @(posedge {clk_name}) $migensim_tick;
"""
		template2 = """
initial begin
	$dumpfile("{vcd_name}");
	$dumpvars({vcd_level}, {dut_name});
end
"""
		r = template1.format(top_name=self.top_name,
			dut_type=self.dut_type,
			dut_name=self.dut_name,
			clk_name=self.clk_name,
			hclk_period=str(self.clk_period/2),
			rst_name=self.rst_name,
			sockaddr=sockaddr)
		if self.vcd_name is not None:
			r += template2.format(vcd_name=self.vcd_name,
				vcd_level=str(self.vcd_level),
				dut_name=self.dut_name)
		r += "\nendmodule"
		return r

class Simulator:
	def __init__(self, fragment, sim_runner, top_level=None, sockaddr="simsocket", **vopts):
		self.fragment = fragment
		if top_level is None:
			self.top_level = TopLevel()
		else:
			self.top_level = top_level
		self.ipc = Initiator(sockaddr)
		
		c_top = self.top_level.get(sockaddr)
		
		clk_signal = Signal(name_override=self.top_level.clk_name)
		rst_signal = Signal(name_override=self.top_level.rst_name)
		c_fragment, self.namespace = verilog.convert(fragment,
			{clk_signal, rst_signal},
			name=self.top_level.dut_type,
			clk_signal=clk_signal,
			rst_signal=rst_signal,
			return_ns=True,
			**vopts)
		
		self.cycle_counter = -1
		self.interrupt = False

		self.sim_runner = sim_runner
		self.sim_runner.start(c_top, c_fragment)
		self.ipc.accept()
		reply = self.ipc.recv()
		assert(isinstance(reply, MessageTick))
		self.fragment.call_sim(self)
	
	def run(self, ncycles=-1):
		self.interrupt = False
		counter = 0
		while not self.interrupt and (ncycles < 0 or counter < ncycles):
			self.cycle_counter += 1
			counter += 1
			self.ipc.send(MessageGo())
			reply = self.ipc.recv()
			assert(isinstance(reply, MessageTick))
			self.fragment.call_sim(self)

	def rd(self, item, index=0):
		name = self.top_level.top_name + "." \
		  + self.top_level.dut_name + "." \
		  + self.namespace.get_name(item)
		self.ipc.send(MessageRead(name, Int32(index)))
		reply = self.ipc.recv()
		assert(isinstance(reply, MessageReadReply))
		if isinstance(item, Memory):
			signed = False
			nbits = item.width
		else:
			signed = item.bv.signed
			nbits = item.bv.width
		value = reply.value & (2**nbits - 1)
		if signed and (value & 2**(nbits - 1)):
			value -= 2**nbits
		return value
	
	def wr(self, item, value, index=0):
		name = self.top_level.top_name + "." \
		  + self.top_level.dut_name + "." \
		  + self.namespace.get_name(item)
		if isinstance(item, Memory):
			nbits = item.width
		else:
			nbits = item.bv.width
		if value < 0:
			value += 2**nbits
		assert(value >= 0 and value < 2**nbits)
		self.ipc.send(MessageWrite(name, Int32(index), value))

class Proxy:
	def __init__(self, sim, obj):
		self.__dict__["_sim"] = sim
		self.__dict__["_obj"] = obj
	
	def __getattr__(self, name):
		item = getattr(self._obj, name)
		if isinstance(item, Signal):
			return self._sim.rd(item)
		elif isinstance(item, list):
			return [Proxy(self._sim, si) for si in item]
		else:
			return Proxy(self._sim, item)

	def __setattr__(self, name, value):
		item = getattr(self._obj, name)
		assert(isinstance(item, Signal))
		self._sim.wr(item, value)
