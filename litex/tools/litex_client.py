#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2016 Tim 'mithro' Ansell <mithro@mithis.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import time
import threading
import argparse
import socket

from litex.tools.remote.etherbone import EtherbonePacket, EtherboneRecord
from litex.tools.remote.etherbone import EtherboneReads, EtherboneWrites
from litex.tools.remote.etherbone import EtherboneIPC
from litex.tools.remote.csr_builder import CSRBuilder

# Remote Client ------------------------------------------------------------------------------------

class RemoteClient(EtherboneIPC, CSRBuilder):
    def __init__(self, host="localhost", port=1234, base_address=0, csr_csv=None, csr_data_width=None, debug=False):
        # If csr_csv set to None and local csr.csv file exists, use it.
        if csr_csv is None and os.path.exists("csr.csv"):
            csr_csv = "csr.csv"
        # If valid csr_csv file found, build the CSRs.
        if csr_csv is not None:
            CSRBuilder.__init__(self, self, csr_csv, csr_data_width)
        # Else if csr_data_width set to None, force to csr_data_width 32-bit.
        elif csr_data_width is None:
            csr_data_width = 32
        self.host         = host
        self.port         = port
        self.debug        = debug
        self.base_address = base_address if base_address is not None else 0

    def open(self):
        if hasattr(self, "socket"):
            return
        self.socket = socket.create_connection((self.host, self.port), 5.0)
        self.socket.settimeout(5.0)

    def close(self):
        if not hasattr(self, "socket"):
            return
        self.socket.close()
        del self.socket

    def read(self, addr, length=None, burst="incr"):
        length_int = 1 if length is None else length
        # Prepare packet
        record = EtherboneRecord()
        incr = (burst == "incr")
        record.reads  = EtherboneReads(addrs=[self.base_address + addr + 4*incr*j for j in range(length_int)])
        record.rcount = len(record.reads)

        # Send packet
        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.send_packet(self.socket, packet)

        # Receive response
        packet = EtherbonePacket(self.receive_packet(self.socket))
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, data in enumerate(datas):
                print("read 0x{:08x} @ 0x{:08x}".format(data, self.base_address + addr + 4*i))
        return datas[0] if length is None else datas

    def write(self, addr, datas):
        datas = datas if isinstance(datas, list) else [datas]
        record = EtherboneRecord()
        record.writes = EtherboneWrites(base_addr=self.base_address + addr, datas=[d for d in datas])
        record.wcount = len(record.writes)

        packet = EtherbonePacket()
        packet.records = [record]
        packet.encode()
        self.send_packet(self.socket, packet)

        if self.debug:
            for i, data in enumerate(datas):
                print("write 0x{:08x} @ 0x{:08x}".format(data, self.base_address + addr + 4*i))

# Utils --------------------------------------------------------------------------------------------

def reg2addr(csr_csv, reg):
    bus = RemoteClient(csr_csv=csr_csv)
    if hasattr(bus.regs, reg):
        return getattr(bus.regs, reg).addr
    else:
        raise ValueError(f"Register {reg} not present, exiting.")

def dump_identifier(csr_csv, port):
    bus = RemoteClient(csr_csv=csr_csv, port=port)
    bus.open()

    # On PCIe designs, CSR is remapped to 0 to limit BAR0 size.
    if hasattr(bus.bases, "pcie_phy"):
        bus.base_address = -bus.mems.csr.base

    fpga_identifier = ""

    for i in range(256):
        c = chr(bus.read(bus.bases.identifier_mem + 4*i) & 0xff)
        fpga_identifier += c
        if c == "\0":
            break

    print(fpga_identifier)

    bus.close()

def dump_registers(csr_csv, port, filter=None):
    bus = RemoteClient(csr_csv=csr_csv, port=port)
    bus.open()

    # On PCIe designs, CSR is remapped to 0 to limit BAR0 size.
    if hasattr(bus.bases, "pcie_phy"):
        bus.base_address = -bus.mems.csr.base

    for name, register in bus.regs.__dict__.items():
        if (filter is None) or filter in name:
            print("0x{:08x} : 0x{:08x} {}".format(register.addr, register.read(), name))

    bus.close()

def read_memory(csr_csv, port, addr, length):
    bus = RemoteClient(csr_csv=csr_csv, port=port)
    bus.open()

    for offset in range(length//4):
        print(f"0x{addr + 4*offset:08x} : 0x{bus.read(addr + 4*offset):08x}")

    bus.close()

def write_memory(csr_csv, port, addr, data):
    bus = RemoteClient(csr_csv=csr_csv, port=port)
    bus.open()

    bus.write(addr, data)

    bus.close()

# Gui ----------------------------------------------------------------------------------------------

def run_gui(csr_csv, port):
    import dearpygui.dearpygui as dpg

    bus = RemoteClient(csr_csv=csr_csv, port=port)
    bus.open()

    def reboot_callback():
        bus.regs.ctrl_reset.write(1)
        bus.regs.ctrl_reset.write(0)

    dpg.create_context()
    dpg.create_viewport(title="LiteX CLI GUI", max_width=800, always_on_top=True)
    dpg.setup_dearpygui()

    with dpg.window(autosize=True):
        dpg.add_text("Control/Status")
        dpg.add_button(label="Reboot", callback=reboot_callback)
        def filter_callback(sender, filter_str):
            dpg.set_value("csr_filter", filter_str)
        dpg.add_input_text(label="CSR Filter (inc, -exc)", callback=filter_callback)
        dpg.add_text("CSR Registers:")
        with dpg.filter_set(id="csr_filter"):
            def reg_callback(tag, data):
                for name, reg in  bus.regs.__dict__.items():
                    if (tag == name):
                        try:
                            reg.write(int(data, 0))
                        except:
                            pass
            for name, reg in bus.regs.__dict__.items():
                dpg.add_input_text(
                    indent     = 16,
                    label      = f"0x{reg.addr:08x} - {name}",
                    tag        = name,
                    filter_key =name,
                    callback   = reg_callback,
                    on_enter   = True,
                    width      = 200
                )

    def timer_callback(refresh=1e-1):
        while True:
            for name, reg in bus.regs.__dict__.items():
                value = reg.read()
                dpg.set_value(item=name, value=f"0x{reg.read():x}")
            time.sleep(refresh)

    timer_thread = threading.Thread(target=timer_callback)
    timer_thread.start()

    dpg.show_viewport()
    dpg.start_dearpygui()
    dpg.destroy_context()

    bus.close()

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX Client utility.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--csr-csv", default="csr.csv",     help="CSR configuration file")
    parser.add_argument("--port",    default="1234",        help="Host bind port.")
    parser.add_argument("--ident",   action="store_true",   help="Dump SoC identifier.")
    parser.add_argument("--regs",    action="store_true",   help="Dump SoC registers.")
    parser.add_argument("--filter",  default=None,          help="Registers filter (to be used with --regs).")
    parser.add_argument("--read",    default=None,          help="Do a MMAP Read to SoC bus (--read addr/reg).")
    parser.add_argument("--write",   default=None, nargs=2, help="Do a MMAP Write to SoC bus (--write addr/reg data).")
    parser.add_argument("--length",  default="4",           help="MMAP access length.")
    parser.add_argument("--gui",     action="store_true",   help="Run Gui.")
    args = parser.parse_args()

    csr_csv = args.csr_csv
    port    = int(args.port, 0)

    if args.ident:
        dump_identifier(csr_csv=csr_csv, port=port)

    if args.regs:
        dump_registers(csr_csv=csr_csv, port=port, filter=args.filter)

    if args.read:
        try:
           addr = int(args.read, 0)
        except ValueError:
            addr = reg2addr(csr_csv, args.read)
        read_memory(csr_csv=csr_csv, port=port, addr=addr, length=int(args.length, 0))

    if args.write:
        try:
           addr = int(args.write[0], 0)
        except ValueError:
            addr = reg2addr(csr_csv, args.write[0])
        write_memory(csr_csv=csr_csv, port=port, addr=addr, data=int(args.write[1], 0))

    if args.gui:
        run_gui(csr_csv=csr_csv, port=port)

if __name__ == "__main__":
    main()
