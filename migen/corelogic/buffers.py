from migen.fhdl.structure import *

class ReorderSlot:
	def __init__(self, tag_width, data_width):
		self.wait_data = Signal()
		self.has_data = Signal()
		self.tag = Signal(BV(tag_width))
		self.data = Signal(BV(data_width))

class ReorderBuffer:
	def __init__(self, tag_width, data_width, depth):
		self.depth = depth
		
		# issue
		self.can_issue = Signal()
		self.issue = Signal()
		self.tag_issue = Signal(BV(tag_width))
		
		# call
		self.call = Signal()
		self.tag_call = Signal(BV(tag_width))
		self.data_call = Signal(BV(data_width))
		
		# readback
		self.can_read = Signal()
		self.read = Signal()
		self.data_read = Signal(BV(data_width))
		
		self._empty_count = Signal(BV(bits_for(self.depth)), reset=self.depth)
		self._produce = Signal(BV(bits_for(self.depth-1)))
		self._consume = Signal(BV(bits_for(self.depth-1)))
		self._slots = Array(ReorderSlot(tag_width, data_width)
			for n in range(self.depth))
	
	def get_fragment(self):
		# issue
		comb = [
			self.can_issue.eq(self._empty_count != 0)
		]
		sync = [
			If(self.issue & self.can_issue,
				self._empty_count.eq(self._empty_count - 1),
				If(self._produce == self.depth - 1,
					self._produce.eq(0)
				).Else(
					self._produce.eq(self._produce + 1)
				),
				self._slots[self._produce].wait_data.eq(1),
				self._slots[self._produce].tag.eq(self.tag_issue)
			)
		]
		
		# call
		for n, slot in enumerate(self._slots):
			sync.append(
				If(self.call & slot.wait_data & (self.tag_call == slot.tag),
					slot.wait_data.eq(0),
					slot.has_data.eq(1),
					slot.data.eq(self.data_call)
				)
			)
		
		# readback
		comb += [
			self.can_read.eq(self._slots[self._consume].has_data),
			self.data_read.eq(self._slots[self._consume].data)
		]
		sync += [
			If(self.read & self.can_read,
				self._empty_count.eq(self._empty_count + 1),
				If(self._consume == self.depth - 1,
					self._consume.eq(0)
				).Else(
					self._consume.eq(self._consume + 1)
				),
				self._slots[self._consume].has_data.eq(0)
			)
		]
		
		# do not touch empty count when issuing and reading at the same time
		sync += [
			If(self.issue & self.can_issue & self.read & self.can_read,
				self._empty_count.eq(self._empty_count)
			)
		]
		
		return Fragment(comb, sync)
