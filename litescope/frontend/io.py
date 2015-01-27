from litescope.common import *

class LiteScopeIO(Module, AutoCSR):
	def __init__(self, dw):
		self.dw = dw
		self._r_i = CSRStatus(dw)
		self._r_o = CSRStorage(dw)

		self.i = self._r_i.status
		self.o = self._r_o.storage
