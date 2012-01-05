from migen.fhdl import verilog 
from migen.flow.ala import *

act = Divider(32)
frag = act.get_control_fragment() + act.get_process_fragment()
print(verilog.convert(frag))
