from migen.fhdl.structure import Signal, StopSimulation
from migen.fhdl.specials import Memory

class MemoryProxy:
	def __init__(self, simulator, obj):
		self.simulator = simulator
		self._simproxy_obj = obj

	def __getitem__(self, key):
		if isinstance(key, int):
			return self.simulator.rd(self._simproxy_obj, key)
		else:
			start, stop, step = key.indices(self._simproxy_obj.depth)
			return [self.simulator.rd(self._simproxy_obj, i) for i in range(start, stop, step)]

	def __setitem__(self, key, value):
		if isinstance(key, int):
			self.simulator.wr(self._simproxy_obj, key, value)
		else:
			start, stop, step = key.indices(self.__obj.depth)
			if len(value) != (stop - start)//step:
				raise ValueError
			for i, v in zip(range(start, stop, step), value):
				self.simulator.wr(self._simproxy_obj, i, v)

class Proxy:
	def __init__(self, simulator, obj):
		object.__setattr__(self, "simulator", simulator)
		object.__setattr__(self, "_simproxy_obj", obj)

	def __process_get(self, item):
		if isinstance(item, Signal):
			return self.simulator.rd(item)
		elif isinstance(item, Memory):
			return MemoryProxy(self.simulator, item)
		else:
			return Proxy(self.simulator, item)
	
	def __getattr__(self, name):
		return self.__process_get(getattr(self._simproxy_obj, name))
	
	def __setattr__(self, name, value):
		item = getattr(self._simproxy_obj, name)
		assert(isinstance(item, Signal))
		self.simulator.wr(item, value)

	def __getitem__(self, key):
		return self.__process_get(self._simproxy_obj[key])

	def __setitem__(self, key, value):
		item = self._simproxy_obj[key]
		assert(isinstance(item, Signal))
		self.simulator.wr(item, value)

class GenSim:
	def __init__(self, simg):
		self.simg = simg
		self.gens = dict()
		self.resume_cycle = 0

	def do_simulation(self, s):
		if isinstance(s, Proxy):
			simulator = s.simulator
		else:
			simulator = s

		if simulator.cycle_counter >= self.resume_cycle:
			try:
				gen = self.gens[simulator]
			except KeyError:
				gen = self.simg(s)
				self.gens[simulator] = gen
			try:
				n = next(gen)
			except StopIteration:
				del self.gens[simulator]
				raise StopSimulation
			else:
				if n is None:
					n = 1
				self.resume_cycle = simulator.cycle_counter + n

class ProxySim:
	def __init__(self, target, simf):
		self.target = target
		self.simf = simf
		self.proxies = dict()

	def do_simulation(self, simulator):
		try:
			proxy = self.proxies[simulator]
		except KeyError:
			proxy = Proxy(simulator, self.target)
			self.proxies[simulator] = proxy
		try:
			self.simf(proxy)
		except StopSimulation:
			del self.proxies[simulator]
			raise
