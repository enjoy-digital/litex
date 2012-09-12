from math import ceil

Hz  = 1
KHz = 10**3
MHz = 10**6
GHz = 10**9

s   = 1
ms  = 1/KHz
us  = 1/MHz
ns  = 1/GHz

class t2n:
	def __init__(self, clk_period_ns):
		self.clk_period_ns = clk_period_ns
		self.clk_period_us = clk_period_ns*(GHz/MHz)
		self.clk_period_ms = clk_period_ns*(GHz/KHz)
	def ns(self,t,margin=True):
		if margin:
			t += self.clk_period_ns/2
		return ceil(t/self.clk_period_ns)
	def us(self,t,margin=True):
		if margin:
			t += self.clk_period_us/2
		return ceil(t/self.clk_period_us)
	def ms(self,t,margin=True):
		if margin:
			t += self.clk_period_ms/2
		return ceil(t/self.clk_period_ms)