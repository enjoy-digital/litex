#!/usr/bin/env python3

import sys
import os
import time
import threading
import argparse
import socket
import struct
from litex.soc.tools.remote import RemoteClient

class ConnectionClosed(Exception):
    pass

# struct vexriscv_req {
#	uint8_t readwrite;
#	uint8_t size;
#	uint32_t address;
#	uint32_t data;
#} __attribute__((packed));
class VexRiscvDebugPacket():
    def __init__(self, data):
        self.is_write, self.size, self.address, self.value = struct.unpack("=?BII", data)

class VexRiscvDebugBridge():
    def __init__(self):
        self._get_args()

    def open(self):
        if not hasattr(self, "debugger_socket"):
            self.debugger_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.debugger_socket.bind(('',7893))
            self.debugger_socket.listen(0)

        if not hasattr(self, "rc"):
            self.rc = RemoteClient(csr_csv=self.args.csr)
            self.rc.open()
            self.core_addr = self.rc.regs.cpu_or_bridge_debug_core.addr
            self.data_addr = self.rc.regs.cpu_or_bridge_debug_data.addr
            self.refresh_addr = self.rc.regs.cpu_or_bridge_debug_refresh.addr

    def _get_args(self):
        parser = argparse.ArgumentParser()
        parser.add_argument("--csr", default="test/csr.csv", help="csr mapping file")
        self.args = parser.parse_args()

    def temperature(self):
        return self.rc.read(self.rc.regs.xadc_temperature.addr) * 503.975 / 4096 - 273.15

    def accept(self):
        if hasattr(self, "debugger"):
            return
        print("Waiting for connection from debugger...")
        self.debugger, address = self.debugger_socket.accept()
        print("Accepted debugger connection from {}".format(address[0]))

    def _refresh_reg(self, reg):
        self.rc.write(self.refresh_addr, reg)

    def read_core(self):
        self._refresh_reg(0)
        self.write_to_debugger(self.rc.read(self.core_addr))

    def read_data(self):
        self._refresh_reg(4)
        self.write_to_debugger(self.rc.read(self.data_addr))

    def write_core(self, value):
        self.rc.write(self.core_addr, value)

    def write_data(self, value):
        self.rc.write(self.data_addr, value)

    def read_from_debugger(self):
        data = self.debugger.recv(10)
        if len(data) != 10:
            self.debugger.close()
            del self.debugger
            raise ConnectionClosed()
        return VexRiscvDebugPacket(data)

    def write_to_debugger(self, data):
        self.debugger.send(struct.pack("=I", data))

def main():
    vrvb = VexRiscvDebugBridge()
    vrvb.open()
    print("FPGA Temperature: {} C".format(vrvb.temperature()))

    while True:
        vrvb.accept()
        try:
            pkt = vrvb.read_from_debugger()
            if pkt.is_write == True:
                if pkt.address == 0xf00f0000:
                    vrvb.write_core(pkt.value)
                elif pkt.address == 0xf00f0004:
                    vrvb.write_data(pkt.value)
                else:
                    raise "Unrecognized address"
            else:
                if pkt.address == 0xf00f0000:
                    vrvb.read_core()
                elif pkt.address == 0xf00f0004:
                    vrvb.read_data()
                else:
                    raise "Unrecognized address"
        except ConnectionClosed:
            print("Debugger connection closed")

if __name__ == "__main__":
    main()
