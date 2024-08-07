#
# This file is part of LiteX.
#
# Copyright (c) 2024 Fin Maaß <f.maass@vogl-electronic.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *

from litex.soc.integration.doc import AutoDoc
from litex.soc.interconnect import stream
from litex.soc.interconnect.csr import *

from litex.soc.cores.litei2c.common import *
from litex.soc.cores.litei2c.crossbar import LiteI2CCrossbar
from litex.soc.cores.litei2c.master import LiteI2CMaster
from litex.soc.cores.litei2c.generic_phy import LiteI2CPHYCore


class LiteI2CCore(Module):
    def __init__(self):
        self.source = stream.Endpoint(i2c_core2phy_layout)
        self.sink   = stream.Endpoint(i2c_phy2core_layout)
        self.enable = Signal()


class LiteI2C(Module, AutoCSR, AutoDoc):
    """I2C Controller wrapper.

    The ``LiteI2C`` class provides a wrapper that can instantiate ``LiteI2CMaster`` and connect it to the PHY.

    Access to PHY can be shared via crossbar.

    Parameters
    ----------
    sys_clk_freq : int
        Frequency of the system clock.

    phy : Module
        Module or object that contains PHY stream interfaces and a enable signal to connect
        the ``LiteI2C`` to. If not provided, it will be created automatically based on the pads.
    
    pads : Object
        I2C pads description.

    clock_domain : str
        Name of LiteI2C clock domain.

    with_master : bool
        Enables register-operated I2C master controller.

    """

    def __init__(self, sys_clk_freq, phy=None, pads=None, clock_domain="sys",
        with_master=True, i2c_master_tx_fifo_depth=1, i2c_master_rx_fifo_depth=1):

        if phy is None:
            if pads is None:
                raise ValueError("Either phy or pads must be provided.")
            self.submodules.phy = phy = LiteI2CPHYCore(pads, clock_domain, sys_clk_freq)


        self.submodules.crossbar = crossbar = LiteI2CCrossbar(clock_domain)

        self.comb += phy.enable.eq(crossbar.enable)

        if with_master:
            self.submodules.master = master = LiteI2CMaster(
                tx_fifo_depth = i2c_master_tx_fifo_depth,
                rx_fifo_depth = i2c_master_rx_fifo_depth)
            port_master = crossbar.get_port(master.enable)
            self.comb += [
                port_master.source.connect(master.sink),
                master.source.connect(port_master.sink),
            ]

        if clock_domain != "sys":
            self.comb += [
                crossbar.tx_cdc.source.connect(phy.sink),
                phy.source.connect(crossbar.rx_cdc.sink),
            ]
        else:
            self.comb += [
                crossbar.master.source.connect(phy.sink),
                phy.source.connect(crossbar.master.sink),
            ]

    def add_i2c_device(self, i2c_device):
        port = self.crossbar.get_port(i2c_device.enable)
        self.comb += [
            port.source.connect(i2c_device.sink),
            i2c_device.source.connect(port.sink),
        ]
        
