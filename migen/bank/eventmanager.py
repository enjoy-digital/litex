from migen.fhdl.structure import *
from migen.bank.description import *
from migen.corelogic.misc import optree

class EventSource:
	def __init__(self):
		self.trigger = Signal()
		self.pending = Signal()

class EventSourcePulse(EventSource):
	pass

class EventSourceLevel(EventSource):
	pass

class EventManager:
	def __init__(self, *sources):
		self.sources = sources
		self.irq = Signal()
		n = len(self.sources)
		self.status = RegisterRaw("status", n)
		self.pending = RegisterRaw("pending", n)
		self.enable = RegisterFields("enable",
		  [Field("s" + str(i), access_bus=READ_WRITE, access_dev=READ_ONLY) for i in range(n)])
	
	def get_registers(self):
		return [self.status, self.pending, self.enable]
	
	def get_fragment(self):
		comb = []
		sync = []
		
		# status
		for i, source in enumerate(self.sources):
			if isinstance(source, EventSourcePulse):
				comb.append(self.status.w[i].eq(0))
			elif isinstance(source, EventSourceLevel):
				comb.append(self.status.w[i].eq(source.trigger))
			else:
				raise TypeError
		
		# pending
		for i, source in enumerate(self.sources):
			# W1C
			sync.append(If(self.pending.re & self.pending.r[i], source.pending.eq(0)))
			if isinstance(source, EventSourcePulse):
				# set on a positive trigger pulse
				sync.append(If(source.trigger, source.pending.eq(1)))
			elif isinstance(source, EventSourceLevel):
				# set on the falling edge of the trigger
				old_trigger = Signal()
				sync += [
					old_trigger.eq(source.trigger),
					If(~source.trigger & old_trigger, source.pending.eq(1))
				]
			else:
				raise TypeError
			comb.append(self.pending.w[i].eq(source.pending))
		
		# IRQ
		irqs = [self.pending.w[i] & field.r for i, field in enumerate(self.enable.fields)]
		comb.append(self.irq.eq(optree("|", irqs)))
		
		return Fragment(comb, sync)
