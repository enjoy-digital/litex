from migen.fhdl.structure import *

class Framebuffer:
	def __init__(self, csr_address, asmiport):
		# VGA clock input
		self.vga_clk = Signal()
		
		# pads
		self.vga_psave_n = Signal()
		self.vga_hsync_n = Signal()
		self.vga_vsync_n = Signal()
		self.vga_sync_n = Signal()
		self.vga_blank_n = Signal()
		self.vga_r = Signal(BV(8))
		self.vga_g = Signal(BV(8))
		self.vga_b = Signal(BV(8))

	def get_fragment(self):
		return Fragment()
