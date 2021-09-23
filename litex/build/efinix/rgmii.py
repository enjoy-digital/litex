#
# This file is part of LiteEth.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# RGMII PHY for 7-Series Xilinx FPGA

from migen import *
from migen.genlib.resetsync import AsyncResetSynchronizer

from litex.build.generic_platform import *
from litex.soc.cores.clock import *

from liteeth.common import *
from liteeth.phy.common import *


class LiteEthPHYRGMIITX(Module):
    def __init__(self, platform, pads):
        self.sink = sink = stream.Endpoint(eth_phy_description(8))

        # # #

        name = platform.get_pin_name(pads.tx_data)
        pad = platform.get_pin_location(pads.tx_data)
        name = 'auto_' + name
        tx_data_d1 = []
        tx_data_d2 = []
        # This a workaround, we could use signals with 4 bits but there is
        # a problem with the Python API that prevents it

        #tx_data_d1 = platform.add_iface_io(name + '_HI', 4)
        #tx_data_d2 = platform.add_iface_io(name + '_LO', 4)

        for i in range(4):
                tx_data_d1.append(platform.add_iface_io(name + str(i) + '_HI'))
                tx_data_d2.append(platform.add_iface_io(name + str(i) + '_LO'))

                block = {'type':'GPIO',
                        'mode':'OUTPUT',
                        'name':name + str(i),
                       #'name':name,
                        'location':[pad[i]],
                        'size':1,
                       #'location':pad,
                       #'size':4,
                        'out_reg':'DDIO_RESYNC',
                        'out_clk_pin':'auto_eth_tx_clk', # -------------------------- TODO
                        'is_inclk_inverted':False
                }
                platform.toolchain.ifacewriter.blocks.append(block)

        platform.del_record_signal(pads, pads.tx_data)

        #self.comb += pads.tx_ctl.eq(sink.valid)
        #self.comb += tx_data_d1.eq(sink.data[0:4])
        #self.comb += tx_data_d2.eq(sink.data[4:8])
        #self.comb += sink.ready.eq(1)

        self.comb += [ pads.tx_ctl.eq(sink.valid),
                       tx_data_d1[0].eq(sink.data[0]),
                       tx_data_d1[1].eq(sink.data[1]),
                       tx_data_d1[2].eq(sink.data[2]),
                       tx_data_d1[3].eq(sink.data[3]),
                       tx_data_d2[0].eq(sink.data[4]),
                       tx_data_d2[1].eq(sink.data[5]),
                       tx_data_d2[2].eq(sink.data[6]),
                       tx_data_d2[3].eq(sink.data[7]),
                       sink.ready.eq(1),
        ]

class LiteEthPHYRGMIIRX(Module):
    def __init__(self, platform, pads):
        self.source = source = stream.Endpoint(eth_phy_description(8))

        # # #

        rx_ctl_d = Signal()
        rx_data = Signal(8)

        # pads.rx_ctl can't be connected to a special GPIO (DDIO) because
        # of this board layout.

        # Add a DDIO_RESYNC input block with 'auto_eth_rx_clk' as clock
        name = platform.get_pin_name(pads.rx_data)
        pad = platform.get_pin_location(pads.rx_data)
        name = 'auto_' + name
        rx_data_d1 = []
        rx_data_d2 = []
        # This a workaround, we could use signals with 4 bits but there is
        # a problem with the Python API that prevents it
        for i in range(4):
            rx_data_d1.append(platform.add_iface_io(name + str(i) + '_HI'))
            rx_data_d2.append(platform.add_iface_io(name + str(i) + '_LO'))

            block = {'type':'GPIO',
                    'mode':'INPUT',
                    'name':name + str(i),
                    'location':[pad[i]],
                    'size':1,
                    'in_reg':'DDIO_RESYNC',
                    'in_clk_pin':'auto_eth_rx_clk',
                    'is_inclk_inverted':False
            }
            platform.toolchain.ifacewriter.blocks.append(block)

        platform.del_record_signal(pads, pads.rx_data)

        self.comb += rx_data.eq(Cat(rx_data_d1[0], rx_data_d1[1], rx_data_d1[2], rx_data_d1[3],
                                    rx_data_d2[0], rx_data_d2[1], rx_data_d2[2], rx_data_d2[3]))

        self.sync += rx_ctl_d.eq(pads.rx_ctl)

        last = Signal()
        self.comb += last.eq(~pads.rx_ctl & rx_ctl_d)
        self.sync += [
            source.valid.eq(pads.rx_ctl),
            source.data.eq(rx_data)
        ]
        self.comb += source.last.eq(last)

class LiteEthPHYRGMIICRG(Module, AutoCSR):
    def __init__(self, platform, clock_pads, with_hw_init_reset, tx_delay=2e-9, hw_reset_cycles=256):
        self._reset = CSRStorage()

        # # #

        # Clocks

        self.clock_domains.cd_eth_rx         = ClockDomain()
        self.clock_domains.cd_eth_tx         = ClockDomain()
        self.clock_domains.cd_eth_tx_delayed = ClockDomain(reset_less=True)

        # Add a GPIO block with clock input property
        # Add a input 'auto_eth_rx_clk' to the top.v 
        clkrx = platform.add_iface_io('auto_eth_rx_clk')
        block = {'type':'GPIO',
                 'size':1,
                 # Get the location from the original resource
                 'location': platform.get_pin_location(clock_pads.rx)[0],
                 'name':platform.get_pin_name(clkrx),
                 'mode':'INPUT_CLK'
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        self.comb += self.cd_eth_rx.clk.eq(clkrx)

        clktx = platform.add_iface_io('auto_eth_tx_delayed_clk')
        block = {'type':'GPIO',
                 'size':1,
                 # Get the location from the original resource
                 'location': platform.get_pin_location(clock_pads.tx)[0],
                 'name':platform.get_pin_name(clktx),
                 'mode':'OUTPUT_CLK'
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        self.comb += clktx.eq(self.cd_eth_tx.clk)

        self.submodules.pll = pll = TRIONPLL(platform)
        # Internal clock must come from a named signal
        pll.register_clkin(None, 125e6, name='auto_eth_rx_clk')
        pll.create_clkout(None,  125e6, phase=90, name='auto_eth_tx_delayed_clk')
        pll.create_clkout(None,  125e6, name='auto_eth_tx_clk')

        platform.delete(clock_pads)

        ## Reset
        #self.reset = reset = Signal()
        #if with_hw_init_reset:
        #    self.submodules.hw_reset = LiteEthPHYHWReset(cycles=hw_reset_cycles)
        #    self.comb += reset.eq(self._reset.storage | self.hw_reset.reset)
        #else:
        #    self.comb += reset.eq(self._reset.storage)
        #if hasattr(clock_pads, "rst_n"):
        #    self.comb += clock_pads.rst_n.eq(~reset)
        #self.specials += [
        #    AsyncResetSynchronizer(self.cd_eth_tx, reset),
        #    AsyncResetSynchronizer(self.cd_eth_rx, reset),
        #]


class LiteEthPHYRGMII(Module, AutoCSR):
    dw          = 8
    tx_clk_freq = 125e6
    rx_clk_freq = 125e6
    def __init__(self, platform, clock_pads, pads, with_hw_init_reset=True, tx_delay=2e-9, rx_delay=2e-9,
            iodelay_clk_freq=200e6, hw_reset_cycles=256):
        self.submodules.crg = LiteEthPHYRGMIICRG(platform, clock_pads, with_hw_init_reset, tx_delay, hw_reset_cycles)
        self.submodules.tx  = ClockDomainsRenamer("eth_tx")(LiteEthPHYRGMIITX(platform, pads))
        self.submodules.rx  = ClockDomainsRenamer("eth_rx")(LiteEthPHYRGMIIRX(platform, pads))
        self.sink, self.source = self.tx.sink, self.rx.source

        #if hasattr(pads, "mdc"):
        #    self.submodules.mdio = LiteEthPHYMDIO(pads)
