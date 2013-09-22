from migen.fhdl.std import *

def dec2bin(d, nb=0):
	if d=="x":
		return "x"*nb
	elif d==0:
		b="0"
	else:
		b=""
		while d!=0:
			b="01"[d&1]+b
			d=d>>1
	return b.zfill(nb)

class RisingEdge(Module):
	def __init__(self):
		self.i = Signal()
		self.o = Signal()
	####
		i_d = Signal()
		self.sync += i_d.eq(self.i)
		self.comb += self.o.eq(self.i & ~i_d)

class FallingEdge(Module):
	def __init__(self):
		self.i = Signal()
		self.o = Signal()
	####
		i_d = Signal()
		self.sync += i_d.eq(self.i)
		self.comb += self.o.eq(~self.i & i_d)

class FreqGen(Module):
	def __init__(self, clk_freq, freq):
		cnt_max = int(clk_freq/freq/2)
		self.o = Signal()
	####
		cnt = Signal(max=cnt_max)
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
	def __init__(self, level=RISING_EDGE, clk_freq=0, length=1):
		cnt_max = int(length*clk_freq)
		self.o = Signal()
	###
		cnt = Signal(max=cnt_max)
		
		if level == RISING_EDGE:
			self.submodules.edge_detect = RisingEdge()
		elif level == FALLING_EDGE:
			self.submodules.edge_detect = FallingEdge()
		
		self.i = self.edge_detect.i
		
		self.sync += [
			If(self.edge_detect.o == 1,
				cnt.eq(0),
				self.o.eq(1)
			).Elif(cnt >= cnt_max,
				self.o.eq(0)
			).Else(
				cnt.eq(cnt+1)
			),
			]
		
class PwmGen(Module):
	def __init__(self, width):
		self.ratio = Signal(width)
		self.o     = Signal()
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