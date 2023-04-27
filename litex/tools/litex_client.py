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
        self.binded       = False
        self.base_address = base_address if base_address is not None else 0

    def _receive_server_info(self):
        info = str(self.socket.recv(128))

        # With LitePCIe, CSRs are translated to 0 to limit BAR0 size, so also translate base address.
        if "CommPCIe" in info:
            self.base_address = -self.mems.csr.base

    def open(self):
        if self.binded:
            return
        self.socket = socket.create_connection((self.host, self.port), 5.0)
        self.socket.settimeout(5.0)
        self._receive_server_info()
        self.binded = True

    def close(self):
        if not self.binded:
            return
        self.socket.close()
        del self.socket
        self.binded = False

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

def reg2addr(host, csr_csv, reg):
    bus = RemoteClient(host=host, csr_csv=csr_csv)
    if hasattr(bus.regs, reg):
        return getattr(bus.regs, reg).addr
    else:
        raise ValueError(f"Register {reg} not present, exiting.")

def dump_identifier(host, csr_csv, port):
    bus = RemoteClient(host=host, csr_csv=csr_csv, port=port)
    bus.open()

    fpga_identifier = ""

    for i in range(256):
        c = chr(bus.read(bus.bases.identifier_mem + 4*i) & 0xff)
        fpga_identifier += c
        if c == "\0":
            break

    print(fpga_identifier)

    bus.close()

def dump_registers(host, csr_csv, port, filter=None, binary=False):
    bus = RemoteClient(host=host, csr_csv=csr_csv, port=port)
    bus.open()

    for name, register in bus.regs.__dict__.items():
        if (filter is None) or filter in name:
            register_value = {
                True  : f"{register.read():032b}",
                False : f"{register.read():08x}",
            }[binary]
            print("0x{:08x} : 0x{} {}".format(register.addr, register_value, name))

    bus.close()

def read_memory(host, csr_csv, port, addr, length):
    bus = RemoteClient(host=host, csr_csv=csr_csv, port=port)
    bus.open()

    for offset in range(length//4):
        print(f"0x{addr + 4*offset:08x} : 0x{bus.read(addr + 4*offset):08x}")

    bus.close()

def write_memory(host, csr_csv, port, addr, data):
    bus = RemoteClient(host=host, csr_csv=csr_csv, port=port)
    bus.open()

    bus.write(addr, data)

    bus.close()

# Gui ----------------------------------------------------------------------------------------------

def run_gui(host, csr_csv, port):
    import dearpygui.dearpygui as dpg

    bus = RemoteClient(host, csr_csv=csr_csv, port=port)
    bus.open()

    # Board capabilities.
    # -------------------
    with_identifier = hasattr(bus.bases, "identifier_mem")
    with_leds       = hasattr(bus.regs, "leds_out")
    with_buttons    = hasattr(bus.regs, "buttons_in")
    with_xadc       = hasattr(bus.regs, "xadc_temperature")

    # Board functions.
    # ----------------
    def reboot():
        bus.regs.ctrl_reset.write(1)
        bus.regs.ctrl_reset.write(0)

    if with_identifier:
        def get_identifier():
            identifier = ""
            for i in range(256):
                c = chr(bus.read(bus.bases.identifier_mem + 4*i) & 0xff)
                identifier += c
                if c == "\0":
                    break
            return identifier

    if with_leds:
        def get_leds(led):
            reg = bus.regs.leds_out.read()
            return (reg >> led) & 0b1

        def set_leds(led, val):
            reg = bus.regs.leds_out.read()
            reg &= ~(1<<led)
            reg |= (val & 0b1)<<led
            bus.regs.leds_out.write(reg)

    if with_buttons:
        def get_buttons(button):
            reg = bus.regs.buttons_in.read()
            return (reg >> button) & 0b1

    if with_xadc:
        def get_xadc_temp():
            return bus.regs.xadc_temperature.read()*503.975/4096 - 273.15

        def get_xadc_vccint():
            return bus.regs.xadc_vccint.read()*3/4096

        def get_xadc_vccaux():
            return bus.regs.xadc_vccaux.read()*3/4096

        def get_xadc_vccbram():
            return bus.regs.xadc_vccbram.read()*3/4096

        def gen_xadc_data(get_cls, n):
            xadc_data = [get_cls()]*n
            while True:
                xadc_data.pop(-1)
                xadc_data.insert(0, get_cls())
                yield xadc_data

    # Create Main Window.
    # -------------------
    dpg.create_context()
    dpg.create_viewport(title="LiteX CLI GUI", width=1920, height=1080, always_on_top=True)
    dpg.setup_dearpygui()

    # Create CSR Window.
    # ------------------
    with dpg.window(label="FPGA CSR Registers", autosize=True):
        dpg.add_text("Control/Status")
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
                    filter_key = name,
                    callback   = reg_callback,
                    on_enter   = True,
                    width      = 200
                )

    # Create Peripheral Window.
    # -------------------------
    with dpg.window(label="FPGA Peripherals", autosize=True, pos=(550, 0)):
        dpg.add_text("SoC")
        dpg.add_button(label="Reboot", callback=reboot)
        if with_identifier:
            dpg.add_text(f"Identifier: {get_identifier()}")
        if with_leds:
           dpg.add_text("Leds")
           with dpg.group(horizontal=True):
                def led_callback(sender):
                    for i in range(8): # FIXME: Get num.
                        if sender == f"led{i}":
                            val = get_leds(i)
                            set_leds(i, ~val)
                for i in range(8): # FIXME: Get num.
                   dpg.add_checkbox(id=f"led{i}", callback=led_callback)
        if with_buttons:
            dpg.add_text("Buttons")
            with dpg.group(horizontal=True):
                for i in range(8): # FIXME: Get num.
                    dpg.add_checkbox(id=f"btn{i}")

    # Create XADC Window.
    # -------------------
    if with_xadc:
        with dpg.window(label="FPGA XADC", width=600, height=600, pos=(950, 0)):
            with dpg.subplots(2, 2, label="", width=-1, height=-1) as subplot_id:
                # Temperature.
                with dpg.plot(label=f"Temperature (°C)"):
                    dpg.add_plot_axis(dpg.mvXAxis,  tag="temp_x")
                    with dpg.plot_axis(dpg.mvYAxis, tag="temp_y"):
                        dpg.add_line_series([], [], label="temp", tag="temp")
                    dpg.set_axis_limits("temp_y", 0, 100)
                # VCCInt.
                with dpg.plot(label=f"VCCInt (V)"):
                    dpg.add_plot_axis(dpg.mvXAxis,  tag="vccint_x")
                    with dpg.plot_axis(dpg.mvYAxis, tag="vccint_y"):
                        dpg.add_line_series([], [], label="vccint", tag="vccint")
                    dpg.set_axis_limits("vccint_y", 0, 1.8)
                # VCCAux.
                with dpg.plot(label=f"VCCAux (V)"):
                    dpg.add_plot_axis(dpg.mvXAxis,  tag="vccaux_x")
                    with dpg.plot_axis(dpg.mvYAxis, tag="vccaux_y"):
                        dpg.add_line_series([], [], label="vcaux", tag="vccaux")
                    dpg.set_axis_limits("vccaux_y", 0, 2.5)
                # VCCBRAM.
                with dpg.plot(label=f"VCCBRAM (V)"):
                    dpg.add_plot_axis(dpg.mvXAxis,  tag="vccbram_x")
                    with dpg.plot_axis(dpg.mvYAxis, tag="vccbram_y"):
                        dpg.add_line_series([], [], label="vccbram", tag="vccbram")
                    dpg.set_axis_limits("vccbram_y", 0, 1.8)

    def timer_callback(refresh=1e-1, xadc_points=100):
        if with_xadc:
            temp    = gen_xadc_data(get_xadc_temp,    n=xadc_points)
            vccint  = gen_xadc_data(get_xadc_vccint,  n=xadc_points)
            vccaux  = gen_xadc_data(get_xadc_vccaux,  n=xadc_points)
            vccbram = gen_xadc_data(get_xadc_vccbram, n=xadc_points)

        while dpg.is_dearpygui_running():
            # CSR Update.
            for name, reg in bus.regs.__dict__.items():
                value = reg.read()
                dpg.set_value(item=name, value=f"0x{reg.read():x}")

            # XADC Update.
            if with_xadc:
                for name, gen in [
                    ("temp",      temp),
                    ("vccint",   vccint),
                    ("vccbram", vccbram),
                    ("vccaux",   vccaux),
                    ("vccint",   vccint),
                ]:
                    datay = next(gen)
                    datax = list(range(len(datay)))
                    dpg.set_value(name, [datax, datay])
                    dpg.set_item_label(name, name)
                    dpg.set_axis_limits_auto(f"{name}_x")
                    dpg.fit_axis_data(f"{name}_x")

            # Peripherals.
            if with_leds:
                for i in range(8): # FIXME; Get num.
                    dpg.set_value(f"led{i}", bool(get_leds(i)))

            if with_buttons:
                for i in range(8): # FIXME; Get num.
                    dpg.set_value(f"btn{i}", bool(get_buttons(i)))

            time.sleep(refresh)

    timer_thread = threading.Thread(target=timer_callback)
    timer_thread.start()

    dpg.show_viewport()
    try:
        while dpg.is_dearpygui_running():
            dpg.render_dearpygui_frame()
    except KeyboardInterrupt:
        dpg.destroy_context()

    bus.close()

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="LiteX Client utility.", formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("--csr-csv", default="csr.csv",     help="CSR configuration file")
    parser.add_argument("--host",    default="localhost",   help="Host ip address")
    parser.add_argument("--port",    default="1234",        help="Host bind port.")
    parser.add_argument("--ident",   action="store_true",   help="Dump SoC identifier.")
    parser.add_argument("--regs",    action="store_true",   help="Dump SoC registers.")
    parser.add_argument("--binary",  action="store_true",   help="Use binary format for displayed values.")
    parser.add_argument("--filter",  default=None,          help="Registers filter (to be used with --regs).")
    parser.add_argument("--read",    default=None,          help="Do a MMAP Read to SoC bus (--read addr/reg).")
    parser.add_argument("--write",   default=None, nargs=2, help="Do a MMAP Write to SoC bus (--write addr/reg data).")
    parser.add_argument("--length",  default="4",           help="MMAP access length.")
    parser.add_argument("--gui",     action="store_true",   help="Run Gui.")
    args = parser.parse_args()

    host    = args.host
    csr_csv = args.csr_csv
    port    = int(args.port, 0)

    if args.ident:
        dump_identifier(
            host    = host,
            csr_csv = csr_csv,
            port    = port,
        )

    if args.regs:
        dump_registers(
            host    = args.host,
            csr_csv = csr_csv,
            port    = port,
            filter  = args.filter,
            binary  = args.binary,
        )

    if args.read:
        try:
           addr = int(args.read, 0)
        except ValueError:
            addr = reg2addr(host, csr_csv, args.read)
        read_memory(
            host    = args.host,
            csr_csv = csr_csv,
            port    = port,
            addr    = addr,
            length  = int(args.length, 0),
        )

    if args.write:
        try:
           addr = int(args.write[0], 0)
        except ValueError:
            addr = reg2addr(host, csr_csv, args.write[0])
        write_memory(
            host    = args.host,
            csr_csv = csr_csv,
            port    = port,
            addr    = addr,
            data    = int(args.write[1], 0),
        )

    if args.gui:
        run_gui(
            host    = args.host,
            csr_csv = csr_csv,
            port    = port,
        )

if __name__ == "__main__":
    main()
