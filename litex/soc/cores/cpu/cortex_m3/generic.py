#
# This file is part of LiteX.
#
# Copyright (c) 2026 Enjoy-Digital <contact@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.gen import *
from litex.soc.interconnect import ahb, wishbone


class CortexM3Generic(LiteXModule):
    """Bus and control wiring for the Cortex-M3 DesignStart Eval integration level.

    The three AHB masters remain independent up to the LiteX interconnect. No Arm
    RTL or vendor-specific memory/debug components are included here.
    """
    def __init__(self, reset, interrupt):
        self.ahb_buses    = []
        self.periph_buses = []
        self.sys_reset_request = Signal()
        self.sys_reset         = Signal()

        # Register and stretch AIRCR/debug system reset requests. Keep the debug
        # power-on reset separate, and reset the AHB bridges with the processor.
        reset_count = Signal(3)
        self.sync += If(self.sys_reset_request,
            reset_count.eq(4)
        ).Elif(reset_count != 0,
            reset_count.eq(reset_count - 1)
        )
        self.comb += self.sys_reset.eq(reset_count != 0)
        cpu_reset = reset | self.sys_reset
        debug_power_request = Signal()
        debug_power_ack     = Signal()
        self.sync += debug_power_ack.eq(debug_power_request)

        self.cpu_params = dict(
            i_FCLK        = ClockSignal("sys"),
            i_HCLK        = ClockSignal("sys"),
            i_TRACECLKIN  = ClockSignal("sys"),
            i_PORESETn    = ~(ResetSignal("sys") | reset),
            i_SYSRESETn   = ~(ResetSignal("sys") | cpu_reset),
            o_SYSRESETREQ = self.sys_reset_request,
            i_RSTBYPASS   = 0,
            i_CGBYPASS    = 1, # No internal clock gating on FPGA.
            i_ISOLATEn    = 1,
            i_RETAINn     = 1,
            i_BIGEND      = 0,
            i_MPUDISABLE  = 1,
            i_DNOTITRANS  = 0, # Independent I-Code/D-Code bridges, no code mux.
            i_IFLUSH      = 0,
            i_AUXFAULT    = Constant(0, 32),
            i_INTISR      = Cat(interrupt, Constant(0, 240 - len(interrupt))),
            i_INTNMI      = 0,
            i_STCLK       = 0,
            i_STCALIB     = Constant(1 << 25, 26), # No external SysTick reference.
            i_RXEV        = 0,
            i_SLEEPHOLDREQn = 1,
            i_WICENREQ    = 0,
            i_EDBGRQ      = 0,
            i_DBGRESTART  = 0,
            i_FIXMASTERTYPE = 0,
            i_TSVALUEB    = Constant(0, 48),
            i_SE          = 0,
            # Debug is disabled until add_jtag() supplies physical pads.
            i_DBGEN       = 0,
            i_NIDEN       = 0,
            i_nTRST       = 0,
            i_SWCLKTCK    = 0,
            i_SWDITMS     = 1,
            i_TDI         = 0,
            o_CDBGPWRUPREQ = debug_power_request,
            i_CDBGPWRUPACK = debug_power_ack,
            # Rely on the core's local exclusive monitor. There is no global
            # monitor protecting shared memory against DMA/other bus masters.
            i_EXRESPD     = 0,
            i_EXRESPS     = 0,
        )

        for suffix in "IDS":
            bus = ahb.AHBInterface(data_width=32, address_width=32)
            wb  = wishbone.Interface(data_width=32, address_width=32, addressing="word")
            bridge = ResetInserter()(ahb.AHB2Wishbone(bus, wb))
            self.submodules += bridge
            self.comb += [bus.sel.eq(1), bridge.reset.eq(cpu_reset)]
            self.ahb_buses.append(bus)
            self.periph_buses.append(wb)
            self.cpu_params.update({
                f"o_HADDR{suffix}":  bus.addr,
                f"o_HTRANS{suffix}": bus.trans,
                f"o_HSIZE{suffix}":  bus.size,
                f"o_HBURST{suffix}": bus.burst,
                f"o_HPROT{suffix}":  bus.prot,
                f"i_HRDATA{suffix}": bus.rdata,
                f"i_HREADY{suffix}": bus.readyout,
                f"i_HRESP{suffix}":  Cat(bus.resp, Constant(0, 1)),
            })
            if suffix == "I":
                self.comb += [bus.write.eq(0), bus.wdata.eq(0)]
            else:
                self.cpu_params.update({
                    f"o_HWRITE{suffix}": bus.write,
                    f"o_HWDATA{suffix}": bus.wdata,
                })
            if suffix == "S":
                self.cpu_params["o_HMASTLOCKS"] = bus.mastlock
