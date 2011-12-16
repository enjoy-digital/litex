from migen.fhdl.structure import *

class Inst:
	def __init__(self, n):
		self.n = n
		self.bn = bits_for(self.n-1)
		declare_signal(self, "request", BV(self.n))
		declare_signal(self, "grant", BV(self.bn))
	
	def get_fragment(self):
		cases = []
		for i in range(self.n):
			switch = []
			for j in reversed(range(i+1,i+self.n)):
				t = j % self.n
				switch = [
					If(self.request[t],
						self.grant.eq(Constant(t, BV(self.bn)))
					).Else(
						*switch
					)
				]
			case = If(~self.request[i], *switch)
			cases.append([Constant(i, BV(self.bn)), case])
		statement = Case(self.grant, *cases)
		return Fragment(sync=[statement])
