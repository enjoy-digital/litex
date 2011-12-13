from migen.fhdl import verilog
from migen.fhdl import structure as f
from migen.bus import wishbone
from milkymist import norflash

norflash0 = norflash.Inst(25, 12)
frag = norflash0.GetFragment()
v = verilog.Convert(frag, name="norflash",
	ios={norflash0.bus.cyc_i, norflash0.bus.stb_i, norflash0.bus.we_i, norflash0.bus.adr_i, norflash0.bus.sel_i, norflash0.bus.dat_i, norflash0.bus.dat_o, norflash0.bus.ack_o})
print(v)
