#
# This file is part of LiteX.
#
# This file is Copyright (c) 2022 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

# Signals ------------------------------------------------------------------------------------------

class Open(Signal):
    """A base Signal class, representing an open signal."""
    pass

class Unsigned(Signal):
    """
    A Signal subclass for unsigned signals.

    Args:
        bits (int): Number of bits of the signal. Defaults to 1.
    """
    def __init__(self, bits=1, *args, **kwargs):
        assert isinstance(bits, int)
        Signal.__init__(self, bits_sign=(bits, 0), *args, **kwargs)

class Signed(Signal):
    """
    A Signal subclass for signed signals.

    Args:
        bits (int): Number of bits of the signal. Defaults to 1.
    """
    def __init__(self, bits=1, *args, **kwargs):
        assert isinstance(bits, int)
        Signal.__init__(self, bits_sign=(bits, 1), *args, **kwargs)
