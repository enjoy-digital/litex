from misoclib.tools.litescope.common import *

class LiteScopeIO(Module, AutoCSR):
    def __init__(self, dw):
        self.dw = dw
        self._i = CSRStatus(dw)
        self._o = CSRStorage(dw)

        self.i = self._i.status
        self.o = self._o.storage
