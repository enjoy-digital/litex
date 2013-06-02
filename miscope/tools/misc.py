from migen.fhdl.structure import *
from migen.fhdl.module import Module

class RisingEdge(Module):
	def __init__(self, i=None, o=None, domain="sys"):
		self.i = ifthenelse(i, i, Signal())
		self.o = ifthenelse(o, o, Signal())
	####
		i_d = Signal()
		sync =[i_d.eq(self.i)]
		self.comb +=[self.o.eq(self.i & ~i_d)]
		self._fragment += Fragment(sync={domain : sync})

class FallingEdge(Module):
	def __init__(self, i=None, o=None, domain="sys"):
		self.i = ifthenelse(i, i, Signal())
		self.o = ifthenelse(o, o, Signal())
	####
		i_d = Signal()
		sync =[i_d.eq(self.i)]
		self.comb +=[self.o.eq(~self.i & i_d)]
		self._fragment += Fragment(sync={domain : sync})

class FreqGen(Module):
	def __init__(self, clk_freq, freq, o=None):
		cnt_max = int(clk_freq/freq/2)
		width = bits_for(cnt_max)
		
		self.o = ifthenelse(o, o, Signal())
	####
		cnt = Signal(width)
		self.sync += [
			If(cnt >= cnt_max,
				cnt.eq(0),
				self.o.eq(~self.o)
			).Else(
				cnt.eq(cnt+1)
				)
			]

RISING_EDGE  = 1
FALLING_EDGE = 0

class EventGen(Module):
	def __init__(self, i=None, level=1, clk_freq=0, length=1, o=None):
		
		cnt_max = int(length*clk_freq)
		width = bits_for(cnt_max)
		
		self.i = ifthenelse(i, i, Signal())
		self.o = ifthenelse(o, o, Signal())
	###
		cnt = Signal(width)
		i_edge = Signal()
		
		if level == RISING_EDGE:
			self.submodules += RisingEdge(self.i, i_edge)
		elif level == FALLING_EDGE:
			self.submodules += FallingEdge(self.i, i_edge)
		
		self.sync += [
			If(i_edge == 1,
				cnt.eq(0),
				self.o.eq(1)
			).Elif(cnt >= cnt_max,
				self.o.eq(0)
			).Else(
				cnt.eq(cnt+1)
			),
			]
		
class PwmGen(Module):
	def __init__(self, width, o=None):
		self.ratio = Signal(width)
		self.o     = ifthenelse(o, o, Signal())
	###
		cnt = Signal(width)
		self.sync += [
			If(cnt == 0,
				self.o.eq(1)
			).Elif(cnt >= self.ratio,
				self.o.eq(0)
			),
			cnt.eq(cnt+1)
			]
		
class Cascade(Module):
	def __init__(self, i=None, elements=None, o=None):
		self.i = ifthenelse(i, i, Signal())
		self.o = ifthenelse(o, o, Signal())
		self.comb +=[elements[0].i.eq(self.i)]
		self.comb +=[elements[i+1].i.eq(elements[i].o) for i in range(len(elements)-1)]
		self.comb +=[self.o.eq(elements[len(elements)-1].o)]

class PwrOnRst(Module):
	def __init__(self, width, rst=None, simulation=False):
		self.rst = ifthenelse(rst, rst, Signal())
	###
		cnt = Signal(width)
		sync_no_reset = [If(self.rst, cnt.eq(cnt+1))]
		if not simulation:
			self.comb +=[
				If(cnt >= (2**width-1),
					self.rst.eq(0)
				).Else(
					self.rst.eq(1)
				)
			]
		else:
			self.comb += self.rst.eq(0)
		self._fragment += Fragment(sync={"sys_no_reset" : sync_no_reset})
		
def get_csr_base(bank, name=None):
	base = 0
	if name != None:
		base = None
		for i, c in enumerate(bank.simple_csrs):
			if name in c.name:
				if base == None:
					base = i
				elif base >= i:
					base = i
	return (bank.address<<9) + base