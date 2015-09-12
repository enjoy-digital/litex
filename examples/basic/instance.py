import subprocess

from migen import *
from migen.fhdl.verilog import convert


# Create a parent module with two instances of a child module.
# Bind input ports to first module and output ports to second,
# and create internal signals to connect the first module to the
# second.
class ParentModule(Module):
    def __init__(self):
        self.inputs = [Signal(x+1, name="input{}".format(x)) for x in range(4)]
        self.trans = [Signal(x+1) for x in range(4)]
        self.outputs = [Signal(x+1, name="output{}".format(x)) for x in range(4)]
        self.io = set(self.inputs) | set(self.outputs)
        i = Instance("ChildModule",
                     i_master_clk=ClockSignal(),
                     i_master_rst=ResetSignal(),
                     i_input0=self.inputs[0],
                     i_input1=self.inputs[1],
                     i_input2=self.inputs[2],
                     i_input3=self.inputs[3],
                     o_output0=self.trans[0],
                     o_output1=self.trans[1],
                     o_output2=self.trans[2],
                     o_output3=self.trans[3]
        )
        j = Instance("ChildModule",
                     i_master_clk=ClockSignal(),
                     i_master_rst=ResetSignal(),
                     i_input0=self.trans[0],
                     i_input1=self.trans[1],
                     i_input2=self.trans[2],
                     i_input3=self.trans[3],
                     o_output0=self.outputs[0],
                     o_output1=self.outputs[1],
                     o_output2=self.outputs[2],
                     o_output3=self.outputs[3]
        )
        self.specials += i, j


class ChildModule(Module):
    def __init__(self):
        self.inputs = [Signal(x+1, name_override="input{}".format(x)) for x in range(4)]
        self.outputs = [Signal(x+1, name_override="output{}".format(x)) for x in range(4)]
        self.io = set()
        for x in range(4):
            self.sync.master += self.outputs[x].eq(self.inputs[x])
        self.io = self.io.union(self.inputs)
        self.io = self.io.union(self.outputs)


# Generate RTL for the parent module and the submodule, run through
# icarus for a syntax check
def test_instance_module():
    sub = ChildModule()
    convert(sub, sub.io, name="ChildModule").write("ChildModule.v")

    im = ParentModule()
    convert(im, im.io, name="ParentModule").write("ParentModule.v")

    subprocess.check_call(["iverilog", "-W", "all",
                           "ParentModule.v", "ChildModule.v"])

if __name__ == "__main__":
    test_instance_module()
