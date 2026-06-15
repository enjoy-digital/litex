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
    max_burst_length = 255

    def __init__(self, host="localhost", port=1234, base_address=0, csr_csv=None, csr_data_width=None,
        csr_bus_address_width=None, debug=False, timeout=2.0, raise_on_timeout=False):
        # If csr_csv set to None and local csr.csv file exists, use it.
        if csr_csv is None and os.path.exists("csr.csv"):
            csr_csv = "csr.csv"
        # If valid csr_csv file found, build the CSRs.
        if csr_csv is not None:
            CSRBuilder.__init__(self, self, csr_csv, csr_data_width, csr_bus_address_width)
        else:
            # Else use provided CSR widths, defaulting to 32-bit.
            self.csr_data_width        = 32 if csr_data_width        is None else csr_data_width
            self.csr_bus_address_width = 32 if csr_bus_address_width is None else csr_bus_address_width
        self.host             = host
        self.port             = port
        self.debug            = debug
        self.timeout          = timeout
        self.binded           = False
        self.base_address     = base_address if base_address is not None else 0
        self.raise_on_timeout = raise_on_timeout

    def _receive_server_info(self):
        info = self.socket.recv(128).decode("utf-8", errors="ignore")

        # With LitePCIe, CSRs are translated to 0 to limit BAR0 size, so also translate base address.
        if "CommPCIe" in info and hasattr(self, "mems") and hasattr(self.mems, "csr"):
            self.base_address = -self.mems.csr.base

    def open(self):
        if self.binded:
            return
        self.socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
        try:
            self.socket.settimeout(self.timeout)
            self._receive_server_info()
            self.binded = True
        except Exception:
            self.socket.close()
            del self.socket
            raise

    def close(self):
        if not self.binded:
            return
        self.socket.close()
        del self.socket
        self.binded = False

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, *args):
        self.close()

    def clear_socket_buffer(self):
        try:
            while True:
                data = self.socket.recv(4096)
                if not data:
                    break
        except (TimeoutError, socket.error):
            pass

    @staticmethod
    def _check_burst(burst):
        if burst not in ["incr", "fixed"]:
            raise ValueError("Unsupported burst mode: {}".format(burst))

    def _read_chunk(self, addr, length, burst):
        addr_size = self.csr_bus_address_width // 8
        incr      = burst == "incr"

        # Prepare packet
        record = EtherboneRecord(addr_size)
        record.reads  = EtherboneReads(
            addr_size = addr_size,
            addrs     = [self.base_address + addr + 4*incr*j for j in range(length)]
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
            if self.debug:
                message = "Timeout occurred during read."
                message += " Raising TimeoutError." if self.raise_on_timeout else " Returning default values."
                print(message)
            self.clear_socket_buffer()
            if self.raise_on_timeout:
                raise TimeoutError("Timeout occurred during read.")
            return [0] * length

        packet = EtherbonePacket(
            addr_width = self.csr_bus_address_width,
            init       = response
        )
        packet.decode()
        datas = packet.records.pop().writes.get_datas()
        if self.debug:
            for i, data in enumerate(datas):
                print("read 0x{:08x} @ 0x{:08x}".format(data, self.base_address + addr + 4*incr*i))
        return datas

    def read(self, addr, length=None, burst="incr"):
        self._check_burst(burst)
        length_int = 1 if length is None else length
        incr       = burst == "incr"
        datas      = []

        for offset in range(0, length_int, self.max_burst_length):
            burst_length = min(length_int - offset, self.max_burst_length)
            burst_addr   = addr + 4*incr*offset
            datas += self._read_chunk(burst_addr, burst_length, burst)
        return datas[0] if length is None else datas

    def _write_chunk(self, addr, datas):
        addr_size = self.csr_bus_address_width // 8
        record = EtherboneRecord(addr_size)
        record.writes = EtherboneWrites(
            base_addr = self.base_address + addr,
            addr_size = addr_size,
            datas     = datas
        )
        record.wcount = len(record.writes)

        packet = EtherbonePacket(self.csr_bus_address_width)
        packet.records = [record]
        packet.encode()
        self.send_packet(self.socket, packet)

    def write(self, addr, datas, burst="incr"):
        self._check_burst(burst)
        datas = datas if isinstance(datas, list) else [datas]
        incr  = burst == "incr"
        step  = self.max_burst_length if incr else 1

        for offset in range(0, len(datas), step):
            burst_datas = datas[offset:offset + step]
            burst_addr  = addr + 4*incr*offset
            self._write_chunk(burst_addr, burst_datas)

        if self.debug:
            for i, data in enumerate(datas):
                print("write 0x{:08x} @ 0x{:08x}".format(data, self.base_address + addr + 4*incr*i))

# Utils --------------------------------------------------------------------------------------------

def reg2addr(host, csr_csv, reg):
    bus = RemoteClient(host=host, csr_csv=csr_csv)
    if hasattr(bus.regs, reg):
        return getattr(bus.regs, reg).addr
    else:
        raise ValueError(f"Register {reg} not present, exiting.")

def dump_identifier(host, csr_csv, port, timeout=2.0, raise_on_timeout=False):
    fpga_identifier = ""

    with RemoteClient(
        host             = host,
        csr_csv          = csr_csv,
        port             = port,
        timeout          = timeout,
        raise_on_timeout = raise_on_timeout,
    ) as bus:
        for i in range(256):
            c = chr(bus.read(bus.bases.identifier_mem + 4*i) & 0xff)
            fpga_identifier += c
            if c == "\0":
                break

    print(fpga_identifier)

def dump_registers(host, csr_csv, port, filter=None, binary=False, timeout=2.0, raise_on_timeout=False):
    with RemoteClient(
        host             = host,
        csr_csv          = csr_csv,
        port             = port,
        timeout          = timeout,
        raise_on_timeout = raise_on_timeout,
    ) as bus:
        for name, register in bus.regs.__dict__.items():
            if (filter is None) or filter in name:
                register_value = {
                    True  : f"0b{register.read():032b}",
                    False : f"0x{register.read():08x}",
                }[binary]
                print("0x{:08x} : {} {}".format(register.addr, register_value, name))

def _word_count(length):
    return (length + 3) // 4

def read_memory(host, csr_csv, port, addr, length, binary=False, file=None, endianness="little", timeout=2.0,
    raise_on_timeout=False):
    word_count = _word_count(length)

    with RemoteClient(
        host             = host,
        csr_csv          = csr_csv,
        port             = port,
        timeout          = timeout,
        raise_on_timeout = raise_on_timeout,
    ) as bus:
        datas = [] if word_count == 0 else bus.read(addr, word_count, burst="incr")

    if file:
        # Read from memory and write to file in binary mode.
        with open(file, "wb") as f:
            data = b"".join([data.to_bytes(4, byteorder=endianness) for data in datas])[:length]
            f.write(data)
    else:
        # Print to console.
        for offset, data in enumerate(datas):
            register_value = {
                True  : f"0b{data:032b}",
                False : f"0x{data:08x}",
            }[binary]
            print(f"0x{addr + 4 * offset:08x} : {register_value}")

def write_memory(host, csr_csv, port, addr, data, file=None, length=None, endianness="little", timeout=2.0,
    raise_on_timeout=False):
    with RemoteClient(
        host             = host,
        csr_csv          = csr_csv,
        port             = port,
        timeout          = timeout,
        raise_on_timeout = raise_on_timeout,
    ) as bus:
        if file:
            # Read from file and write to memory.
            with open(file, "rb") as f:
                if length:
                    data = f.read(length)
                else:
                    data = f.read()

            datas = []
            for i in range(0, len(data), 4):
                chunk = data[i:i + 4]
                chunk += bytes(4 - len(chunk))
                datas.append(int.from_bytes(chunk, byteorder=endianness))

            if datas:
                bus.write(addr, datas, burst="incr")
        else:
            # Write single data value to memory.
            bus.write(addr, data)

# GUI ----------------------------------------------------------------------------------------------

def run_gui(host, csr_csv, port, timeout=2.0, raise_on_timeout=False):
    import dearpygui.dearpygui as dpg

    bus = RemoteClient(
        host,
        csr_csv          = csr_csv,
        port             = port,
        timeout          = timeout,
        raise_on_timeout = raise_on_timeout,
    )
    bus.open()

    # Board capabilities.
    # -------------------
    with_identifier = hasattr(bus.bases, "identifier_mem")
    with_leds       = hasattr(bus.regs, "leds_out")
    with_buttons    = hasattr(bus.regs, "buttons_in")
    with_xadc       = hasattr(bus.regs, "xadc_temperature")

    def get_constant(names, default):
        constants = getattr(getattr(bus, "constants", None), "d", {})
        for name in names:
            if name in constants:
                value = constants[name]
                return int(value, 0) if isinstance(value, str) else int(value)
        return default

    leds_count    = get_constant(["leds_ngpio",    "leds_count"],    8) if with_leds    else 0
    buttons_count = get_constant(["buttons_ngpio", "buttons_count"], 8) if with_buttons else 0

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
        xadc_temp_scale      = get_constant(["xadc_hwmon_temp_scale"],      503975)
        xadc_temp_divisor    = get_constant(["xadc_hwmon_temp_divisor"],    4096)
        xadc_temp_offset     = get_constant(["xadc_hwmon_temp_offset"],     273150)
        xadc_voltage_scale   = get_constant(["xadc_hwmon_voltage_scale"],   3000)
        xadc_voltage_divisor = get_constant(["xadc_hwmon_voltage_divisor"], 4096)

        def get_xadc_temp():
            raw = bus.regs.xadc_temperature.read()
            return (raw*xadc_temp_scale/xadc_temp_divisor - xadc_temp_offset)/1000

        def get_xadc_voltage(reg):
            raw = reg.read()
            return raw*xadc_voltage_scale/xadc_voltage_divisor/1000

        def get_xadc_vccint():
            return get_xadc_voltage(bus.regs.xadc_vccint)

        def get_xadc_vccaux():
            return get_xadc_voltage(bus.regs.xadc_vccaux)

        def get_xadc_vccbram():
            return get_xadc_voltage(bus.regs.xadc_vccbram)

        def gen_xadc_data(get_cls, n):
            xadc_data = [get_cls()]*n
            while True:
                xadc_data.pop(-1)
                xadc_data.insert(0, get_cls())
                yield xadc_data

    # Memory.
    # -------

    def convert_size(size_bytes):
        """
        Convert the size from bytes to a more human-readable format.
        """
        if size_bytes < 1024:
            return f"{size_bytes} Bytes"
        elif size_bytes < 1024**2:
            return f"{size_bytes / 1024:.2f} KB"
        elif size_bytes < 1024**3:
            return f"{size_bytes / (1024 ** 2):.2f} MB"
        else:
            return f"{size_bytes / (1024 ** 3):.2f} GB"

    def read_memory_chunk(base, length):
        """Reads `length` bytes from `base` address (word-aligned)."""
        if length <= 0:
            return []

        aligned_len = (length + 3) & ~3  # Round up to nearest multiple of 4
        words       = bus.read(base, aligned_len // 4, burst="incr")
        out         = []

        for word in words:
            for byte_idx in range(4):
                byte_val = (word >> (8 * byte_idx)) & 0xff
                out.append(byte_val)

        return out[:length]

    def _printable_chr(bval):
        c = chr(bval)
        return c if 32 <= bval <= 126 else '.'

    def refresh_dump_table():
        """Refreshes the dump table with data from the specified base address and length."""
        try:
            base       = int(dpg.get_value("dump_base"), 0)
            length_str = dpg.get_value("dump_length")
            length     = int(length_str, 0) if length_str else 0
        except ValueError:
            print("Invalid base address or length.")
            return

        memory_data = read_memory_chunk(base, length)

        # Clear existing ROWS (slot=1) but keep the columns in slot=0
        for row_id in dpg.get_item_children("dump_table", 1):
            dpg.delete_item(row_id)

        # Add new rows
        BYTES_PER_LINE = 16
        for row_start in range(0, len(memory_data), BYTES_PER_LINE):
            row_data = memory_data[row_start:row_start + BYTES_PER_LINE]
            with dpg.table_row(parent="dump_table"):
                # Address column
                dpg.add_text(f"0x{base + row_start:08X}")

                # Hex data column
                hex_values = [f"{byte:02X}" for byte in row_data]
                dpg.add_text(" ".join(hex_values))

                # ASCII column
                ascii_values = [_printable_chr(byte) for byte in row_data]
                dpg.add_text("".join(ascii_values))

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
                        except ValueError:
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
                    for i in range(leds_count):
                        if sender == f"led{i}":
                            val = get_leds(i)
                            set_leds(i, ~val)
                for i in range(leds_count):
                    dpg.add_checkbox(id=f"led{i}", callback=led_callback)
        if with_buttons:
            dpg.add_text("Buttons")
            with dpg.group(horizontal=True):
                for i in range(buttons_count):
                    dpg.add_checkbox(id=f"btn{i}")

    # Create Memory Window.
    # ---------------------
    with dpg.window(label="FPGA Memory", autosize=True, pos=(550, 150)):
        # Memory Regions.
        dpg.add_text("Mem Regions:")
        with dpg.table(
            tag            = "memory_regions_table",
            header_row     = True,
            row_background = True,
            scrollY        = True,   # allow scrolling within the child
            width          = -1,
            height         = 100,
        ):
            dpg.add_table_column(label="Name")
            dpg.add_table_column(label="Base")
            dpg.add_table_column(label="Size")
            dpg.add_table_column(label="Type")

            for region_name, region_obj in bus.mems.__dict__.items():
                with dpg.table_row():
                    dpg.add_text(f"{region_name}")
                    dpg.add_text(f"0x{region_obj.base:08X}")
                    dpg.add_text(f"{convert_size(region_obj.size)}")
                    dpg.add_text(f"{region_obj.type}")

        # Memory Read.
        dpg.add_separator()
        dpg.add_text("Mem Read:")
        with dpg.group(horizontal=True):
            dpg.add_checkbox(label="Auto-Refresh", tag="auto_refresh_mem_read", default_value=False)
            dpg.add_text("Delay (s):")
            dpg.add_input_float(tag="mem_read_delay", default_value=1.0, width=100)
        with dpg.group(horizontal=True):
            dpg.add_text("Address:")
            dpg.add_input_text(
                tag           = "read_addr",
                default_value = "0x00000000",
                width         = 120
            )
            dpg.add_text("Value:")
            dpg.add_input_text(
                tag           = "read_value",
                default_value = "0x00000000",
                width         = 120,
                readonly      = True
            )
            dpg.add_button(
                label    = "Read",
                callback = lambda: dpg.set_value("read_value", f"0x{bus.read(int(dpg.get_value('read_addr'), 0)):08X}")
            )

        # Memory Write.
        dpg.add_separator()
        dpg.add_text("Mem Write:")
        with dpg.group(horizontal=True):
            dpg.add_text("Address:")
            dpg.add_input_text(
                tag           = "write_addr",
                default_value = "0x00000000",
                width         = 120
            )
            dpg.add_text("Value:")
            dpg.add_input_text(
                tag           = "write_value",
                default_value = "0x00000000",
                width         = 120
            )
            dpg.add_button(
                label    = "Write",
                callback = lambda: bus.write(int(dpg.get_value("write_addr"), 0), int(dpg.get_value("write_value"), 0))
            )


        # Memory Dump
        dpg.add_separator()
        dpg.add_text("Mem Dump")
        with dpg.group(horizontal=True):
            dpg.add_checkbox(label="Auto-Refresh", tag="auto_refresh_mem_dump", default_value=False)
            dpg.add_text("Delay (s):")
            dpg.add_input_float(tag="mem_dump_delay", default_value=1.0, width=100)
        with dpg.group(horizontal=True):
            # Base.
            dpg.add_text("Base:")
            dpg.add_input_text(
                tag           = "dump_base",
                default_value = "0x00000000",
                width         = 120
            )

            # Length.
            dpg.add_text("Length (bytes):")
            dpg.add_input_text(
                tag           = "dump_length",
                default_value = "256",
                width         = 120
            )

            # Control
            dpg.add_button(label="Read", callback=refresh_dump_table)

        # Memory Table
        with dpg.table(
            tag            = "dump_table",
            header_row     = True,
            resizable      = False,
            policy         = dpg.mvTable_SizingStretchProp,
            scrollX        = True,
            scrollY        = True,
            row_background = True,
            width          = -1,
            height         = -1,
        ):
            dpg.add_table_column(label="Address")
            dpg.add_table_column(label="Hex Data")
            dpg.add_table_column(label="ASCII")

    # Create XADC Window.
    # -------------------
    if with_xadc:
        with dpg.window(label="FPGA XADC", width=600, height=600, pos=(1000, 0)):
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

    def timer_callback(refresh=1e-1, xadc_points=100):
        last_mem_read_time = time.time()
        last_mem_dump_time = time.time()

        if with_xadc:
            temp    = gen_xadc_data(get_xadc_temp,    n=xadc_points)
            vccint  = gen_xadc_data(get_xadc_vccint,  n=xadc_points)
            vccaux  = gen_xadc_data(get_xadc_vccaux,  n=xadc_points)
            vccbram = gen_xadc_data(get_xadc_vccbram, n=xadc_points)

        while dpg.is_dearpygui_running():
            now = time.time()

            # CSR Update.
            for name, reg in bus.regs.__dict__.items():
                value = reg.read()
                dpg.set_value(item=name, value=f"0x{value:x}")

            # XADC Update.
            if with_xadc:
                for name, gen in [
                    ("temp",      temp),
                    ("vccint",   vccint),
                    ("vccbram", vccbram),
                    ("vccaux",   vccaux),
                ]:
                    datay = next(gen)
                    datax = list(range(len(datay)))
                    dpg.set_value(name, [datax, datay])
                    dpg.set_item_label(name, name)
                    dpg.set_axis_limits_auto(f"{name}_x")
                    dpg.fit_axis_data(f"{name}_x")

            # Peripherals.
            if with_leds:
                for i in range(leds_count):
                    dpg.set_value(f"led{i}", bool(get_leds(i)))

            if with_buttons:
                for i in range(buttons_count):
                    dpg.set_value(f"btn{i}", bool(get_buttons(i)))

            # Mem Read Auto-Refresh.
            if dpg.does_item_exist("auto_refresh_mem_read"):
                if dpg.get_value("auto_refresh_mem_read"):
                    delay_sec = dpg.get_value("mem_read_delay")
                    if (now - last_mem_read_time) >= delay_sec:
                        try:
                            read_addr = int(dpg.get_value("read_addr"), 0)
                            val       = bus.read(read_addr)
                            dpg.set_value("read_value", f"0x{val:08X}")
                        except ValueError:
                            pass
                        last_mem_read_time = now

            # Mem Dump Auto-Refresh.
            if dpg.does_item_exist("auto_refresh_mem_dump"):
                if dpg.get_value("auto_refresh_mem_dump"):
                    delay_sec = dpg.get_value("mem_dump_delay")
                    if (now - last_mem_dump_time) >= delay_sec:
                        refresh_dump_table()
                        last_mem_dump_time = now

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
    # Common.
    parser.add_argument("--csr-csv",    default="csr.csv",       help="CSR configuration file")
    parser.add_argument("--host",       default="localhost",     help="Host ip address")
    parser.add_argument("--port",       default="1234",          help="Host bind port.")
    parser.add_argument("--binary",     action="store_true",     help="Use binary format for displayed values.")
    parser.add_argument("--file",       default=None,            help="File to read from or write to in binary mode.")
    parser.add_argument("--endianness", default="little",        choices=["little", "big"], help="Endianness for memory accesses (little or big).")
    parser.add_argument("--timeout",        default="2.0",          help="Socket timeout.")
    parser.add_argument("--strict-timeout", action="store_true",    help="Raise on remote read timeout.")

    # Identifier.
    parser.add_argument("--ident",      action="store_true",     help="Dump SoC identifier.")

    # Registers.
    parser.add_argument("--regs",       action="store_true",     help="Dump SoC registers.")
    parser.add_argument("--filter",     default=None,            help="Registers filter (to be used with --regs).")

    # Memory.
    parser.add_argument("--read",       default=None,            help="Do a MMAP Read to SoC bus (--read addr/reg).")
    parser.add_argument("--write",      default=None, nargs="*", help="Do a MMAP Write to SoC bus (--write addr/reg [data]).")
    parser.add_argument("--length",     default="4",             help="MMAP access length.")

    # GUI.
    parser.add_argument("--gui",        action="store_true",     help="Run GUI.")

    args = parser.parse_args()

    # Parameters.
    host    = args.host
    csr_csv = args.csr_csv
    port    = int(args.port, 0)
    timeout = float(args.timeout)

    # Identifier.
    if args.ident:
        dump_identifier(
            host             = host,
            csr_csv          = csr_csv,
            port             = port,
            timeout          = timeout,
            raise_on_timeout = args.strict_timeout,
        )

    # Registers.
    if args.regs:
        dump_registers(
            host             = host,
            csr_csv          = csr_csv,
            port             = port,
            filter           = args.filter,
            binary           = args.binary,
            timeout          = timeout,
            raise_on_timeout = args.strict_timeout,
        )

    # Memory Read.
    if args.read:
        try:
           addr = int(args.read, 0)
        except ValueError:
            addr = reg2addr(host, csr_csv, args.read)
        read_memory(
            host             = host,
            csr_csv          = csr_csv,
            port             = port,
            addr             = addr,
            length           = int(args.length, 0),
            binary           = args.binary,
            file             = args.file,
            endianness       = args.endianness,
            timeout          = timeout,
            raise_on_timeout = args.strict_timeout,
        )

    # Memory Write.
    if args.write:
        try:
            addr = int(args.write[0], 0)
        except ValueError:
            addr = reg2addr(host, csr_csv, args.write[0])

        # If --file is provided, ignore the second argument for --write
        if args.file:
            data = 0  # Dummy value, not used when --file is provided
        else:
            if len(args.write) < 2:
                raise ValueError("Data argument is required for --write when --file is not provided.")
            data = int(args.write[1], 0)

        write_memory(
            host             = host,
            csr_csv          = csr_csv,
            port             = port,
            addr             = addr,
            data             = data,
            file             = args.file,
            length           = int(args.length, 0) if args.length else None,
            endianness       = args.endianness,
            timeout          = timeout,
            raise_on_timeout = args.strict_timeout,
        )

    # GUI.
    if args.gui:
        run_gui(
            host             = host,
            csr_csv          = csr_csv,
            port             = port,
            timeout          = timeout,
            raise_on_timeout = args.strict_timeout,
        )

if __name__ == "__main__":
    main()
