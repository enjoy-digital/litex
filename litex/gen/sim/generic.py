import warnings
import sys

from litex.gen import *
from litex.gen.fhdl.structure import _Fragment

from litex.gen.fhdl import verilog
from litex.gen.sim.ipc import *
from litex.gen.sim import icarus


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
        if sys.platform == "win32":
            sockaddr = sockaddr[0]  # Get the IP address only

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


class Simulator:
    def __init__(self, fragment, top_level=None, sim_runner=None, sockaddr="simsocket", **vopts):
        if not isinstance(fragment, _Fragment):
            fragment = fragment.get_fragment()
        if top_level is None:
            top_level = TopLevel()
        if sim_runner is None:
            sim_runner = icarus.Runner()
        self.top_level = top_level
        if sys.platform == "win32":
            sockaddr = ("127.0.0.1", 50007)
            self.ipc = Initiator(sockaddr)
        else:
            self.ipc = Initiator(sockaddr)

        self.sim_runner = sim_runner

        c_top = self.top_level.get(sockaddr)

        fragment = fragment + _Fragment(clock_domains=top_level.clock_domains)
        c_fragment = verilog.convert(fragment,
            ios=self.top_level.ios,
            name=self.top_level.dut_type,
            regular_comb=False,
            **vopts)
        self.namespace = c_fragment.ns

        self.cycle_counter = -1

        self.sim_runner = sim_runner
        self.sim_runner.start(c_top, c_fragment)
        self.ipc.accept()
        reply = self.ipc.recv()
        assert(isinstance(reply, MessageTick))

        self.sim_functions = fragment.sim
        self.active_sim_functions = set(f for f in fragment.sim if not hasattr(f, "passive") or not f.passive)
        self.unreferenced = {}

    def run(self, ncycles=None):
        counter = 0

        if self.active_sim_functions:
            if ncycles is None:
                def continue_simulation():
                    return bool(self.active_sim_functions)
            else:
                def continue_simulation():
                    return self.active_sim_functions and counter < ncycles
        else:
            if ncycles is None:
                raise ValueError("No active simulation function present - must specify ncycles to end simulation")
            def continue_simulation():
                return counter < ncycles

        while continue_simulation():
            self.cycle_counter += 1
            counter += 1
            self.ipc.send(MessageGo())
            reply = self.ipc.recv()
            assert(isinstance(reply, MessageTick))

            del_list = []
            for s in self.sim_functions:
                try:
                    s(self)
                except StopSimulation:
                    del_list.append(s)
            for s in del_list:
                self.sim_functions.remove(s)
                try:
                    self.active_sim_functions.remove(s)
                except KeyError:
                    pass

    def get_unreferenced(self, item, index):
        try:
            return self.unreferenced[(item, index)]
        except KeyError:
            if isinstance(item, Memory):
                try:
                    init = item.init[index]
                except (TypeError, IndexError):
                    init = 0
            else:
                init = item.reset
            self.unreferenced[(item, index)] = init
            return init

    def rd(self, item, index=0):
        try:
            name = self.top_level.top_name + "." \
              + self.top_level.dut_name + "." \
              + self.namespace.get_name(item)
            self.ipc.send(MessageRead(name, Int32(index)))
            reply = self.ipc.recv()
            assert(isinstance(reply, MessageReadReply))
            value = reply.value
        except KeyError:
            value = self.get_unreferenced(item, index)
        if isinstance(item, Memory):
            signed = False
            nbits = item.width
        else:
            signed = item.signed
            nbits = len(item)
        value = value & (2**nbits - 1)
        if signed and (value & 2**(nbits - 1)):
            value -= 2**nbits
        return value

    def wr(self, item, value, index=0):
        if isinstance(item, Memory):
            nbits = item.width
        else:
            nbits = len(item)
        if value < 0:
            value += 2**nbits
        assert(value >= 0 and value < 2**nbits)
        try:
            name = self.top_level.top_name + "." \
              + self.top_level.dut_name + "." \
              + self.namespace.get_name(item)
            self.ipc.send(MessageWrite(name, Int32(index), value))
        except KeyError:
            self.unreferenced[(item, index)] = value

    def __del__(self):
        if hasattr(self, "ipc"):
            warnings.warn("call Simulator.close() to clean up "
                    "or use it as a contextmanager", DeprecationWarning)
            self.close()

    def close(self):
        self.ipc.close()
        self.sim_runner.close()
        del self.ipc
        del self.sim_runner

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.close()


def run_simulation(fragment, ncycles=None, vcd_name=None, **kwargs):
    with Simulator(fragment, TopLevel(vcd_name), icarus.Runner(**kwargs)) as s:
        s.run(ncycles)

