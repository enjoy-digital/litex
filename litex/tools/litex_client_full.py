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
    def __init__(self, host="localhost", port=1234, base_address=0, csr_csv=None, csr_data_width=None,
        csr_bus_address_width=None, debug=False):
        # If csr_csv set to None and local csr.csv file exists, use it.
        if csr_csv is None and os.path.exists("csr.csv"):
            csr_csv = "csr.csv"
        # If valid csr_csv file found, build the CSRs.
        if csr_csv is not None:
            CSRBuilder.__init__(self, self, csr_csv, csr_data_width)
        else:
            # Else if csr_data_width set to None, force to csr_data_width 32-bit.
            if csr_data_width is None:
                self.csr_data_width = 32
            # Else if csr_bus_address_width set to None, force to csr_bus_address_width 32-bit.
            if csr_bus_address_width is None:
                self.csr_bus_address_width = 32
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
        self.socket = socket.create_connection((self.host, self.port))
        self.socket.settimeout(2.0)
        self._receive_server_info()
        self.binded = True

    def close(self):
        if not self.binded:
            return
        self.socket.close()
        del self.socket
        self.binded = False

    def clear_socket_buffer(self):
        try:
            while True:
                data = self.socket.recv(4096)
                if not data:
                    break
        except (TimeoutError, socket.error):
            pass

    def read(self, addr, length=None, burst="incr"):
        length_int = 1 if length is None else length
        addr_size  = self.csr_bus_address_width // 8
        # Prepare packet
        record = EtherboneRecord(addr_size)
        incr = (burst == "incr")
        record.reads  = EtherboneReads(
            addr_size = addr_size,
            addrs     = [self.base_address + addr + 4*incr*j for j in range(length_int)]
        )
        record.rcount = len(record.reads)

        # Send packet
        packet = EtherbonePacket(self.csr_bus_address_width)
        packet.records = [record]
        packet.encode()
        self.send_packet(self.socket, packet)

        # Receive response
        response = self.receive_packet(self.socket, addr_size)
        if response == 0:
            # Handle error by returning default values
            if self.debug:
                print("Timeout occurred during read. Returning default values.")
            self.clear_socket_buffer()
            return 0 if length is None else [0] * length_int

        packet = EtherbonePacket(
            addr_width = self.csr_bus_address_width,
            init       = response
        )
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, data in enumerate(datas):
                print("read 0x{:08x} @ 0x{:08x}".format(data, self.base_address + addr + 4*i))
        return datas[0] if length is None else datas

    def write(self, addr, datas):
        datas = datas if isinstance(datas, list) else [datas]
        addr_size = self.csr_bus_address_width // 8
        record = EtherboneRecord(addr_size)
        record.writes = EtherboneWrites(
            base_addr = self.base_address + addr,
            addr_size = addr_size,
            datas     = [d for d in datas]
        )
        record.wcount = len(record.writes)

        packet = EtherbonePacket(self.csr_bus_address_width)
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
                True  : f"0b{register.read():032b}",
                False : f"0x{register.read():08x}",
            }[binary]
            print("0x{:08x} : {} {}".format(register.addr, register_value, name))

    bus.close()

def read_memory(host, csr_csv, port, addr, length, binary=False):
    bus = RemoteClient(host=host, csr_csv=csr_csv, port=port)
    bus.open()

    for offset in range(length//4):
        register_value = {
            True  : f"0b{bus.read(addr + 4*offset):032b}",
            False : f"0x{bus.read(addr + 4*offset):08x}",
        }[binary]
        print(f"0x{addr + 4*offset:08x} : {register_value}")

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
            reg &= ~(1 << led)
            reg |= ((val & 0b1) << led)
            bus.regs.leds_out.write(reg)

    if with_buttons:
        def get_buttons(button):
            reg = bus.regs.buttons_in.read()
            return (reg >> button) & 0b1

    if with_xadc:
        def get_xadc_temp():
            return bus.regs.xadc_temperature.read() * 503.975 / 4096 - 273.15

        def get_xadc_vccint():
            return bus.regs.xadc_vccint.read() * 3 / 4096

        def get_xadc_vccaux():
            return bus.regs.xadc_vccaux.read() * 3 / 4096

        def get_xadc_vccbram():
            return bus.regs.xadc_vccbram.read() * 3 / 4096

        def gen_xadc_data(get_cls, n):
            xadc_data = [get_cls()] * n
            while True:
                xadc_data.pop(-1)
                xadc_data.insert(0, get_cls())
                yield xadc_data

    #--------------------------------------------------------------------------
    # Memory Editor Panel
    #--------------------------------------------------------------------------
    # We'll store memory data in a structure so we can refresh easily.
    # For convenience, we'll show 16 bytes per row in the UI.
    #--------------------------------------------------------------------------

    # Internal state for Memory Editor.
    MEM_TABLE_TAG       = "mem_table"
    MEM_EDITOR_WINDOW   = "Memory Editor"
    MEM_BASE_TAG        = "mem_base_addr"
    MEM_LENGTH_TAG      = "mem_length"
    MEM_AUTO_REFRESH_TAG= "mem_auto_refresh"
    MEM_REFRESH_RATE_TAG= "mem_refresh_rate"

    # We'll store the last-read memory as a list of bytes.
    memory_data = []

    def read_memory_chunk(base, length):
        """Reads `length` bytes from `base` address (word-aligned)."""
        # This function does the tricky part:
        #  - The bus.read() is word-based (32 bits). We'll read in multiples of 4 bytes
        #  - Then break them down into single bytes for display
        #  - If length not a multiple of 4, we handle leftover bytes carefully
        if length <= 0:
            return []

        # Round up the length to a multiple of 4
        # so we read whole words from the device.
        aligned_len = (length + 3) & ~3
        words       = bus.read(base, aligned_len // 4, burst="incr")
        out         = []

        for word_idx, w in enumerate(words):
            # Break word into 4 bytes in little-endian.
            for byte_idx in range(4):
                byte_val = (w >> (8 * byte_idx)) & 0xff
                out.append(byte_val)

        # Truncate if we over-read.
        out = out[:length]
        return out

    def write_memory_byte(addr, val):
        """Writes a single byte `val` at memory address `addr`."""
        # Because our bus is word-based, we need to do a read-modify-write of the word
        # that contains this byte.
        aligned_addr = addr & ~3
        word_offset  = addr &  3

        current_word = bus.read(aligned_addr)  # single word read
        # Clear out the previous byte in that position, then set it
        mask = 0xFF << (8 * word_offset)
        new_word = (current_word & ~mask) | ((val & 0xFF) << (8 * word_offset))
        bus.write(aligned_addr, new_word)

    def _printable_chr(bval):
        # Returns a printable ASCII char or '.' if not printable.
        c = chr(bval)
        if (bval < 32) or (bval > 126):
            c = '.'
        return c

    def update_memory_view():
        """Updates the internal memory_data and the DPG table from base/length fields."""
        nonlocal memory_data

        base = int(dpg.get_value(MEM_BASE_TAG), 0)
        length = int(dpg.get_value(MEM_LENGTH_TAG), 0)

        # Debug: Print base and length
        print(f"Reading memory from base: 0x{base:08X}, length: {length} bytes")

        memory_data = read_memory_chunk(base, length)

        # Debug: Print memory data
        print(f"Memory data: {memory_data}")

        BYTES_PER_LINE = 16
        row_count = len(memory_data) // BYTES_PER_LINE

        # Ensure the table has enough rows
        current_row_count = dpg.get_item_children(MEM_TABLE_TAG, slot=1)  # Get current row count
        if len(current_row_count) < row_count:
            # Add missing rows
            for _ in range(row_count - len(current_row_count)):
                with dpg.table_row(parent=MEM_TABLE_TAG):
                    dpg.add_text("")  # Address column
                    for _ in range(16):  # Hex columns
                        dpg.add_text("")  # Hex data
                    dpg.add_text("")  # ASCII representation

        # Update existing rows
        for row_start in range(0, len(memory_data), BYTES_PER_LINE):
            row_data = memory_data[row_start:row_start + BYTES_PER_LINE]
            row_index = row_start // BYTES_PER_LINE

            # Debug: Print row data
            print(f"Row data: {row_data}")

            # Get the row's children (cells)
            row_id = dpg.get_item_children(MEM_TABLE_TAG, slot=1)[row_index]
            cells = dpg.get_item_children(row_id, slot=1)

            # Update Address column
            dpg.set_value(cells[0], f"0x{base + row_start:08X}")

            # Update Hex columns
            hex_values = []
            for i in range(16):
                if i < len(row_data):
                    hex_values.append(f"{row_data[i]:02X}")
                else:
                    hex_values.append("  ")
            dpg.set_value(cells[1], " ".join(hex_values))

            # Update ASCII representation
            ascii_values = []
            for i in range(16):
                if i < len(row_data):
                    ascii_values.append(_printable_chr(row_data[i]))
                else:
                    ascii_values.append(" ")
            dpg.set_value(cells[2], "".join(ascii_values))

    # Create Main Window.
    dpg.create_context()
    dpg.create_viewport(title="LiteX CLI GUI", width=1920, height=1080, always_on_top=True)
    dpg.setup_dearpygui()

    # Create a new Memory Editor window.
    with dpg.window(
        label=MEM_EDITOR_WINDOW,
        width=800,
        height=400,
        pos=(550, 500),
    ):
        # 32-bit Access Section
        dpg.add_text("Mem Read (32-bit)")
        with dpg.group(horizontal=True):
            # Read 32-bit value
            dpg.add_input_text(
                label="Read Address",
                tag="read_addr",
                default_value="0x00000000",
                width=120
            )
            dpg.add_button(
                label="Read 32-bit",
                callback=lambda: dpg.set_value("read_value", f"0x{bus.read(int(dpg.get_value('read_addr'), 0)):08X}")
            )
            dpg.add_text("Value:")
            dpg.add_input_text(
                tag="read_value",
                default_value="0x00000000",
                width=120,
                readonly=True
            )
        dpg.add_text("Mem Write (32-bit)")
        with dpg.group(horizontal=True):
            # Write 32-bit value
            dpg.add_input_text(
                label="Write Address",
                tag="write_addr",
                default_value="0x00000000",
                width=120
            )
            dpg.add_input_text(
                label="Write Value",
                tag="write_value",
                default_value="0x00000000",
                width=120
            )
            dpg.add_button(
                label="Write 32-bit",
                callback=lambda: bus.write(int(dpg.get_value("write_addr"), 0), int(dpg.get_value("write_value"), 0))
            )

        # Dump Section
        dpg.add_text("Mem Dump")
        with dpg.group(horizontal=True):
            # Base address
            dpg.add_input_text(
                label="Base Address",
                tag=MEM_BASE_TAG,
                default_value="0x40000000",  # Adjust as you see fit
                width=120
            )

            # Length
            dpg.add_input_text(
                label="Length (bytes)",
                tag=MEM_LENGTH_TAG,
                default_value="256",
                width=120
            )

            # Refresh controls
            dpg.add_button(label="Read", callback=lambda: update_memory_view())
            dpg.add_checkbox(
                label="Auto Refresh",
                tag=MEM_AUTO_REFRESH_TAG,
                default_value=False
            )
            dpg.add_input_text(
                label="Refresh Rate (s)",
                tag=MEM_REFRESH_RATE_TAG,
                default_value="1.0",
                width=60
            )

        # Table for memory display
        with dpg.table(
            tag=MEM_TABLE_TAG,
            header_row=True,
            resizable=True,
            policy=dpg.mvTable_SizingStretchProp,
            scrollX=True,
            scrollY=True,
            row_background=True,
            width=-1,  # Use full width of the window
            height=-1,  # Use full heigth of the window
        ):
            # Table columns:
            # 1) Address
            # 2) Hex Data (16 bytes)
            # 3) ASCII Representation
            dpg.add_table_column(label="Address")
            dpg.add_table_column(label="Hex Data")
            dpg.add_table_column(label="ASCII")

    #--------------------------------------------------------------------------
    # Existing Windows (CSR, Peripherals, XADC...) from your script
    #--------------------------------------------------------------------------


    # Create CSR Window.
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
    with dpg.window(label="FPGA Peripherals", autosize=True, pos=(0, 400)):
        dpg.add_text("SoC")
        dpg.add_button(label="Reboot", callback=reboot)
        if with_identifier:
            dpg.add_text(f"Identifier: {get_identifier()}")
        if with_leds:
           dpg.add_text("Leds")
           with dpg.group(horizontal=True):
                def led_callback(sender):
                    for i in range(8):  # Or real number of LEDs
                        if sender == f"led{i}":
                            val = get_leds(i)
                            set_leds(i, ~val)
                for i in range(8):
                   dpg.add_checkbox(id=f"led{i}", callback=led_callback)
        if with_buttons:
            dpg.add_text("Buttons")
            with dpg.group(horizontal=True):
                for i in range(8):
                    dpg.add_checkbox(id=f"btn{i}")

    # Create XADC Window.
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
                        dpg.add_line_series([], [], label="vccaux", tag="vccaux")
                    dpg.set_axis_limits("vccaux_y", 0, 2.5)
                # VCCBRAM.
                with dpg.plot(label=f"VCCBRAM (V)"):
                    dpg.add_plot_axis(dpg.mvXAxis,  tag="vccbram_x")
                    with dpg.plot_axis(dpg.mvYAxis, tag="vccbram_y"):
                        dpg.add_line_series([], [], label="vccbram", tag="vccbram")
                    dpg.set_axis_limits("vccbram_y", 0, 1.8)

    #--------------------------------------------------------------------------
    # Timer Thread (for auto-update of CSR, XADC, Memory Editor, etc.)
    #--------------------------------------------------------------------------
    def timer_callback(refresh=0.1, xadc_points=100):
        if with_xadc:
            temp    = gen_xadc_data(get_xadc_temp,    n=xadc_points)
            vccint  = gen_xadc_data(get_xadc_vccint,  n=xadc_points)
            vccaux  = gen_xadc_data(get_xadc_vccaux,  n=xadc_points)
            vccbram = gen_xadc_data(get_xadc_vccbram, n=xadc_points)

        while dpg.is_dearpygui_running():
            # CSR Update.
            for name, reg in bus.regs.__dict__.items():
                value = reg.read()
                dpg.set_value(item=name, value=f"0x{value:x}")

            # XADC Update.
            if with_xadc:
                for name, gen in [
                    ("temp",     temp),
                    ("vccint",   vccint),
                    ("vccbram",  vccbram),
                    ("vccaux",   vccaux),
                ]:
                    datay = next(gen)
                    datax = list(range(len(datay)))
                    dpg.set_value(name, [datax, datay])
                    dpg.set_item_label(name, name)
                    dpg.set_axis_limits_auto(f"{name}_x")
                    dpg.fit_axis_data(f"{name}_x")

            # Peripherals (LEDs / Buttons).
            if with_leds:
                for i in range(8):
                    dpg.set_value(f"led{i}", bool(get_leds(i)))
            if with_buttons:
                for i in range(8):
                    dpg.set_value(f"btn{i}", bool(get_buttons(i)))

            # Memory Editor Auto Refresh
            if dpg.get_value(MEM_AUTO_REFRESH_TAG):
                try:
                    period = float(dpg.get_value(MEM_REFRESH_RATE_TAG))
                except:
                    period = 1.0
                update_memory_view()
                time.sleep(period)
            else:
                time.sleep(refresh)

    timer_thread = threading.Thread(target=timer_callback, daemon=True)
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
            binary  = args.binary,
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