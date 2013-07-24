from migen.fhdl.std import *

class ReorderSlot:
	def __init__(self, tag_width, data_width):
		self.wait_data = Signal()
		self.has_data = Signal()
		self.tag = Signal(tag_width)
		self.data = Signal(data_width)

class ReorderBuffer(Module):
	def __init__(self, tag_width, data_width, depth):
		# issue
		self.can_issue = Signal()
		self.issue = Signal()
		self.tag_issue = Signal(tag_width)
		
		# call
		self.call = Signal()
		self.tag_call = Signal(tag_width)
		self.data_call = Signal(data_width)
		
		# readback
		self.can_read = Signal()
		self.read = Signal()
		self.data_read = Signal(data_width)
	
		###

		empty_count = Signal(max=depth+1, reset=depth)
		produce = Signal(max=depth)
		consume = Signal(max=depth)
		slots = Array(ReorderSlot(tag_width, data_width)
			for n in range(depth))

		# issue
		self.comb += self.can_issue.eq(empty_count != 0)
		self.sync += If(self.issue & self.can_issue,
				empty_count.eq(empty_count - 1),
				If(produce == depth - 1,
					produce.eq(0)
				).Else(
					produce.eq(produce + 1)
				),
				slots[produce].wait_data.eq(1),
				slots[produce].tag.eq(self.tag_issue)
			)
		
		# call
		for n, slot in enumerate(slots):
			self.sync += If(self.call & slot.wait_data & (self.tag_call == slot.tag),
					slot.wait_data.eq(0),
					slot.has_data.eq(1),
					slot.data.eq(self.data_call)
				)
		
		# readback
		self.comb += [
			self.can_read.eq(slots[consume].has_data),
			self.data_read.eq(slots[consume].data)
		]
		self.sync += [
			If(self.read & self.can_read,
				empty_count.eq(empty_count + 1),
				If(consume == depth - 1,
					consume.eq(0)
				).Else(
					consume.eq(consume + 1)
				),
				slots[consume].has_data.eq(0)
			)
		]
		
		# do not touch empty count when issuing and reading at the same time
		self.sync += If(self.issue & self.can_issue & self.read & self.can_read,
				empty_count.eq(empty_count)
			)
