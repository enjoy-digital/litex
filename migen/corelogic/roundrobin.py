from migen.fhdl import structure as f

class Inst:
	def __init__(self, n):
		self.n = n
		self.bn = f.bits_for(self.n-1)
		f.declare_signal(self, "request", f.BV(self.n))
		f.declare_signal(self, "grant", f.BV(self.bn))
	
	def get_fragment(self):
		cases = []
		for i in range(self.n):
			switch = []
			for j in reversed(range(i+1,i+self.n)):
				t = j % self.n
				switch = [f.If(self.request[t],
					[f.Assign(self.grant, f.Constant(t, f.BV(self.bn)))],
					switch)]
			case = f.If(~self.request[i], switch)
			cases.append((f.Constant(i, f.BV(self.bn)), case))
		statement = f.Case(self.grant, cases)
		return f.Fragment(sync=[statement])
