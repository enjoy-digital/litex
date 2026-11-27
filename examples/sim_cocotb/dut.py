#
# This file is part of the LiteX cocotb+Verilator simulation POC.
# See ../../../issues/2380 (enjoy-digital/litex) for background.
#
# Copyright (c) 2026 Vishnu Sentha <vishnusentha@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause
"""
Minimal, CPU-less LiteX design used to demonstrate driving a LiteX-generated
design with a cocotb testbench under Verilator.

Design goals (see README.md for the full rationale):

  * No CPU, no Wishbone/CSR bus -- cocotb plays the role of the "host",
    driving every signal directly, the way a peripheral developer would
    when bringing up a new core in isolation.
  * Still built entirely out of LiteX/Migen building blocks (LiteXModule,
    clock domains, MultiReg synchronizers) and one real LiteX peripheral
    core (``litex.soc.cores.uart.RS232PHY``), so it behaves like a genuine
    LiteX design, not a bare hand-written Verilog stub.
  * Verilog is generated with Migen's own ``verilog.convert()`` instead of
    ``SimPlatform.build()``. ``SimPlatform``/``VerilatorSimulator`` own a
    C++-driven main loop that starts the simulation itself, which conflicts
    with cocotb, where Python (via the VPI/GPI layer) owns the main loop.
    Using ``verilog.convert()`` keeps this example fully standalone and
    makes zero changes to ``litex/build/sim/``.

Run standalone to (re)generate ``dut.v``:

    python3 dut.py

The Makefile does this automatically before invoking Verilator.
"""
from migen import Module, Signal, ClockDomain, If, Record
from migen.fhdl import verilog
from migen.genlib.cdc import MultiReg

from litex.gen import LiteXModule
from litex.soc.cores.uart import RS232PHY

# Parameters -----------------------------------------------------------------

GPIO_WIDTH    = 8
SYS_CLK_FREQ  = 100e6   # 100 MHz system clock used by the testbench.
UART_BAUDRATE = 115200  # Matches the default LiteX BIOS console baudrate.


class CocotbDemoTop(LiteXModule):
    """
    Top-level module exercised by the cocotb testbench.

    Port summary
    ------------
    sys_clk, sys_rst                                    : clock / reset
    gpio_in[GPIO_WIDTH]                                  : async input pins
    gpio_in_sync[GPIO_WIDTH]                              : 2FF-synchronized view of gpio_in
    gpio_out_data[GPIO_WIDTH], gpio_out_we                : write port for the GPIO output register
    gpio_out[GPIO_WIDTH]                                  : registered GPIO output pins
    uart_tx_data[8], uart_tx_valid, uart_tx_ready          : byte-level handshake INTO the UART PHY
    uart_rx_data[8], uart_rx_valid, uart_rx_ready          : byte-level handshake OUT OF the UART PHY
    uart_tx, uart_rx                                       : the actual serial line pins

    The UART is exposed at the byte-level stream (sink/source) handshake
    that ``RS232PHY`` already provides internally, *and* at the raw serial
    pins. Driving the stream handshake means the cocotb testbench doesn't
    have to hand-roll bit-level UART framing to send a byte; asserting
    ``uart_tx_valid``/``uart_tx_data`` for one cycle (until ``uart_tx_ready``)
    queues a full start+8N1+stop frame on ``uart_tx``. The raw ``uart_tx``/
    ``uart_rx`` pins are still exposed so the testbench (or a waveform
    viewer) can also observe/inject the actual serial bitstream.
    """

    def __init__(self, gpio_width=GPIO_WIDTH, sys_clk_freq=SYS_CLK_FREQ,
                 baudrate=UART_BAUDRATE):
        # Clock / Reset -------------------------------------------------
        self.sys_clk = sys_clk = Signal()
        self.sys_rst = sys_rst = Signal()

        self.clock_domains.cd_sys = ClockDomain()
        self.comb += self.cd_sys.clk.eq(sys_clk)
        self.comb += self.cd_sys.rst.eq(sys_rst)

        # GPIO ------------------------------------------------------------
        # Output register: cocotb pulses gpio_out_we for one cycle with the
        # desired value on gpio_out_data; the value is then held on gpio_out.
        self.gpio_out_data = gpio_out_data = Signal(gpio_width)
        self.gpio_out_we   = gpio_out_we   = Signal()
        self.gpio_out      = gpio_out      = Signal(gpio_width, reset=0)
        self.sync += If(gpio_out_we, gpio_out.eq(gpio_out_data))

        # Input: cocotb drives gpio_in asynchronously (like an external
        # button/sensor); gpio_in_sync is the 2FF-synchronized, glitch-safe
        # view a real LiteX peripheral would read from -- this mirrors the
        # MultiReg pattern litex.soc.cores.gpio.GPIOIn uses internally.
        self.gpio_in      = gpio_in      = Signal(gpio_width)
        self.gpio_in_sync = gpio_in_sync = Signal(gpio_width)
        self.specials += MultiReg(gpio_in, gpio_in_sync)

        # UART --------------------------------------------------------------
        # Real LiteX UART PHY core (litex.soc.cores.uart.RS232PHY), wired
        # directly to top-level pins/handshake signals -- no CSR bus, no
        # Wishbone, no CPU. cocotb is the bus master.
        self.uart_tx = uart_tx = Signal()
        self.uart_rx = uart_rx = Signal()

        uart_pads = Record([("tx", 1), ("rx", 1)])
        self.comb += [
            uart_tx.eq(uart_pads.tx),
            uart_pads.rx.eq(uart_rx),
        ]

        self.uart_phy = uart_phy = RS232PHY(
            uart_pads,
            clk_freq = int(sys_clk_freq),
            baudrate = int(baudrate),
        )

        self.uart_tx_data  = Signal(8)
        self.uart_tx_valid = Signal()
        self.uart_tx_ready = Signal()
        self.uart_rx_data  = Signal(8)
        self.uart_rx_valid = Signal()
        self.uart_rx_ready = Signal()

        self.comb += [
            uart_phy.sink.data.eq(self.uart_tx_data),
            uart_phy.sink.valid.eq(self.uart_tx_valid),
            self.uart_tx_ready.eq(uart_phy.sink.ready),

            self.uart_rx_data.eq(uart_phy.source.data),
            self.uart_rx_valid.eq(uart_phy.source.valid),
            uart_phy.source.ready.eq(self.uart_rx_ready),
        ]

    def ios(self):
        """Signals that must become ports on the generated top module."""
        return {
            self.sys_clk, self.sys_rst,
            self.gpio_in, self.gpio_in_sync,
            self.gpio_out_data, self.gpio_out_we, self.gpio_out,
            self.uart_tx_data, self.uart_tx_valid, self.uart_tx_ready,
            self.uart_rx_data, self.uart_rx_valid, self.uart_rx_ready,
            self.uart_tx, self.uart_rx,
        }


def generate(v_file="dut.v", top_name="dut"):
    top = CocotbDemoTop()
    verilog.convert(
        top,
        ios  = top.ios(),
        name = top_name,
    ).write(v_file)
    print(f"Wrote {v_file} (top module '{top_name}')")


if __name__ == "__main__":
    generate()
