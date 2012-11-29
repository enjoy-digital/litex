from migen.fhdl.structure import *

(SP_WITHDRAW, SP_CE) = range(2)

class RoundRobin:
	def __init__(self, n, switch_policy=SP_WITHDRAW):
		self.n = n
		self.request = Signal(max=self.n)
		self.grant = Signal(max=self.n)
		self.switch_policy = switch_policy
		if self.switch_policy == SP_CE:
			self.ce = Signal()
	
	def get_fragment(self):
		if self.n > 1:
			cases = {}
			for i in range(self.n):
				switch = []
				for j in reversed(range(i+1,i+self.n)):
					t = j % self.n
					switch = [
						If(self.request[t],
							self.grant.eq(t)
						).Else(
							*switch
						)
					]
				if self.switch_policy == SP_WITHDRAW:
					case = [If(~self.request[i], *switch)]
				else:
					case = switch
				cases[i] = case
			statement = Case(self.grant, cases)
			if self.switch_policy == SP_CE:
				statement = If(self.ce, statement)
			return Fragment(sync=[statement])
		else:
			return Fragment([self.grant.eq(0)])
