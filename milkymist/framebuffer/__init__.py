from migen.fhdl.structure import *
from migen.flow.actor import *
from migen.flow.network import *
from migen.bank.description import *
from migen.bank import csrgen

_hbits = 11
_vbits = 11

class _FrameInitiator(Actor):
	def __init__(self, asmi_bits, alignment_bits):
		self._alignment_bits = alignment_bits
		length_bits = _hbits + _vbits + 2 - alignment_bits
		
		self._enable = RegisterField("enable")
		
		self._hres = RegisterField("hres", _hbits, reset=640)
		self._hsync_start = RegisterField("hsync_start", _hbits, reset=656)
		self._hsync_end = RegisterField("hsync_end", _hbits, reset=752)
		self._hscan = RegisterField("hscan", _hbits, reset=799)
		
		self._vres = RegisterField("vres", _vbits, reset=480)
		self._vsync_start = RegisterField("vsync_start", _vbits, reset=492)
		self._vsync_end = RegisterField("vsync_end", _vbits, reset=494)
		self._vscan = RegisterField("vscan", _vbits, reset=524)
		
		self._base = RegisterField("base", asmi_bits + self._alignment_bits)
		self._length = RegisterField("length", length_bits + self._alignment_bits)
		
		layout = [
			("hres", BV(_hbits)),
			("hsync_start", BV(_hbits)),
			("hsync_end", BV(_hbits)),
			("hscan", BV(_hbits)),
			("vres", BV(_vbits)),
			("vsync_start", BV(_vbits)),
			("vsync_end", BV(_vbits)),
			("vscan", BV(_vbits)),
			("base", BV(asmi_bits)),
			("length", BV(length_bits))
		]
		super().__init__(("frame", Source, layout))
		
	def get_registers(self):
		return [self._enable,
			self._hres, self._hsync_start, self._hsync_end, self._hscan,
			self._vres, self._vsync_start, self._vsync_end, self._vscan,
			self._base, self._length]
		
	def get_fragment(self):
		# TODO: make address updates atomic
		token = self.token("frame")
		comb = [
			self.endpoints["frame"].stb.eq(self._enable.field.r),
			token.hres.eq(self._hres.field.r),
			token.hsync_start.eq(self._hsync_start.field.r),
			token.hsync_end.eq(self._hsync_end.field.r),
			token.hscan.eq(self._hscan.field.r),
			token.vres.eq(self._vres.field.r),
			token.vsync_start.eq(self._vsync_start.field.r),
			token.vsync_end.eq(self._vsync_end.field.r),
			token.vscan.eq(self._vscan.field.r),
			token.base.eq(self._base.field.r[self._alignment_bits:]),
			token.length.eq(self._length.field.r[self._alignment_bits:])
		]
		return Fragment(comb)

class Framebuffer:
	def __init__(self, address, asmiport):
		asmi_bits = asmiport.hub.aw
		alignment_bits = asmiport.hub.dw//8
		
		fi = _FrameInitiator(asmi_bits, alignment_bits)
		
		self.bank = csrgen.Bank(fi.get_registers(), address=address)
		
		# VGA clock input
		self.vga_clk = Signal()
		
		# Pads
		self.vga_psave_n = Signal()
		self.vga_hsync_n = Signal()
		self.vga_vsync_n = Signal()
		self.vga_sync_n = Signal()
		self.vga_blank_n = Signal()
		self.vga_r = Signal(BV(8))
		self.vga_g = Signal(BV(8))
		self.vga_b = Signal(BV(8))

	def get_fragment(self):
		comb = [
			self.vga_sync_n.eq(0),
			self.vga_psave_n.eq(1),
			self.vga_blank_n.eq(1)
		]
		return Fragment()
