#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.fhdl.specials import Special, Tristate

# Helpers ------------------------------------------------------------------------------------------

def _check_widths(name, **signals):
    widths = {k: len(v) for k, v in signals.items() if v is not None}
    if len(set(widths.values())) != 1:
        widths = ", ".join(f"{k}={v}" for k, v in widths.items())
        raise ValueError(f"{name} signal widths must match ({widths})")

# Differential Input/Output ------------------------------------------------------------------------

class DifferentialInput(Special):
    def __init__(self, i_p, i_n, o):
        Special.__init__(self)
        self.i_p = wrap(i_p)
        self.i_n = wrap(i_n)
        self.o   = wrap(o)
        _check_widths(self.__class__.__name__, i_p=self.i_p, i_n=self.i_n, o=self.o)
        if len(self.o) != 1:
            raise ValueError(f"{self.__class__.__name__} only supports single-bit signals")

    def iter_expressions(self):
        yield self, "i_p", SPECIAL_INPUT
        yield self, "i_n", SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Differential Input, but platform does not support them")


class DifferentialOutput(Special):
    def __init__(self, i, o_p, o_n):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o_p = wrap(o_p)
        self.o_n = wrap(o_n)
        _check_widths(self.__class__.__name__, i=self.i, o_p=self.o_p, o_n=self.o_n)
        if len(self.i) != 1:
            raise ValueError(f"{self.__class__.__name__} only supports single-bit signals")

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o_p", SPECIAL_OUTPUT
        yield self, "o_n", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Differential Output, but platform does not support them")

# Clk Input/Output ---------------------------------------------------------------------------------

class ClkInput(Special):
    """Clock input primitive.

    This is currently lowered by the Efinix backend. Other platforms fail
    explicitly unless they provide an override.
    """

    def __init__(self, i, o):
        Special.__init__(self)
        self.i = wrap(i)
        self.o = o if isinstance(o, str) else wrap(o)

    def iter_expressions(self):
        yield self, "i", SPECIAL_INPUT
        yield self, "o", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Clk Input, but platform does not support them")


class ClkOutput(Special):
    """Clock output primitive.

    This is currently lowered by the Efinix backend. Other platforms fail
    explicitly unless they provide an override.
    """

    def __init__(self, i, o):
        Special.__init__(self)
        if isinstance(i, str):
            raise ValueError("ClkOutput input must be a Signal or ClockSignal")
        self.i = wrap(i)
        self.o = wrap(o)

    def iter_expressions(self):
        yield self, "i", SPECIAL_INPUT
        yield self, "o", SPECIAL_OUTPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a Clk Output, but platform does not support them")

# SDR Input/Output ---------------------------------------------------------------------------------

class InferredSDRIO(Module):
    """Generic SDR IO fallback.

    The generic fallback is a fabric register clocked by ``clk``. Vendor
    overrides should map SDRInput/SDROutput to IO register primitives when the
    toolchain exposes them; otherwise timing/placement are toolchain-dependent.
    """

    n = 0

    def __init__(self, i, o, clk, clock_domain=None):
        if clock_domain is None:
            clock_domain = f"sdrio{InferredSDRIO.n}"
            InferredSDRIO.n += 1
            cd = ClockDomain(clock_domain, reset_less=True)
            self.clock_domains += cd
            self.comb += cd.clk.eq(clk)
        cd_name = clock_domain
        sync = getattr(self.sync, cd_name)
        sync += o.eq(i)

class SDRIO(Special):
    def __init__(self, i, o, clk=None):
        Special.__init__(self)
        self.i            = wrap(i)
        self.o            = wrap(o)
        if clk is None:
            clk = ClockSignal()
        self.clk          = wrap(clk)
        self.clk_domain   = None if not hasattr(clk, "cd") else clk.cd
        _check_widths(self.__class__.__name__, i=self.i, o=self.o)

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferredSDRIO(dr.i, dr.o, dr.clk, dr.clk_domain)

class SDRInput(SDRIO):  pass
class SDROutput(SDRIO): pass

# SDR Tristate -------------------------------------------------------------------------------------

class InferredSDRTristate(Module):
    def __init__(self, io, o, oe, i, clk):
        _o  = Signal.like(o)
        _oe = Signal.like(oe)
        _i  = Signal.like(i) if i is not None else None
        self.specials   += SDROutput(o, _o, clk)
        if _i is not None:
            self.specials   += SDRInput(_i, i, clk)
        self.submodules += InferredSDRIO(oe, _oe, clk)
        self.specials   += Tristate(io, _o, _oe, _i)

class SDRTristate(Special):
    def __init__(self, io, o, oe, i=None, clk=None):
        Special.__init__(self)
        self.io  = wrap(io)
        self.o   = wrap(o)
        self.oe  = wrap(oe)
        self.i   = wrap(i) if i is not None else None
        self.clk = wrap(clk) if clk is not None else ClockSignal()
        _check_widths(self.__class__.__name__, io=self.io, o=self.o, oe=self.oe, i=self.i)

    def iter_expressions(self):
        yield self, "io" , SPECIAL_INOUT
        yield self, "o"  , SPECIAL_INPUT
        yield self, "oe" , SPECIAL_INPUT
        if self.i is not None:
            yield self, "i"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        return InferredSDRTristate(dr.io, dr.o, dr.oe, dr.i, dr.clk)

# DDR Input/Output ---------------------------------------------------------------------------------

class DDRInput(Special):
    def __init__(self, i, o1, o2, clk=None):
        Special.__init__(self)
        self.i   = wrap(i)
        self.o1  = wrap(o1)
        self.o2  = wrap(o2)
        if clk is None:
            clk = ClockSignal()
        self.clk = clk if isinstance(clk, str) else wrap(clk)
        _check_widths(self.__class__.__name__, i=self.i, o1=self.o1, o2=self.o2)

    def iter_expressions(self):
        yield self, "i"  , SPECIAL_INPUT
        yield self, "o1" , SPECIAL_OUTPUT
        yield self, "o2" , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a DDR input, but platform does not support them")


class DDROutput(Special):
    def __init__(self, i1, i2, o, clk=None):
        Special.__init__(self)
        self.i1  = wrap(i1)
        self.i2  = wrap(i2)
        self.o   = wrap(o)
        if clk is None:
            clk = ClockSignal()
        self.clk = clk if isinstance(clk, str) else wrap(clk)
        _check_widths(self.__class__.__name__, i1=self.i1, i2=self.i2, o=self.o)

    def iter_expressions(self):
        yield self, "i1" , SPECIAL_INPUT
        yield self, "i2" , SPECIAL_INPUT
        yield self, "o"  , SPECIAL_OUTPUT
        yield self, "clk", SPECIAL_INPUT

    @staticmethod
    def lower(dr):
        raise NotImplementedError("Attempted to use a DDR output, but platform does not support them")

# DDR Tristate -------------------------------------------------------------------------------------

class InferredDDRTristate(Module):
    def __init__(self, io, o1, o2, oe1, oe2, i1, i2, clk, i_async):
        _o  = Signal.like(o1)
        _oe = Signal.like(oe1)
        _i  = Signal.like(_o) if i1 is not None and i2 is not None else None
        self.specials += DDROutput(o1, o2, _o, clk)
        self.specials += DDROutput(oe1, oe2, _oe, clk) if oe2 is not None else SDROutput(oe1, _oe, clk)
        if _i is not None:
            self.specials += DDRInput(_i, i1, i2, clk)
            if i_async is not None:
                self.comb += i_async.eq(_i)
        elif i_async is not None:
            _i = i_async
        self.specials += Tristate(io, _o, _oe, _i)

class DDRTristate(Special):
    def __init__(self, io, o1, o2, oe1, oe2=None, i1=None, i2=None, clk=None, i_async=None):
        Special.__init__(self)
        self.io      = wrap(io)
        self.o1      = wrap(o1)
        self.o2      = wrap(o2)
        self.oe1     = wrap(oe1)
        self.oe2     = wrap(oe2) if oe2 is not None else None
        self.i1      = wrap(i1) if i1 is not None else None
        self.i2      = wrap(i2) if i2 is not None else None
        self.clk     = clk if isinstance(clk, str) else wrap(clk) if clk is not None else ClockSignal()
        self.i_async = wrap(i_async) if i_async is not None else None
        if (self.i1 is None) != (self.i2 is None):
            raise ValueError("DDRTristate i1 and i2 must both be provided or both be omitted")
        _check_widths(
            self.__class__.__name__,
            io      = self.io,
            o1      = self.o1,
            o2      = self.o2,
            oe1     = self.oe1,
            oe2     = self.oe2,
            i1      = self.i1,
            i2      = self.i2,
            i_async = self.i_async,
        )

    def iter_expressions(self):
        attr_context = [
            ("io" ,     SPECIAL_INOUT),
            ("o1" ,     SPECIAL_INPUT),
            ("o2" ,     SPECIAL_INPUT),
            ("oe1",     SPECIAL_INPUT),
            ("oe2",     SPECIAL_INPUT),
            ("i1" ,     SPECIAL_OUTPUT),
            ("i2" ,     SPECIAL_OUTPUT),
            ("clk",     SPECIAL_INPUT),
            ("i_async", SPECIAL_OUTPUT)
        ]
        for attr, target_context in attr_context:
            if getattr(self, attr) is not None:
                yield self, attr, target_context

    @staticmethod
    def lower(dr):
        return InferredDDRTristate(dr.io, dr.o1, dr.o2, dr.oe1, dr.oe2, dr.i1, dr.i2, dr.clk, dr.i_async)

# Clock Reset Generator ----------------------------------------------------------------------------

class CRG(Module):
    def __init__(self, clk, rst=0):
        self.clock_domains.cd_sys = ClockDomain("sys")
        self.clock_domains.cd_por = ClockDomain("por", reset_less=True)

        if hasattr(clk, "p"):
            clk_se = Signal()
            self.specials += DifferentialInput(clk.p, clk.n, clk_se)
            clk = clk_se

        # Power on Reset (vendor agnostic)
        int_rst = Signal(reset=1)
        self.sync.por += int_rst.eq(rst)
        self.comb += [
            self.cd_sys.clk.eq(clk),
            self.cd_por.clk.eq(clk),
            self.cd_sys.rst.eq(int_rst)
        ]
