from migen.fhdl.module import Module
from migen.fhdl.specials import Instance, Tristate
from migen.fhdl.bitcontainer import value_bits_sign
from migen.genlib.io import *
from migen.genlib.resetsync import AsyncResetSynchronizer


class LatticeECPXAsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("FD1S3BX", i_D=0, i_PD=async_reset,
                     i_CK=cd.clk, o_Q=rst1),
            Instance("FD1S3BX", i_D=rst1, i_PD=async_reset,
                     i_CK=cd.clk, o_Q=cd.rst)
        ]


class LatticeECPXAsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeECPXAsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


class LatticeECPXDDROutputImpl(Module):
    def __init__(self, i1, i2, o, clk):
        self.specials += Instance("ODDRXD1",
                                  synthesis_directive="ODDRAPPS=\"SCLK_ALIGNED\"",
                                  i_SCLK=clk,
                                  i_DA=i1, i_DB=i2, o_Q=o)


class LatticeECPXDDROutput:
    @staticmethod
    def lower(dr):
        return LatticeECPXDDROutputImpl(dr.i1, dr.i2, dr.o, dr.clk)


lattice_ecpx_special_overrides = {
    AsyncResetSynchronizer: LatticeECPXAsyncResetSynchronizer,
    DDROutput:              LatticeECPXDDROutput
}


class LatticeECPXPrjTrellisTristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        for bit in range(nbits):
            self.specials += \
                Instance("TRELLIS_IO",
                    p_DIR="BIDIR",
                    i_B=~io[bit],
                    i_I=o[bit],
                    o_O=i[bit]
                )

class LatticeECPXPrjTrellisTristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeECPXPrjTrellisTristateImpl(dr.target, dr.o, dr.oe, dr.i)


lattice_ecpx_prjtrellis_special_overrides = {
    AsyncResetSynchronizer: LatticeECPXAsyncResetSynchronizer,
    Tristate:               LatticeECPXPrjTrellisTristate,
    DDROutput:              LatticeECPXDDROutput
}


class LatticeiCE40AsyncResetSynchronizerImpl(Module):
    def __init__(self, cd, async_reset):
        rst1 = Signal()
        self.specials += [
            Instance("SB_DFFS", i_D=0, i_S=async_reset,
                     i_C=cd.clk, o_Q=rst1),
            Instance("SB_DFFS", i_D=rst1, i_S=async_reset,
                     i_C=cd.clk, o_Q=cd.rst)
        ]


class LatticeiCE40AsyncResetSynchronizer:
    @staticmethod
    def lower(dr):
        return LatticeiCE40AsyncResetSynchronizerImpl(dr.cd, dr.async_reset)


class LatticeiCE40TristateImpl(Module):
    def __init__(self, io, o, oe, i):
        nbits, sign = value_bits_sign(io)
        for bit in range(nbits):
            self.specials += \
                Instance("SB_IO",
                    p_PIN_TYPE=C(0b101001, 6),
                    io_PACKAGE_PIN=io[bit],
                    i_OUTPUT_ENABLE=oe,
                    i_D_OUT_0=o[bit],
                    o_D_IN_0=i[bit],
                )


class LatticeiCE40Tristate(Module):
    @staticmethod
    def lower(dr):
        return LatticeiCE40TristateImpl(dr.target, dr.o, dr.oe, dr.i)


class LatticeiCE40DifferentialOutputImpl(Module):
    def __init__(self, i, o_p, o_n):
        self.specials += Instance("SB_IO",
                                  p_PIN_TYPE=C(0b011000, 6),
                                  p_IO_STANDARD="SB_LVCMOS",
                                  io_PACKAGE_PIN=o_p,
                                  i_D_OUT_0=i)

        self.specials += Instance("SB_IO",
                                  p_PIN_TYPE=C(0b011000, 6),
                                  p_IO_STANDARD="SB_LVCMOS",
                                  io_PACKAGE_PIN=o_n,
                                  i_D_OUT_0=~i)


class LatticeiCE40DifferentialOutput:
    @staticmethod
    def lower(dr):
        return LatticeiCE40DifferentialOutputImpl(dr.i, dr.o_p, dr.o_n)


lattice_ice40_special_overrides = {
    AsyncResetSynchronizer: LatticeiCE40AsyncResetSynchronizer,
    Tristate:               LatticeiCE40Tristate,
    DifferentialOutput:     LatticeiCE40DifferentialOutput
}
