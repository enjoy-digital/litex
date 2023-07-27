#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

# Signals ------------------------------------------------------------------------------------------

class Open(Signal): pass

class Unsigned(Signal):
    def __init__(self, bits=1, *args, **kwargs):
        assert isinstance(bits, int)
        Signal.__init__(self, bits_sign=(bits, 0), *args, **kwargs)

class Signed(Signal):
    def __init__(self, bits=1, *args, **kwargs):
        assert isinstance(bits, int)
        Signal.__init__(self, bits_sign=(bits, 1), *args, **kwargs)
