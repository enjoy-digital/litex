from migen.fhdl.structure import *
from migen.fhdl import verilog
from migen.sim.ipc import *

class TopLevel:
	def __init__(self, top_name="top", dut_type="dut", dut_name="dut", clk_name="sys_clk", 
	  clk_period=10, rst_name="sys_rst"):
		self.top_name = top_name
		self.dut_type = dut_type
		self.dut_name = dut_name
		self.clk_name = clk_name
		self.clk_period = clk_period
		self.rst_name = rst_name
	
	def get(self, sockaddr):
		template = """module {top_name}();

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

endmodule
"""
		return template.format(top_name=self.top_name,
			dut_type=self.dut_type,
			dut_name=self.dut_name,
			clk_name=self.clk_name,
			hclk_period=str(self.clk_period/2),
			rst_name=self.rst_name,
			sockaddr=sockaddr)

class Simulator:
	def __init__(self, fragment, sim_runner, top_level=None, sockaddr="simsocket"):
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
			return_ns=True)
		
		sim_runner.start(c_top, c_fragment)
		self.ipc.accept()
		self.cycle_counter = 0
		self.interrupt = False
		self.fragment.call_sim(self, 0)
		self.ipc.send(MessageGo())
	
	def run(self, ncycles=-1):
		counter = 0
		while not self.interrupt and (ncycles < 0 or counter < ncycles):
			reply = self.ipc.recv()
			assert(isinstance(reply, MessageTick))
			self.cycle_counter += 1
			counter += 1
			self.fragment.call_sim(self, self.cycle_counter)
			self.ipc.send(MessageGo())

	def rd(self, signal):
		name = self.top_level.top_name + "." \
		  + self.top_level.dut_name + "." \
		  + self.namespace.get_name(signal)
		self.ipc.send(MessageRead(name))
		reply = self.ipc.recv()
		assert(isinstance(reply, MessageReadReply))
		# TODO: negative numbers + cleanup LSBs
		return reply.value
	
	def wr(self, signal, value):
		name = self.top_level.top_name + "." \
		  + self.top_level.dut_name + "." \
		  + self.namespace.get_name(signal)
		# TODO: negative numbers
		self.ipc.send(MessageWrite(name, value))
