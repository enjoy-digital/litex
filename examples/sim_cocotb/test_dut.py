#
# This file is part of the LiteX cocotb+Verilator simulation POC.
# See ../../../issues/2380 (enjoy-digital/litex) for background.
#
# Copyright (c) 2026 Vishnu Sentha <vishnusentha@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause
"""
cocotb testbench for ``dut.py`` / ``dut.v``.

Exercises the CPU-less LiteX design entirely from Python, the way a
peripheral developer would when bringing up a new core in isolation:

  * ``test_gpio_out_register``                    -- write the GPIO output
    register and check it is held.
  * ``test_gpio_out_holds_without_write_enable``   -- writes are ignored
    unless ``gpio_out_we`` is pulsed.
  * ``test_gpio_in_synchronizer``                  -- drive ``gpio_in``
    asynchronously and check ``gpio_in_sync`` follows it after the 2FF
    synchronizer latency.
  * ``test_uart_loopback``                         -- physically loop
    ``uart_tx`` back to ``uart_rx`` (as if a wire bridged the two pins on a
    board) and send a byte through the byte-level stream handshake,
    confirming it comes back out the RX stream handshake unchanged.

Run with:

    python3 test_runner.py

or

    pytest test_runner.py
"""
import random

import cocotb
from cocotb.clock import Clock
from cocotb.triggers import RisingEdge, ReadOnly, ReadWrite, Event

SYS_CLK_PERIOD_NS = 10  # 100 MHz, matches dut.py's SYS_CLK_FREQ.
UART_BAUDRATE      = 115200  # Must match dut.py's UART_BAUDRATE.


async def start_clock(dut):
    cocotb.start_soon(Clock(dut.sys_clk, SYS_CLK_PERIOD_NS, unit="ns").start())


async def reset_dut(dut):
    """Assert reset, hold all inputs at known-idle values, then release."""
    dut.sys_rst.value      = 1
    dut.gpio_in.value      = 0
    dut.gpio_out_data.value = 0
    dut.gpio_out_we.value   = 0
    dut.uart_tx_data.value  = 0
    dut.uart_tx_valid.value = 0
    # Held high for the whole test: the testbench is always ready to accept
    # received bytes, like a simple "always draining" peripheral consumer.
    dut.uart_rx_ready.value = 1
    dut.uart_rx.value       = 1  # UART idle/mark state.
    for _ in range(5):
        await RisingEdge(dut.sys_clk)
    dut.sys_rst.value = 0
    await RisingEdge(dut.sys_clk)


@cocotb.test()
async def test_gpio_out_register(dut):
    """gpio_out_we pulses gpio_out_data into gpio_out for one write."""
    await start_clock(dut)
    await reset_dut(dut)

    value = 0xA5
    dut.gpio_out_data.value = value
    dut.gpio_out_we.value   = 1
    await RisingEdge(dut.sys_clk)
    dut.gpio_out_we.value   = 0
    dut.gpio_out_data.value = 0

    await ReadOnly()
    assert int(dut.gpio_out.value) == value, \
        f"gpio_out: expected {value:#x}, got {int(dut.gpio_out.value):#x}"


@cocotb.test()
async def test_gpio_out_holds_without_write_enable(dut):
    """Without gpio_out_we, gpio_out must not change even if data changes."""
    await start_clock(dut)
    await reset_dut(dut)

    # Prime gpio_out with a known value first.
    dut.gpio_out_data.value = 0x3C
    dut.gpio_out_we.value   = 1
    await RisingEdge(dut.sys_clk)
    dut.gpio_out_we.value   = 0

    # Change gpio_out_data without asserting we -- gpio_out must hold.
    dut.gpio_out_data.value = 0xFF
    for _ in range(4):
        await RisingEdge(dut.sys_clk)

    await ReadOnly()
    assert int(dut.gpio_out.value) == 0x3C, \
        f"gpio_out changed without write-enable: {int(dut.gpio_out.value):#x}"


@cocotb.test()
async def test_gpio_in_synchronizer(dut):
    """gpio_in_sync must track gpio_in after the 2FF synchronizer latency."""
    await start_clock(dut)
    await reset_dut(dut)

    value = 0x66
    dut.gpio_in.value = value

    # MultiReg is a 2-flop synchronizer; allow a couple of cycles of margin
    # beyond the minimum 2 for the change to propagate through.
    for _ in range(4):
        await RisingEdge(dut.sys_clk)

    await ReadOnly()
    assert int(dut.gpio_in_sync.value) == value, \
        f"gpio_in_sync: expected {value:#x}, got {int(dut.gpio_in_sync.value):#x}"


@cocotb.test()
async def test_uart_loopback(dut):
    """
    Physically loop uart_tx back to uart_rx (as if a wire bridged the two
    pins on a board), then push a byte in via the TX stream handshake and
    confirm the same byte comes out the RX stream handshake.

    This exercises the *real* litex.soc.cores.uart.RS232PHY core, both its
    TX bit-framing (start + 8N1 + stop) and its RX bit-sampling/framing, all
    driven purely from cocotb -- no CSR bus, no CPU.

    Timing note: RS232PHYTX and RS232PHYRX each run their own
    RS232ClkPhaseAccum baud-tick generator off the *same* tuning word, but
    with different phase preloads -- TX preloads the full tuning word, so
    its first tick (and hence each bit-edge update) lands a full bit period
    after entering its RUN state; RX preloads half that, so it samples
    mid-bit for noise immunity. The two accumulators are otherwise
    unsynchronized, so RS232PHYRX's completion pulse (source.valid, held
    for exactly one clock) lands roughly half a bit period *before*
    RS232PHYTX's own completion (sink.ready) -- i.e. before the TX-queueing
    loop below even returns. Watching uart_rx_valid only *after* that loop
    finishes would miss the pulse entirely, so the RX capture below runs
    concurrently, started before the byte is even queued.
    """
    await start_clock(dut)
    await reset_dut(dut)

    # Loop uart_tx back into uart_rx every cycle -- cocotb stands in for the
    # PCB trace that would normally bridge the two pins. Reading uart_tx
    # immediately after RisingEdge races the DUT's own posedge-triggered
    # update (the read can see the pre-edge value), so wait for the
    # ReadWrite phase first: per the simulator's per-timestep region order
    # (Active/NBA -> ReadWrite -> ReadOnly), ReadWrite fires after
    # non-blocking assignments have been applied (so uart_tx already
    # reflects its new, settled value) but, unlike ReadOnly, still permits
    # writes -- exactly what's needed to read-then-write uart_rx in the
    # same timestep.
    async def loopback():
        while True:
            await RisingEdge(dut.sys_clk)
            await ReadWrite()
            dut.uart_rx.value = int(dut.uart_tx.value)

    cocotb.start_soon(loopback())

    # Give the loopback coroutine a cycle to establish the idle-line value
    # before queuing the byte.
    await RisingEdge(dut.sys_clk)

    # Start watching for RS232PHYRX's completion pulse *before* queuing the
    # send -- see the timing note above for why this must run concurrently
    # with, rather than after, the TX handshake.
    rx_done   = Event()
    rx_result = {}

    async def capture_rx():
        while True:
            await RisingEdge(dut.sys_clk)
            await ReadOnly()
            if dut.uart_rx_valid.value == 1:
                rx_result["data"] = int(dut.uart_rx_data.value)
                rx_done.set()
                return

    cocotb.start_soon(capture_rx())

    byte = random.randint(0, 255)

    # Queue one byte on the TX stream handshake: hold valid until ready.
    dut.uart_tx_data.value  = byte
    dut.uart_tx_valid.value = 1
    while True:
        await RisingEdge(dut.sys_clk)
        await ReadOnly()
        if dut.uart_tx_ready.value == 1:
            break
    await RisingEdge(dut.sys_clk)
    dut.uart_tx_valid.value = 0
    dut.uart_tx_data.value  = 0

    # A full byte takes 10 bit periods (start + 8 data + stop) at
    # UART_BAUDRATE, each bit period lasting sys_clk_freq/baudrate cycles;
    # bound the wait generously so a real protocol bug fails fast instead of
    # hanging the test.
    max_cycles = 20 * (int(1 / (SYS_CLK_PERIOD_NS * 1e-9)) // UART_BAUDRATE) * 10
    cycles = 0
    while not rx_done.is_set():
        await RisingEdge(dut.sys_clk)
        cycles += 1
        assert cycles < max_cycles, \
            "UART loopback: timed out waiting for uart_rx_valid"

    received = rx_result["data"]
    assert received == byte, \
        f"UART loopback: sent {byte:#x}, got {received:#x}"
