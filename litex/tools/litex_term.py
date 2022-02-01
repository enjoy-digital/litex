#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2015-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2015 Sebastien Bourdeauducq <sb@m-labs.hk>
# Copyright (c) 2016 whitequark <whitequark@whitequark.org>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import signal
import os
import time
import serial
import threading
import multiprocessing
import argparse
import json
import socket

# Console ------------------------------------------------------------------------------------------

if sys.platform == "win32":
    import ctypes
    import msvcrt
    class Console:
        def configure(self):
            # https://stackoverflow.com/a/36760881
            # ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32 = ctypes.windll.kernel32
            kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)

        def unconfigure(self):
            pass

        def getkey(self):
            return msvcrt.getch()

        # getch doesn't return Virtual Keycodes, but rather
        # PS/2 Scan Codes. Keycodes starting with 0xE0 are
        # worth handling.
        def escape_char(self, b):
            return b == b"\xe0"

        def handle_escape(self, b):
            return {
                b"H" : b"\x1b[A",  # Up
                b"P" : b"\x1b[B",  # Down
                b"K" : b"\x1b[D",  # Left
                b"M" : b"\x1b[C",  # Right
                b"G" : b"\x1b[H",  # Home
                b"O" : b"\x1b[F",  # End
                b"R" : b"\x1b[2~", # Insert
                b"S" : b"\x1b[3~", # Delete
            }.get(b, None) # TODO: Handle ESC? Others?

else:
    import termios
    import pty
    class Console:
        def __init__(self):
            self.fd = sys.stdin.fileno()
            self.default_settings = termios.tcgetattr(self.fd)

        def configure(self):
            settings = termios.tcgetattr(self.fd)
            settings[3] = settings[3] & ~termios.ICANON & ~termios.ECHO
            settings[6][termios.VMIN] = 1
            settings[6][termios.VTIME] = 0
            termios.tcsetattr(self.fd, termios.TCSANOW, settings)

        def unconfigure(self):
            termios.tcsetattr(self.fd, termios.TCSAFLUSH, self.default_settings)

        def getkey(self):
            return os.read(self.fd, 1)

        def escape_char(self, b):
            return False

        def handle_escape(self, b):
            return None

# Crossover UART  -------------------------------------------------------------------------------------

from litex import RemoteClient

class CrossoverUART:
    def __init__(self, name="uart_xover", host="localhost", base_address=None, csr_csv=None):
        self.bus = RemoteClient(host=host, base_address=base_address, csr_csv=csr_csv)
        present = False
        for k, v in self.bus.regs.d.items():
            if f"{name}_" in k:
                setattr(self, k.replace(f"{name}_", ""), v)
                present = True
        if not present:
            raise ValueError(f"CrossoverUART {name} not present in design.")

        # FIXME: On PCIe designs, CSR is remapped to 0 to limit BAR0 size.
        if base_address is None and hasattr(self.bus.bases, "pcie_phy"):
            self.bus.base_address = -self.bus.mems.csr.base

    def open(self):
        self.bus.open()
        self.file, self.name = pty.openpty()
        self.pty2crossover_thread = multiprocessing.Process(target=self.pty2crossover)
        self.crossover2pty_thread = multiprocessing.Process(target=self.crossover2pty)
        self.pty2crossover_thread.start()
        self.crossover2pty_thread.start()

    def close(self):
        self.bus.close()
        self.pty2crossover_thread.terminate()
        self.crossover2pty_thread.terminate()

    def pty2crossover(self):
        while True:
            r = os.read(self.file, 1)
            self.rxtx.write(ord(r))

    def crossover2pty(self):
        while True:
            if self.rxfull.read():
                length = 16
            elif not self.rxempty.read():
                length = 1
            else:
                time.sleep(1e-3)
                continue
            r = self.bus.read(self.rxtx.addr, length=length, burst="fixed")
            for v in r:
                os.write(self.file, bytes(chr(v).encode("utf-8")))

# JTAG UART ----------------------------------------------------------------------------------------

from litex.build.openocd import OpenOCD

class JTAGUART:
    def __init__(self, config="openocd_xc7_ft2232.cfg", port=20000, chain=1):
        self.config = config
        self.port   = port
        self.chain  = chain

    def open(self):
        self.file, self.name = pty.openpty()
        self.jtag2tcp_thread = multiprocessing.Process(target=self.jtag2tcp)
        self.jtag2tcp_thread.start()
        time.sleep(0.5)
        self.pty2tcp_thread  = multiprocessing.Process(target=self.pty2tcp)
        self.tcp2pty_thread  = multiprocessing.Process(target=self.tcp2pty)
        self.tcp = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.tcp.connect(("localhost", self.port))
        self.pty2tcp_thread.start()
        self.tcp2pty_thread.start()

    def close(self):
        self.jtag2tcp_thread.terminate()
        self.pty2tcp_thread.terminate()
        self.tcp2pty_thread.terminate()

    def jtag2tcp(self):
        prog = OpenOCD(self.config)
        prog.stream(self.port, self.chain)

    def pty2tcp(self):
        while True:
            r = os.read(self.file, 1)
            self.tcp.send(r)

    def tcp2pty(self):
        while True:
            r = self.tcp.recv(1)
            os.write(self.file, bytes(r))

# Intel/Altera JTAG UART via nios2-terminal
class Nios2Terminal():
    def __init__(self):
        from subprocess import Popen, PIPE
        p = Popen("nios2-terminal", stdin=PIPE, stdout=PIPE)
        self.p = p

    def read(self):
        return self.p.stdout.read(1)

    def in_waiting(self):
        # unfortunately p.stdout does not provide
        # information about awaiting input
        return False

    def write(self, data):
        if data is not None:
            self.p.stdin.write(data)
            try:
                self.p.stdin.flush()
            except BrokenPipeError:
                print("nios2-terminal has terminated, exiting...\n")
                sys.exit(1)

    def close(self):
        self.p.terminate()

# SFL ----------------------------------------------------------------------------------------------

sfl_prompt_req = b"F7:    boot from serial\n"
sfl_prompt_ack = b"\x06"

sfl_magic_req = b"sL5DdSMmkekro\n"
sfl_magic_ack = b"z6IHG7cYDID6o\n"

sfl_payload_length  = 255

# General commands
sfl_cmd_abort       = b"\x00"
sfl_cmd_load        = b"\x01"
sfl_cmd_jump        = b"\x02"

# Replies
sfl_ack_success  = b"K"
sfl_ack_crcerror = b"C"
sfl_ack_unknown  = b"U"
sfl_ack_error    = b"E"


class SFLFrame:
    def __init__(self):
        self.cmd = bytes()
        self.payload = bytes()

    def compute_crc(self):
        return crc16(self.cmd + self.payload)

    def encode(self):
        packet = bytes([len(self.payload)])
        packet += self.compute_crc().to_bytes(2, "big")
        packet += self.cmd
        packet += self.payload
        return packet

# CRC16 --------------------------------------------------------------------------------------------

crc16_table = [
    0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
    0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
    0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
    0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
    0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
    0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
    0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
    0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
    0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
    0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
    0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
    0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
    0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
    0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
    0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
    0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
    0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
    0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
    0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
    0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
    0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
    0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
    0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
    0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
    0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
    0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
    0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
    0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
    0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
    0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
    0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
    0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
]


def crc16(l):
    crc = 0
    for d in l:
        crc = crc16_table[((crc >> 8) ^ d) & 0xff] ^ (crc << 8)
    return crc & 0xffff

# LiteXTerm ----------------------------------------------------------------------------------------

class LiteXTerm:
    def __init__(self, serial_boot, kernel_image, kernel_address, json_images, safe):
        self.serial_boot = serial_boot
        assert not (kernel_image is not None and json_images is not None)
        self.mem_regions = {}
        if kernel_image is not None:
            self.mem_regions = {kernel_image: kernel_address}
            self.boot_address = kernel_address
        if json_images is not None:
            f = open(json_images, "r")
            json_dir = os.path.dirname(json_images)
            for k, v in json.load(f).items():
                self.mem_regions[os.path.join(json_dir, k)] = v
            self.boot_address = self.mem_regions[list(self.mem_regions.keys())[-1]]
            f.close()

        self.reader_alive = False
        self.writer_alive = False

        self.prompt_detect_buffer = bytes(len(sfl_prompt_req))
        self.magic_detect_buffer  = bytes(len(sfl_magic_req))

        self.console = Console()

        signal.signal(signal.SIGINT, self.sigint)
        self.sigint_time_last = 0

        self.safe        = safe
        self.delay       = 0
        self.length      = 64
        self.outstanding = 0 if safe else 128

    def open(self, port, baudrate):
        if hasattr(self, "port"):
            return
        self.port = serial.serial_for_url(port, baudrate)

    def close(self):
        if not hasattr(self, "port"):
            return
        self.port.close()
        del self.port

    def sigint(self, sig, frame):
        if hasattr(self, "port"):
            self.port.write(b"\x03")
        sigint_time_current = time.time()
        # Exit term if 2 CTRL-C pressed in less than 0.5s.
        if (sigint_time_current - self.sigint_time_last < 0.5):
            self.console.unconfigure()
            self.close()
            sys.exit()
        else:
            self.sigint_time_last = sigint_time_current

    def send_frame(self, frame):
        retry = 1
        while retry:
            self.port.write(frame.encode())
            # Get the reply from the device
            reply = self.port.read()
            if reply == sfl_ack_success:
                retry = 0
            elif reply == sfl_ack_crcerror:
                retry = 1
            else:
                print("[LITEX-TERM] Got unknown reply '{}' from the device, aborting.".format(reply))
                return 0
        return 1

    def receive_upload_response(self):
        reply = self.port.read()
        if reply == sfl_ack_success:
            return True
        elif reply == sfl_ack_crcerror:
            print("[LITEX-TERM] Upload to device failed due to data corruption (CRC error)")
        else:
            print(f"[LITEX-TERM] Got unexpected response from device '{reply}'")
        sys.exit(1)

    def upload_calibration(self, address):

        print("[LITEX-TERM] Upload calibration... ", end="")
        sys.stdout.flush()

        # Calibration parameters.
        min_delay    = 1e-5
        max_delay    = 1e-3
        nframes      = 16
        length_range = [64]

        # Run calibration with increasing delay and decreasing length.
        delay = min_delay
        working_delay  = None
        working_length = None
        while delay <= max_delay:
            for length in length_range:
                #p0rint(f"delay {delay}, length {length}")
                # Prepare frame.
                frame         = SFLFrame()
                frame.cmd     = sfl_cmd_load
                frame_data    = bytearray(min(length, sfl_payload_length-4))
                frame.payload = address.to_bytes(4, "big")
                frame.payload += frame_data
                frame = frame.encode()

                # Send N consecutive frames.
                for i in range(nframes):
                    self.port.write(frame)
                    time.sleep(delay)

                # Wait and get acks.
                working = True
                time.sleep(0.2)
                while self.port.in_waiting:
                    ack = self.port.read()
                    #print(ack)
                    if ack in [sfl_ack_error, sfl_ack_crcerror]:
                        working = False

                if working:
                    # Save working delay/length and exit.
                    working_delay  = delay
                    working_length = min(length, sfl_payload_length - 4)
                    break

            # Exit if working delay found.
            if (working_delay is not None):
                break

            # Else increase delay.
            delay = delay*2

        # Set parameters.
        if (working_delay is not None):
            print(f"(inter-frame: {working_delay*1e6:5.2f}us, length: {working_length})")
            self.delay  = working_delay
            self.length = working_length
        else:
            print("failed, switching to --safe mode.")
            self.delay       = 0
            self.length      = 64
            self.outstanding = 0

    def upload(self, filename, address):
        f = open(filename, "rb")
        f.seek(0, 2)
        length = f.tell()
        f.seek(0, 0)

        print(f"[LITEX-TERM] Uploading {filename} to 0x{address:08x} ({length} bytes)...")

        # Upload calibration
        if not self.safe:
            self.upload_calibration(address)
            # Force safe mode settings when calibration fails.
            if self.delay is None:
                self.delay       = 0
                self.length      = 64
                self.outstanding = 0

        # Prepare parameters
        current_address = address
        position        = 0
        start           = time.time()
        remaining       = length
        outstanding     = 0
        while remaining:
            # Show progress
            sys.stdout.write("|{}>{}| {}%\r".format(
                "=" * (20*position//length),
                " " * (20-20*position//length),
                100*position//length))
            sys.stdout.flush()

            # Send frame if max outstanding not reached.
            if outstanding <= self.outstanding:
                # Prepare frame.
                frame      = SFLFrame()
                frame.cmd  = sfl_cmd_load
                frame_data = f.read(min(remaining, self.length-4))
                frame.payload = current_address.to_bytes(4, "big")
                frame.payload += frame_data

                # Encode frame and send it.
                self.port.write(frame.encode())

                # Update parameters
                current_address += len(frame_data)
                position        += len(frame_data)
                remaining       -= len(frame_data)
                outstanding     += 1

                # Inter-frame delay.
                time.sleep(self.delay)

            # Read response if available.
            while self.port.in_waiting:
                ack = self.receive_upload_response()
                if ack:
                    outstanding -= 1
                    break

        # Get remaining responses.
        for _ in range(outstanding):
            self.receive_upload_response()

        # Compute speed.
        end     = time.time()
        elapsed = end - start
        print("[LITEX-TERM] Upload complete ({0:.1f}KB/s).".format(length/(elapsed*1024)))
        f.close()
        return length

    def boot(self):
        print("[LITEX-TERM] Booting the device.")
        frame = SFLFrame()
        frame.cmd = sfl_cmd_jump
        frame.payload = int(self.boot_address, 16).to_bytes(4, "big")
        self.send_frame(frame)

    def detect_prompt(self, data):
        if len(data):
            self.prompt_detect_buffer = self.prompt_detect_buffer[1:] + data
            return self.prompt_detect_buffer == sfl_prompt_req
        else:
            return False

    def answer_prompt(self):
        print("[LITEX-TERM] Received serial boot prompt from the device.")
        self.port.write(sfl_prompt_ack)

    def detect_magic(self, data):
        if len(data):
            self.magic_detect_buffer = self.magic_detect_buffer[1:] + data
            return self.magic_detect_buffer == sfl_magic_req
        else:
            return False

    def answer_magic(self):
        print("[LITEX-TERM] Received firmware download request from the device.")
        if(len(self.mem_regions)):
            self.port.write(sfl_magic_ack)
        for filename, base in self.mem_regions.items():
            self.upload(filename, int(base, 16))
        self.boot()
        print("[LITEX-TERM] Done.")

    def reader(self):
        try:
            while self.reader_alive:
                c = self.port.read()
                sys.stdout.buffer.write(c)
                sys.stdout.flush()
                if len(self.mem_regions):
                    if self.serial_boot and self.detect_prompt(c):
                        self.answer_prompt()
                    if self.detect_magic(c):
                        self.answer_magic()

        except serial.SerialException:
            self.reader_alive = False
            self.console.unconfigure()
            raise

    def start_reader(self):
        self.reader_alive = True
        self.reader_thread = threading.Thread(target=self.reader)
        self.reader_thread.setDaemon(True)
        self.reader_thread.start()

    def stop_reader(self):
        self.reader_alive = False
        self.reader_thread.join()

    def writer(self):
        try:
            while self.writer_alive:
                b = self.console.getkey()
                if b == b"\x03":
                    self.stop()
                elif b == b"\n":
                    self.port.write(b"\x0a")
                elif self.console.escape_char(b):
                    b = self.console.getkey()
                    ansi_seq = self.console.handle_escape(b)
                    self.port.write(ansi_seq)
                else:
                    self.port.write(b)
        except:
            self.writer_alive = False
            self.console.unconfigure()
            raise

    def start_writer(self):
        self.writer_alive = True
        self.writer_thread = threading.Thread(target=self.writer)
        self.writer_thread.setDaemon(True)
        self.writer_thread.start()

    def stop_writer(self):
        self.writer_alive = False
        self.writer_thread.join()

    def start(self):
        self.start_reader()
        self.start_writer()

    def stop(self):
        self.reader_alive = False
        self.writer_alive = False

    def join(self, writer_only=False):
        self.writer_thread.join()
        if not writer_only:
            self.reader_thread.join()

# Run ----------------------------------------------------------------------------------------------

def _get_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("port",                                               help="Serial port (eg /dev/tty*, crossover, jtag).")
    parser.add_argument("--speed",        default=115200,                     help="Serial baudrate.")
    parser.add_argument("--serial-boot",  default=False, action='store_true', help="Automatically initiate serial boot.")
    parser.add_argument("--kernel",       default=None,                       help="Kernel image.")
    parser.add_argument("--kernel-adr",   default="0x40000000",               help="Kernel address.")
    parser.add_argument("--images",       default=None,                       help="JSON description of the images to load to memory.")
    parser.add_argument("--safe",         action="store_true",                help="Safe serial boot mode, disable upload speed optimizations.")

    parser.add_argument("--csr-csv",        default=None,                       help="SoC CSV file.")
    parser.add_argument("--base-address",   default=None,                       help="CSR base address.")
    parser.add_argument("--crossover-name", default="uart_xover",               help="Crossover UART name to use (present in design/csr.csv).")

    parser.add_argument("--jtag-name",    default="jtag_uart",                help="JTAG UART type (jtag_uart).")
    parser.add_argument("--jtag-config",  default="openocd_xc7_ft2232.cfg",   help="OpenOCD JTAG configuration file for jtag_uart.")
    parser.add_argument("--jtag-chain",   default=1,                          help="JTAG chain.")
    return parser.parse_args()

def main():
    args = _get_args()
    term = LiteXTerm(args.serial_boot, args.kernel, args.kernel_adr, args.images, args.safe)

    if sys.platform == "win32":
        if args.port in ["crossover", "jtag"]:
            raise NotImplementedError
    if args.port in ["crossover"]:
        base_address = None if args.base_address is None else int(args.base_address)
        xover = CrossoverUART(base_address=base_address, csr_csv=args.csr_csv, name=args.crossover_name)
        xover.open()
        port = os.ttyname(xover.name)
    elif args.port in ["jtag"]:
        if args.jtag_name == "jtag_uart":
            jtag_uart = JTAGUART(config=args.jtag_config, chain=int(args.jtag_chain))
            jtag_uart.open()
            port = os.ttyname(jtag_uart.name)
        else:
            raise NotImplementedError
    else:
        port = args.port
    term.open(port, int(float(args.speed)))
    term.console.configure()
    term.start()
    term.join(True)

if __name__ == "__main__":
    main()
