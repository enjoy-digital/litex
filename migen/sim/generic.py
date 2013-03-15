# Copyright (C) 2012 Vermeer Manufacturing Co.
# License: GPLv3 with additional permissions (see README).

from migen.fhdl.structure import *
from migen.fhdl.specials import Memory
from migen.fhdl import verilog
from migen.sim.ipc import *
from migen.sim import icarus

class TopLevel:
	def __init__(self, vcd_name=None, vcd_level=1,
	  top_name="top", dut_type="dut", dut_name="dut",
	  cd_name="sys", clk_period=10):
		self.vcd_name = vcd_name
		self.vcd_level = vcd_level
		self.top_name = top_name
		self.dut_type = dut_type
		self.dut_name = dut_name
		
		self._cd_name = cd_name
		self._clk_period = clk_period
		
		cd = ClockDomain(self._cd_name)
		self.clock_domains = [cd]
		self.ios = {cd.clk, cd.rst}
	
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
			clk_name=self._cd_name + "_clk",
			rst_name=self._cd_name + "_rst",
			hclk_period=str(self._clk_period/2),
			sockaddr=sockaddr)
		if self.vcd_name is not None:
			r += template2.format(vcd_name=self.vcd_name,
				vcd_level=str(self.vcd_level),
				dut_name=self.dut_name)
		r += "\nendmodule"
		return r

def _call_sim(fragment, simulator):
	for s in fragment.sim:
		if simulator.cycle_counter >= 0 or (hasattr(s, "initialize") and s.initialize):
			s(simulator)

class Simulator:
	def __init__(self, fragment, top_level=None, sim_runner=None, sockaddr="simsocket", **vopts):
		if not isinstance(fragment, Fragment):
			fragment = fragment.get_fragment()
		if top_level is None:
			top_level = TopLevel()
		if sim_runner is None:
			sim_runner = icarus.Runner()		
		self.fragment = fragment + Fragment(clock_domains=top_level.clock_domains)
		self.top_level = top_level
		self.ipc = Initiator(sockaddr)
		self.sim_runner = sim_runner
		
		c_top = self.top_level.get(sockaddr)
		
		c_fragment, self.namespace = verilog.convert(self.fragment,
			ios=self.top_level.ios,
			name=self.top_level.dut_type,
			return_ns=True,
			**vopts)
		
		self.cycle_counter = -1
		self.interrupt = False

		self.sim_runner = sim_runner
		self.sim_runner.start(c_top, c_fragment)
		self.ipc.accept()
		reply = self.ipc.recv()
		assert(isinstance(reply, MessageTick))
		_call_sim(self.fragment, self)
	
	def run(self, ncycles=-1):
		self.interrupt = False
		counter = 0
		while not self.interrupt and (ncycles < 0 or counter < ncycles):
			self.cycle_counter += 1
			counter += 1
			self.ipc.send(MessageGo())
			reply = self.ipc.recv()
			assert(isinstance(reply, MessageTick))
			_call_sim(self.fragment, self)

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
			signed = item.signed
			nbits = len(item)
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
			nbits = len(item)
		if value < 0:
			value += 2**nbits
		assert(value >= 0 and value < 2**nbits)
		self.ipc.send(MessageWrite(name, Int32(index), value))
	
	def multiread(self, obj):
		if isinstance(obj, Signal):
			return self.rd(obj)
		elif isinstance(obj, list):
			r = []
			for item in obj:
				rd = self.multiread(item)
				if isinstance(item, Signal) or rd:
					r.append(rd)
			return r
		elif hasattr(obj, "__dict__"):
			r = {}
			for k, v in obj.__dict__.items():
				rd = self.multiread(v)
				if isinstance(v, Signal) or rd:
					r[k] = rd
			return r
	
	def multiwrite(self, obj, value):
		if isinstance(obj, Signal):
			self.wr(obj, value)
		elif isinstance(obj, list):
			for target, source in zip(obj, value):
				self.multiwrite(target, source)
		else:
			for k, v in value.items():
				self.multiwrite(getattr(obj, k), v)

	def __del__(self):
		del self.ipc
		del self.sim_runner

# Contrary to multiread/multiwrite, Proxy fetches the necessary signals only and
# immediately forwards writes into the simulation.
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

class PureSimulable:
	def do_simulation(self, s):
		raise NotImplementedError("Need to overload do_simulation")
	
	def get_fragment(self):
		return Fragment(sim=[self.do_simulation])
