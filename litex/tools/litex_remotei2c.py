#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2024 Andrew Dennison <andrew.dennison@motec.com.au>
# SPDX-License-Identifier: BSD-2-Clause
from enum import IntEnum, auto

__all__ = ["RemoteI2C"]


class I2CAddr(IntEnum):
    XFER = 0
    CONFIG = 1


class I2CCmd(IntEnum):
    # bits 0-7 are address or data
    ACK = 8
    READ = auto()
    WRITE = auto()
    START = auto()
    STOP = auto()
    IDLE = auto()


class RemoteI2C:
    def __init__(self, name, bus=None, clk_freq=100e3):
        if bus:
            self.wb = bus
        else:
            from litex import RemoteClient

            self.wb = RemoteClient()
            self.wb.open()

        self.addr_stride = self.wb.constants.config_bus_data_width // 8
        self.name = name
        self.mem_base = getattr(self.wb.mems, name).base
        self.clk_freq = clk_freq

    @property
    def clk_freq(self):
        """I2C clock."""
        config = self._reg_read(I2CAddr.CONFIG)
        clk_freq = self.wb.constants.config_clock_frequency / (2 * config + 1)
        return clk_freq

    @clk_freq.setter
    def clk_freq(self, clk_freq: int | float):
        # config is clk2x prescale+1.
        # NOTE: -1 is omitted below as the integer math gives us the floor
        # so this is implicitly catered for.
        config = int(self.wb.constants.config_clock_frequency // (2 * clk_freq))
        self._reg_write(I2CAddr.CONFIG, config)
        print(f"{self.name}: clk_freq now {self.clk_freq/1000:.0f}kHz")

    def _reg_read(self, reg: I2CAddr) -> int:
        return self.wb.read(self.mem_base + reg * self.addr_stride)

    def _reg_write(self, reg: I2CAddr, data: int) -> None:
        self.wb.write(self.mem_base + reg * self.addr_stride, data)

    def _wait_idle(self) -> int:
        """low-level API: wait for an i2c command to complete: controller idle

        Returns
        -------
        XFER register contents: command flags and data
        """
        timeout = 0
        while not (data := self._reg_read(I2CAddr.XFER)) & (1 << I2CCmd.IDLE):
            assert timeout < 200
        return data

    def cmd_start(self) -> None:
        """low-level API: generate an i2c (re)start condition on the bus"""
        cmd_data = 1 << I2CCmd.START
        self._reg_write(I2CAddr.XFER, cmd_data)
        self._wait_idle()

    def cmd_stop(self) -> None:
        """low-level API: generate an i2c stop condition on the bus"""
        cmd_data = 1 << I2CCmd.STOP
        self._reg_write(I2CAddr.XFER, cmd_data)
        self._wait_idle()

    def cmd_write(self, data) -> bool:
        """low-level API: transmit data (8-bits) on the bus

        Arguments
        -------
        data : int
            8-data to transmit

        Returns
        -------
        bool
            ack bit that was received from the bus
        """
        cmd_data = data + (1 << I2CCmd.WRITE)
        self._reg_write(I2CAddr.XFER, cmd_data)
        cmd_data = self._wait_idle()
        return bool(cmd_data & (1 << I2CCmd.ACK))

    def cmd_read(self, ack: bool = True) -> int:
        """low-level API: receive data (8-bits) from the bus

        Arguments
        -------
        ack : bool, optional
            ack bit to transmit on the bus (default=True)

        Returns
        -------
        int
            data received from the bus
        """
        cmd_data = (1 << I2CCmd.READ) | (int(ack) << I2CCmd.ACK)
        self._reg_write(I2CAddr.XFER, cmd_data)
        cmd_data = self._wait_idle()
        return cmd_data & 0xFF

    def write(self, addr: int, data: bytearray, silent: bool = False, stop: bool = True) -> bool:
        """write bytearray to i2c. Interface matches GreenPakI2cInterface.write()"""
        rd_nwr = 0
        i = 0
        self.cmd_start()
        if not (ack := self.cmd_write((addr << 1) | rd_nwr)):
            if not silent:
                print(f"write: no ack from address {addr}")
        else:
            i = 0
            for byte in data:
                i += 1
                if not (ack := self.cmd_write(byte)):
                    if not silent:
                        print(f"write failed at byte {i}")
                    break
        if stop:
            self.cmd_stop()
        return ack

    def read(self, addr: int, byte_count: int, silent: bool = False, stop: bool = True) -> bytearray | None:
        """read bytearray from i2c. Interface matches GreenPakI2cInterface.read()"""
        rd_nwr = 1
        data = None
        self.cmd_start()
        if not self.cmd_write((addr << 1) | rd_nwr):
            print(f"read: no ack from address {addr}")
        else:
            data = bytearray()
            if byte_count:
                for _ in range(1, byte_count):
                    data.append(self.cmd_read())
                data.append(self.cmd_read(ack=False))
        if stop:
            self.cmd_stop()
        return data

    def scan(self, start: int = 1, stop: int = 0x7F) -> list[int]:
        """Scan the bus for devices.

        Parameters
        ----------
        start : int, optional
            Start address for scan. (default=1)

        stop : int, optional
            Stop address for scan. (default=0x7f)

        Raises
        ------
        None

        Returns
        ------
        list[int]
            A list of addresses where devices were detected
        """
        addresses = []
        for addr in range(start, stop + 1):
            self.cmd_start()
            if self.cmd_write(addr << 1):
                addresses.append(addr)
                print(f"device at {addr:#x}")
        self.cmd_stop()
        return addresses


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--bus", "-b", default="i2c_0", help="i2c bus to scan.")
    args = parser.parse_args()

    i2c = RemoteI2C(args.bus)
    addresses = i2c.scan()
    print(addresses)
