from migen.fhdl.structure import *

def handler(memory, ns, clk):
	r = ""
	gn = ns.get_name
	adrbits = bits_for(memory.depth-1)
	
	storage = Signal(name_override="mem")
	r += "reg [" + str(memory.width-1) + ":0] " \
		+ gn(storage) \
		+ "[0:" + str(memory.depth-1) + "];\n"

	adr_regs = {}
	data_regs = {}
	for port in memory.ports:
		if not port.async_read:
			if port.mode == WRITE_FIRST and port.we is not None:
				adr_reg = Signal(name_override="memadr")
				r += "reg [" + str(adrbits-1) + ":0] " \
					+ gn(adr_reg) + ";\n"
				adr_regs[id(port)] = adr_reg
			else:
				data_reg = Signal(name_override="memdat")
				r += "reg [" + str(memory.width-1) + ":0] " \
					+ gn(data_reg) + ";\n"
				data_regs[id(port)] = data_reg

	r += "always @(posedge " + gn(clk) + ") begin\n"
	for port in memory.ports:
		if port.we is not None:
			if port.we_granularity:
				n = memory.width//port.we_granularity
				for i in range(n):
					m = i*port.we_granularity
					M = (i+1)*port.we_granularity-1
					sl = "[" + str(M) + ":" + str(m) + "]"
					r += "\tif (" + gn(port.we) + "[" + str(i) + "])\n"
					r += "\t\t" + gn(storage) + "[" + gn(port.adr) + "]" + sl + " <= " + gn(port.dat_w) + sl + ";\n"
			else:
				r += "\tif (" + gn(port.we) + ")\n"
				r += "\t\t" + gn(storage) + "[" + gn(port.adr) + "] <= " + gn(port.dat_w) + ";\n"
		if not port.async_read:
			if port.mode == WRITE_FIRST and port.we is not None:
				r += "\t" + gn(adr_regs[id(port)]) + " <= " + gn(port.adr) + ";\n"
			else:
				bassign = gn(data_regs[id(port)]) + " <= " + gn(storage) + "[" + gn(port.adr) + "];\n"
				if port.mode == READ_FIRST or port.we is None:
					r += "\t" + bassign
				elif port.mode == NO_CHANGE:
					r += "\tif (!" + gn(port.we) + ")\n"
					r += "\t\t" + bassign
	r += "end\n\n"
	
	for port in memory.ports:
		if port.async_read:
			r += "assign " + gn(port.dat_r) + " = " + gn(storage) + "[" + gn(port.adr) + "];\n"
		else:
			if port.mode == WRITE_FIRST and port.we is not None:
				r += "assign " + gn(port.dat_r) + " = " + gn(storage) + "[" + gn(adr_regs[id(port)]) + "];\n"
			else:
				r += "assign " + gn(port.dat_r) + " = " + gn(data_regs[id(port)]) + ";\n"
	r += "\n"
	
	if memory.init is not None:
		r += "initial begin\n"
		for i, c in enumerate(memory.init):
			r += "\t" + gn(storage) + "[" + str(i) + "] <= " + str(memory.width) + "'d" + str(c) + ";\n"
		r += "end\n\n"
	
	return r
