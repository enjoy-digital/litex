#
# This file is part of LiteX.
#
# Copyright (c) 2014-2015 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2019-2023 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 bunnie <bunnie@kosagi.com>
# Copyright (c) 2021 Vamsi K Vytla <vamsi.vytla@gmail.com>
# Copyright (c) 2022 Sylvain Munaut <tnt@246tNt.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import LiteXModule

from litex.soc.interconnect.csr import *

# Layouts  -----------------------------------------------------------------------------------------

analog_layout = [("vauxp", 16), ("vauxn", 16), ("vp", 1), ("vn", 1)]

# Xilinx System Monitor ----------------------------------------------------------------------------

class XilinxSystemMonitorChannel:
    def __init__(self, name, addr, bits, desc):
        self.name = name
        self.addr = addr
        self.bits = bits
        self.desc = "\n".join(desc) if isinstance(desc, list) else desc

class XilinxSystemMonitor(LiteXModule):
    def add_channel(self, channel):
        setattr(self, channel.name, CSRStatus(channel.bits, name=channel.name, description=channel.desc))
        channel.status = getattr(self, channel.name).status

    def expose_drp(self):
        self.drp_enable = CSRStorage() # Set to 1 to use DRP and disable auto-sampling.
        self.drp_read   = CSR()
        self.drp_write  = CSR()
        self.drp_drdy   = CSRStatus()
        self.drp_adr    = CSRStorage(self.dadr_size,  reset_less=True)
        self.drp_dat_w  = CSRStorage(16, reset_less=True)
        self.drp_dat_r  = CSRStatus(16)

        # # #

        den_pipe = Signal() # Add a register to ease timing closure of den.

        self.comb += [
            self.di.eq(self.drp_dat_w.storage),
            self.drp_dat_r.status.eq(self.do),
            If(self.drp_en,
               self.den.eq(den_pipe),
               self.dadr.eq(self.drp_adr.storage),
            )
        ]
        self.sync += [
            self.dwe.eq(self.drp_write.re),
            self.drp_en.eq(self.drp_enable.storage),
            den_pipe.eq(self.drp_read.re | self.drp_write.re),
            If(self.drp_read.re | self.drp_write.re,
                self.drp_drdy.status.eq(0)
            ).Elif(self.drdy,
                self.drp_drdy.status.eq(1)
            )
        ]

# Xilinx 7-Series System Monitor -------------------------------------------------------------------

S7SystemMonitorChannels = [
    XilinxSystemMonitorChannel(name="temperature", addr=0x0, bits=12, desc=[
        "Raw Temperature value from XADC.",
        "Temperature (°C) = ``Value`` x 503.975 / 4096 - 273.15.",
    ]),
    XilinxSystemMonitorChannel(name="vccint",      addr=0x1, bits=12, desc=[
        "Raw VCCINT value from XADC.",
        "VCCINT (V) = ``Value`` x 3 / 4096.",
    ]),
    XilinxSystemMonitorChannel(name="vccaux",      addr=0x2, bits=12, desc=[
        "Raw VCCAUX value from XADC.",
        "VCCAUX (V) = ``Value`` x 3 / 4096.",
    ]),
    XilinxSystemMonitorChannel(name="vccbram",     addr=0x6, bits=12, desc=[
        "Raw VCCBRAM value from XADC.",
        "VCCBRAM (V) = ``Value`` x 3 / 4096.",
    ]),
]

class S7SystemMonitor(XilinxSystemMonitor):
    def __init__(self, channels=S7SystemMonitorChannels, analog_pads=None):
        # Channels.
        for channel in channels:
            self.add_channel(channel)

        # End of Convertion/Sequence
        self.eoc = CSRStatus(description="End of Convertion Status, ``1``: Convertion Done.")
        self.eos = CSRStatus(description="End of Sequence Status,   ``1``: Sequence Done.")

        # Alarms
        self.alarm = Signal(8)
        self.ot    = Signal()

        # # #

        busy    = Signal()
        channel = Signal(7)
        eoc     = Signal()
        eos     = Signal()

        # XADC instance.
        self.dwe    = Signal()
        self.den    = Signal()
        self.drdy   = Signal()
        self.dadr   = Signal(7)
        self.di     = Signal(16)
        self.do     = Signal(16)
        self.drp_en = Signal()
        self.specials += Instance("XADC",
            # From UG480
            p_INIT_40   = 0x9000, p_INIT_41 = 0x2ef0, p_INIT_42 = 0x0400,
            p_INIT_48   = 0x4701, p_INIT_49 = 0x000f,
            p_INIT_4A   = 0x4700, p_INIT_4B = 0x0000,
            p_INIT_4C   = 0x0000, p_INIT_4D = 0x0000,
            p_INIT_4E   = 0x0000, p_INIT_4F = 0x0000,
            p_INIT_50   = 0xb5ed, p_INIT_51 = 0x5999,
            p_INIT_52   = 0xa147, p_INIT_53 = 0xdddd,
            p_INIT_54   = 0xa93a, p_INIT_55 = 0x5111,
            p_INIT_56   = 0x91eb, p_INIT_57 = 0xae4e,
            p_INIT_58   = 0x5999, p_INIT_5C = 0x5111,
            o_ALM       = self.alarm,
            o_OT        = self.ot,
            o_BUSY      = busy,
            o_CHANNEL   = channel,
            o_EOC       = eoc,
            o_EOS       = eos,
            i_VAUXP     = 0 if analog_pads is None else analog_pads.vauxp,
            i_VAUXN     = 0 if analog_pads is None else analog_pads.vauxn,
            i_VP        = 0 if analog_pads is None else analog_pads.vp,
            i_VN        = 0 if analog_pads is None else analog_pads.vn,
            i_CONVST    = 0,
            i_CONVSTCLK = 0,
            i_RESET     = ResetSignal("sys"),
            i_DCLK      = ClockSignal("sys"),
            i_DWE       = self.dwe,
            i_DEN       = self.den,
            o_DRDY      = self.drdy,
            i_DADDR     = self.dadr,
            i_DI        = self.di,
            o_DO        = self.do
        )

        # DRP.
        self.comb += If(~self.drp_en,
            self.den.eq(eoc),
            self.dadr.eq(channel),
        )

        # Channels update.
        channel_cases = dict(zip(
            [c.addr                    for c in channels],
            [c.status.eq(self.do >> 4) for c in channels],
        ))
        self.sync += If(self.drdy, Case(channel, channel_cases))

        # End of Conversion/Sequence update.
        self.sync += [
            self.eoc.status.eq((self.eoc.status & ~self.eoc.we) | eoc),
            self.eos.status.eq((self.eos.status & ~self.eos.we) | eos),
        ]

class XADC(S7SystemMonitor): pass # For compat.

# Xilinx Ultrascale System Monitor -----------------------------------------------------------------

USSystemMonitorChannels = [
    XilinxSystemMonitorChannel(name="temperature", addr=0x0, bits=10, desc=[
        "Raw Temperature value from SYSMONE1.",
        "Temperature (°C) = ``Value`` x 503.975 / 1024 - 273.15.",
    ]),
    XilinxSystemMonitorChannel(name="vccint",      addr=0x1, bits=10, desc=[
        "Raw VCCINT value from SYSMONE1.",
        "VCCINT (V) = ``Value`` x 3 / 1024.",
    ]),
    XilinxSystemMonitorChannel(name="vccaux",      addr=0x2, bits=10, desc=[
        "Raw VCCAUX value from SYSMONE1.",
        "VCCAUX (V) = ``Value`` x 3 / 1024.",
    ]),
    XilinxSystemMonitorChannel(name="vccbram",     addr=0x6, bits=10, desc=[
        "Raw VCCBRAM value from SYSMONE1.",
        "VCCBRAM (V) = ``Value`` x 3 / 1024.",
    ]),
]

class USSystemMonitor(XilinxSystemMonitor):
    def __init__(self, channels=USSystemMonitorChannels, primitive="SYSMONE1", sim_device=None, analog_pads=None):
        # Channels.
        for channel in channels:
            self.add_channel(channel)

        # End of Convertion/Sequence
        self.eoc = CSRStatus(description="End of Conversion Status, ``1``: Conversion Done.")
        self.eos = CSRStatus(description="End of Sequence Status,   ``1``: Sequence Done.")

        # Alarms
        self.alarm = Signal(16)
        self.ot    = Signal()

        # # #

        busy    = Signal()
        channel = Signal(8)
        eoc     = Signal()
        eos     = Signal()

        # SYSMOM instance.
        self.dwe    = Signal()
        self.den    = Signal()
        self.drdy   = Signal()
        self.dadr   = Signal(8)
        self.di     = Signal(16)
        self.do     = Signal(16)
        self.drp_en = Signal()
        self.params = dict()
        if sim_device is not None:
            self.params.update(p_SIM_DEVICE=sim_device)
        self.params.update(
            # From UG580
            p_INIT_40    = 0x9000, p_INIT_41 = 0x2fd0, p_INIT_42 = 0x1000,
            p_INIT_46    = 0x000f, p_INIT_48 = 0x4701, p_INIT_49 = 0x000f,
            p_INIT_47    = 0x000f, p_INIT_4A = 0x47e0, p_INIT_4B = 0x0000,
            p_INIT_4C    = 0x0000, p_INIT_4D = 0x0000,
            p_INIT_4E    = 0x0000, p_INIT_4F = 0x0000,
            p_INIT_50    = 0xb5ed, p_INIT_51 = 0x5999,
            p_INIT_52    = 0xa147, p_INIT_53 = 0xdddd,
            p_INIT_54    = 0xa93a, p_INIT_55 = 0x5111,
            p_INIT_56    = 0x91eb, p_INIT_57 = 0xae4e,
            p_INIT_58    = 0x5999, p_INIT_5C = 0x5111,
            o_ALM        = self.alarm,
            o_OT         = self.ot,
            o_BUSY       = busy,
            o_CHANNEL    = channel,
            o_EOC        = eoc,
            o_EOS        = eos,
            i_VAUXP      = 0 if analog_pads is None else analog_pads.vauxp,
            i_VAUXN      = 0 if analog_pads is None else analog_pads.vauxn,
            i_VP         = 0 if analog_pads is None else analog_pads.vp,
            i_VN         = 0 if analog_pads is None else analog_pads.vn,
            i_CONVST     = 0,
            i_CONVSTCLK  = 0,
            i_RESET      = ResetSignal("sys"),
            i_DCLK       = ClockSignal("sys"),
            i_DWE        = self.dwe,
            i_DEN        = self.den,
            o_DRDY       = self.drdy,
            i_DADDR      = self.dadr,
            i_DI         = self.di,
            o_DO         = self.do
        )
        self.specials += Instance(primitive, **self.params)

        # DRP.
        self.comb += If(~self.drp_en,
            self.den.eq(eoc),
            self.dadr.eq(channel),
        )

        # Channels update.
        channel_cases = dict(zip(
            [c.addr                              for c in channels],
            [c.status.eq((self.do >> 6) & 0x3ff) for c in channels],
        ))
        self.sync += If(self.drdy, Case(channel, channel_cases))

        # End of Convertion/Sequence update.
        self.sync += [
            self.eoc.status.eq((self.eoc.status & ~self.eoc.we) | eoc),
            self.eos.status.eq((self.eos.status & ~self.eos.we) | eos),
        ]

# Xilinx Ultrascale Plus System Monitor ------------------------------------------------------------

USPSystemMonitorChannels = [
    XilinxSystemMonitorChannel(name="temperature", addr=0x0, bits=10, desc=[
        "Raw Temperature value from SYSMONE4.",
        "Temperature (°C) = ``Value`` x 507.5921310 / 1024 - 279.42657680."
    ]),
    XilinxSystemMonitorChannel(name="vccint",      addr=0x1, bits=10, desc=[
        "Raw VCCINT value from SYSMONE4.",
        "VCCINT (V) = ``Value`` x 3 / 1024."
    ]),
    XilinxSystemMonitorChannel(name="vccaux",      addr=0x2, bits=10, desc=[
        "Raw VCCAUX value from SYSMONE4.",
        "VCCAUX (V) = ``Value`` x 3 / 1024."
    ]),
    XilinxSystemMonitorChannel(name="vccbram",     addr=0x6, bits=10, desc=[
        "Raw VCCBRAM value from SYSMONE4.",
        "VCCBRAM (V) = ``Value`` x 3 / 1024."
    ]),
]

ZynqUSPSystemMonitorChannels = USPSystemMonitorChannels + [
    XilinxSystemMonitorChannel(name="vccpsintlp", addr=0xd, bits=10, desc=[
        "Raw VCCPSINTLP value from SYSMONE4.",
        "VCCPSINTLP (V) = ``Value`` x 3 / 1024.",
    ]),
    XilinxSystemMonitorChannel(name="vccpsintfp", addr=0xe, bits=10, desc=[
        "Raw VCCPSINTFP value from SYSMONE4.",
        "VCCPSINTFP (V) = ``Value`` x 3 / 1024.",
    ]),
    XilinxSystemMonitorChannel(name="vccpsaux",   addr=0xf, bits=10, desc=[
        "Raw VCCPSAUX value from SYSMONE4.",
        "VCCPSAUX (V) = ``Value`` x 3 / 1024.",
    ]),
]

class USPSystemMonitor(USSystemMonitor):
    def __init__(self, analog_pads=None):
        USSystemMonitor.__init__(self,
            channels    = USPSystemMonitorChannels,
            primitive   = "SYSMONE4",
            sim_device  = "ULTRASCALE_PLUS",
            analog_pads = analog_pads,
        )

class ZynqUSPSystemMonitor(USSystemMonitor):
    def __init__(self, analog_pads=None):
        USSystemMonitor.__init__(self,
            channels    = ZynqUSPSystemMonitorChannels,
            primitive   = "SYSMONE4",
            sim_device  = "ZYNQ_ULTRASCALE",
            analog_pads = analog_pads,
        )
