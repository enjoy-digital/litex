from migen.fhdl.structure import *

class ReorderSlot:
	def __init__(self, tag_width, data_width):
		self.wait_data = Signal()
		self.has_data = Signal()
		self.tag = Signal(tag_width)
		self.data = Signal(data_width)

class ReorderBuffer:
	def __init__(self, tag_width, data_width, depth):
		self.depth = depth
		
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
		
		self._empty_count = Signal(max=self.depth+1, reset=self.depth)
		self._produce = Signal(max=self.depth)
		self._consume = Signal(max=self.depth)
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
