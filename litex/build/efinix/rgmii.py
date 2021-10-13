#
# This file is part of LiteEth.
#
# Copyright (c) 2021 Franck Jullien <franck.jullien@collshade.fr>
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

# RGMII PHY for Efinix FPGAs

# FIXME: Cleanup/Move.

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
        tx_data_h = []
        tx_data_l = []

        # This a workaround, we could use signals with 4 bits but there is
        # a problem with the Python API that prevents it
        for i in range(4):
                tx_data_h.append(platform.add_iface_io(name + str(i) + '_HI'))
                tx_data_l.append(platform.add_iface_io(name + str(i) + '_LO'))

                block = {'type':'GPIO',
                        'mode':'OUTPUT',
                        'name':name + str(i),
                        'location':[pad[i]],
                        'size':1,
                        'out_reg':'DDIO_RESYNC',
                        'out_clk_pin':'auto_eth_tx_clk',
                        'is_inclk_inverted':False,
                        'drive_strength':4  # TODO: get this from pin constraints
                }
                platform.toolchain.ifacewriter.blocks.append(block)

        platform.del_record_signal(pads, pads.tx_data)

        name = platform.get_pin_name(pads.tx_ctl)
        pad = platform.get_pin_location(pads.tx_ctl)
        name = 'auto_' + name
        tx_ctl_h = platform.add_iface_io(name + '_HI')
        tx_ctl_l = platform.add_iface_io(name + '_LO')

        block = {'type':'GPIO',
                'mode':'OUTPUT',
                'name':name,
                'location':[pad[0]],
                'size':1,
                'out_reg':'DDIO_RESYNC',
                'out_clk_pin':'auto_eth_tx_clk',
                'is_inclk_inverted':False,
                'drive_strength':4  # TODO: get this from pin constraints
        }
        platform.toolchain.ifacewriter.blocks.append(block)
        platform.del_record_signal(pads, pads.tx_ctl)

        self.sync += [ tx_data_h[0].eq(sink.data[0]),
                       tx_data_h[1].eq(sink.data[1]),
                       tx_data_h[2].eq(sink.data[2]),
                       tx_data_h[3].eq(sink.data[3]),
                       tx_data_l[0].eq(sink.data[4]),
                       tx_data_l[1].eq(sink.data[5]),
                       tx_data_l[2].eq(sink.data[6]),
                       tx_data_l[3].eq(sink.data[7]),
                       tx_ctl_h.eq(sink.valid),
                       tx_ctl_l.eq(sink.valid),
        ]

        self.comb += sink.ready.eq(1)

class LiteEthPHYRGMIIRX(Module):
    def __init__(self, platform, pads):
        self.source = source = stream.Endpoint(eth_phy_description(8))

        # # #

        rx_data = Signal(8)

        # Add a DDIO_RESYNC input block with 'auto_eth_rx_clk' as clock
        name = platform.get_pin_name(pads.rx_data)
        pad = platform.get_pin_location(pads.rx_data)
        name = 'auto_' + name
        rx_data_h = []
        rx_data_l = []
        # This a workaround, we could use signals with 4 bits but there is
        # a problem with the Python API that prevents it
        for i in range(4):
            rx_data_h.append(platform.add_iface_io(name + str(i) + '_HI'))
            rx_data_l.append(platform.add_iface_io(name + str(i) + '_LO'))

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

        self.comb += rx_data.eq(Cat(rx_data_l[0], rx_data_l[1], rx_data_l[2], rx_data_l[3],
                                    rx_data_h[0], rx_data_h[1], rx_data_h[2], rx_data_h[3]))

        rx_ctl_d = Signal()
        self.sync += rx_ctl_d.eq(pads.rx_ctl)

        last = Signal()
        self.comb += last.eq(~pads.rx_ctl & rx_ctl_d)
        self.sync += [
            source.valid.eq(rx_ctl_d),
            source.data.eq(rx_data),
            source.last.eq(last),
        ]

class LiteEthPHYRGMIICRG(Module, AutoCSR):
    def __init__(self, platform, clock_pads, with_hw_init_reset, tx_delay=2e-9, hw_reset_cycles=256):
        self._reset = CSRStorage()

        # # #

        # Clocks

        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()

        # *************************
        # *        RX CLOCK       *
        # *************************

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

        cmd = "create_clock -period {} auto_eth_rx_clk".format(1e9/125e6)
        platform.toolchain.additional_sdc_commands.append(cmd)

        # *************************
        # *     TX CLOCK PIN      *
        # *************************

        block = {'type':'GPIO',
                 'size':1,
                 # Get the location from the original resource
                 'location': platform.get_pin_location(clock_pads.tx)[0],
                 'name':'auto_eth_tx_delayed_clk',
                 'mode':'OUTPUT_CLK'
        }
        platform.toolchain.ifacewriter.blocks.append(block)

        # *************************
        # *        TX CLOCK       *
        # *************************

        self.submodules.pll = pll = TRIONPLL(platform)
        pll.register_clkin(None, 125e6, name='auto_eth_rx_clk')
        pll.create_clkout(None,  125e6, phase=0, name='auto_eth_tx_delayed_clk')
        pll.create_clkout(self.cd_eth_tx,  125e6, name='auto_eth_tx_clk')

        cmd = "create_clock -period {} auto_eth_tx_clk".format(1e9/125e6)
        platform.toolchain.additional_sdc_commands.append(cmd)

        platform.delete(clock_pads)

        # *************************
        # *        RESET          *
        # *************************

        self.reset = reset = Signal()
        if with_hw_init_reset:
            self.submodules.hw_reset = LiteEthPHYHWReset(cycles=hw_reset_cycles)
            self.comb += reset.eq(self._reset.storage | self.hw_reset.reset)
        else:
            self.comb += reset.eq(self._reset.storage)
        if hasattr(clock_pads, "rst_n"):
            self.comb += clock_pads.rst_n.eq(~reset)
        self.specials += [
            AsyncResetSynchronizer(self.cd_eth_tx, reset),
            AsyncResetSynchronizer(self.cd_eth_rx, reset),
        ]

        #platform.add_false_path_constraints(ClockSignal('sys'), self.cd_eth_rx.clk, self.cd_eth_tx.clk)

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
