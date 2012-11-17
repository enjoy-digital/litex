import types

class Trampoline:
	def __init__(self, g):
		self.stack = [g]
	
	def __iter__(self):
		return self
	
	def __next__(self):
		while True:
			while True:
				try:
					r = next(self.stack[-1])
					break
				except StopIteration:
					self.stack.pop()
					if not self.stack:
						raise
			if isinstance(r, types.GeneratorType):
				self.stack.append(r)
			else:
				return r
