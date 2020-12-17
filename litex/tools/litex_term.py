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
import multiprocessing
import argparse
import json
import pty
import telnetlib

# Console ------------------------------------------------------------------------------------------

if sys.platform == "win32":
    import msvcrt
    class Console:
        def configure(self):
            pass

        def unconfigure(self):
            pass

        def getkey(self):
            return msvcrt.getch()
else:
    import termios
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

# Crossover UART  ----------------------------------------------------------------------------------

from litex import RemoteClient

class CrossoverUART:
    def __init__(self, host="localhost", base_address=0): # FIXME: add command line arguments
        self.bus = RemoteClient(host=host, base_address=base_address)

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
            self.bus.regs.uart_xover_rxtx.write(ord(r))

    def crossover2pty(self):
        while True:
            if self.bus.regs.uart_txfull.read():
                length = 16
            elif not self.bus.regs.uart_xover_rxempty.read():
                length = 1
            else:
                length = 0
            if length:
                r = self.bus.read(self.bus.regs.uart_xover_rxtx.addr, length=length, burst="fixed")
                for v in r:
                    os.write(self.file, bytes(chr(v).encode("utf-8")))

# JTAG UART ----------------------------------------------------------------------------------------

from litex.build.openocd import OpenOCD

class JTAGUART:
    def __init__(self, config="openocd_xc7_ft2232.cfg", port=20000): # FIXME: add command line arguments
        self.config = config
        self.port   = port

    def open(self):
        self.file, self.name = pty.openpty()
        self.jtag2telnet_thread = multiprocessing.Process(target=self.jtag2telnet)
        self.jtag2telnet_thread.start()
        time.sleep(0.5)
        self.pty2telnet_thread  = multiprocessing.Process(target=self.pty2telnet)
        self.telnet2pty_thread  = multiprocessing.Process(target=self.telnet2pty)
        self.telnet = telnetlib.Telnet("localhost", self.port)
        self.pty2telnet_thread.start()
        self.telnet2pty_thread.start()

    def close(self):
        self.jtag2telnet_thread.terminate()
        self.pty2telnet_thread.terminate()
        self.telnet2pty_thread.terminate()

    def jtag2telnet(self):
        prog = OpenOCD(self.config)
        prog.stream(self.port)

    def pty2telnet(self):
        while True:
            r = os.read(self.file, 1)
            self.telnet.write(r)
            if r == bytes("\n".encode("utf-8")):
                self.telnet.write("\r".encode("utf-8"))
            self.telnet.write("\n".encode("utf-8"))

    def telnet2pty(self):
        while True:
            r = self.telnet.read_some()
            os.write(self.file, bytes(r))

# SFL ----------------------------------------------------------------------------------------------

sfl_prompt_req = b"F7:    boot from serial\n"
sfl_prompt_ack = b"\x06"

sfl_magic_req = b"sL5DdSMmkekro\n"
sfl_magic_ack = b"z6IHG7cYDID6o\n"

sfl_payload_length = 255
sfl_outstanding    = 128

# General commands
sfl_cmd_abort       = b"\x00"
sfl_cmd_load        = b"\x01"
sfl_cmd_jump        = b"\x02"
sfl_cmd_flash       = b"\x04"
sfl_cmd_reboot      = b"\x05"

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
    def __init__(self, serial_boot, kernel_image, kernel_address, json_images, flash):
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
        self.flash = flash

        self.reader_alive = False
        self.writer_alive = False

        self.prompt_detect_buffer = bytes(len(sfl_prompt_req))
        self.magic_detect_buffer = bytes(len(sfl_magic_req))

        self.console = Console()

        signal.signal(signal.SIGINT, self.sigint)
        self.sigint_time_last = 0

    def open(self, port, baudrate):
        if hasattr(self, "port"):
            return
        # FIXME: https://github.com/enjoy-digital/litex/issues/720
        if "ttyACM" in port:
            self.payload_length = sfl_payload_length
            self.delay          = 1e-4
        else:
            self.payload_length = 64
            self.delay          = 1e-5
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
                print("[LXTERM] Got unknown reply '{}' from the device, aborting.".format(reply))
                return 0
        return 1

    def receive_upload_response(self):
        reply = self.port.read()
        if reply == sfl_ack_success:
            return
        elif reply == sfl_ack_crcerror:
            print("[LXTERM] Upload to device failed due to data corruption (CRC error)")
        else:
            print(f"[LXTERM] Got unexpected response from device '{reply}'")
        sys.exit(1)

    def upload(self, filename, address):
        f = open(filename, "rb")
        f.seek(0, 2)
        length = f.tell()
        f.seek(0, 0)

        action = "Flashing" if self.flash else "Uploading"
        print(f"[LXTERM] {action} {filename} to 0x{address:08x} ({length} bytes)...")

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
            if outstanding <= sfl_outstanding:
                # Prepare frame.
                frame = SFLFrame()
                frame_data = f.read(min(remaining, self.payload_length-4))
                if self.flash:
                    frame.cmd = sfl_cmd_flash
                else:
                    frame.cmd = sfl_cmd_load
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

            # Read response if availables.
            while self.port.in_waiting:
                self.receive_upload_response()
                outstanding -= 1

        # Get remaining responses.
        for _ in range(outstanding):
            self.receive_upload_response()

        # Compute speed.
        end     = time.time()
        elapsed = end - start
        print("[LXTERM] Upload complete ({0:.1f}KB/s).".format(length/(elapsed*1024)))
        f.close()
        return length

    def boot(self):
        print("[LXTERM] Booting the device.")
        frame = SFLFrame()
        frame.cmd = sfl_cmd_jump
        frame.payload = int(self.boot_address, 16).to_bytes(4, "big")
        self.send_frame(frame)

    def reboot(self):
        print("[LXTERM] Rebooting the device.")
        frame = SFLFrame()
        frame.cmd = sfl_cmd_reboot
        self.send_frame(frame)

    def detect_prompt(self, data):
        if len(data):
            self.prompt_detect_buffer = self.prompt_detect_buffer[1:] + data
            return self.prompt_detect_buffer == sfl_prompt_req
        else:
            return False

    def answer_prompt(self):
        print("[LXTERM] Received serial boot prompt from the device.")
        self.port.write(sfl_prompt_ack)

    def detect_magic(self, data):
        if len(data):
            self.magic_detect_buffer = self.magic_detect_buffer[1:] + data
            return self.magic_detect_buffer == sfl_magic_req
        else:
            return False

    def answer_magic(self):
        print("[LXTERM] Received firmware download request from the device.")
        if(len(self.mem_regions)):
            self.port.write(sfl_magic_ack)
        for filename, base in self.mem_regions.items():
            self.upload(filename, int(base, 16))
        if self.flash:
            # clear mem_regions to avoid re-flashing on next reboot(s)
            self.mem_regions = {}
        else:
            self.boot()
        print("[LXTERM] Done.");

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
        self.reader_thread = multiprocessing.Process(target=self.reader)
        self.reader_thread.start()

    def stop_reader(self):
        self.reader_alive = False
        self.reader_thread.terminate()

    def writer(self):
        try:
            while self.writer_alive:
                b = self.console.getkey()
                if b == b"\x03":
                    self.stop()
                elif b == b"\n":
                    self.port.write(b"\x0a")
                else:
                    self.port.write(b)
        except:
            self.writer_alive = False
            self.console.unconfigure()
            raise

    def start_writer(self):
        self.writer_alive = True
        self.writer_thread = multiprocessing.Process(target=self.writer)
        self.writer_thread.start()

    def stop_writer(self):
        self.writer_alive = False
        self.writer_thread.terminate()

    def start(self):
        self.start_reader()
        self.start_writer()

    def stop(self):
        self.reader_thread.terminate()
        self.writer_thread.terminate()

# Run ----------------------------------------------------------------------------------------------

def _get_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("port",                                              help="Serial port")
    parser.add_argument("--speed",       default=115200,                     help="Aerial baudrate")
    parser.add_argument("--serial-boot", default=False, action='store_true', help="Automatically initiate serial boot")
    parser.add_argument("--kernel",      default=None,                       help="Kernel image")
    parser.add_argument("--kernel-adr",  default="0x40000000",               help="Kernel address (or flash offset with --flash)")
    parser.add_argument("--images",      default=None,                       help="JSON description of the images to load to memory")
    parser.add_argument("--no-crc",      default=False, action='store_true', help="Disable CRC check (speedup serialboot)")
    parser.add_argument("--flash",       default=False, action='store_true', help="Flash data with serialboot command")
    return parser.parse_args()

def main():
    args = _get_args()
    if args.no_crc:
        print("[LXTERM] --no-crc is deprecated and now does nothing (CRC checking is now fast)")
    term = LiteXTerm(args.serial_boot, args.kernel, args.kernel_adr, args.images, args.flash)

    bridge_cls = {"crossover": CrossoverUART, "jtag_uart": JTAGUART}.get(args.port, None)
    if bridge_cls is not None:
        bridge = bridge_cls()
        bridge.open()
        port = os.ttyname(bridge.name)
    else:
        port = args.port
    term.open(port, int(float(args.speed)))
    term.console.configure()
    try:
        term.start()
        while True: pass
    except:
        if bridge_cls is not None:
            bridge.close()
        term.console.unconfigure()
        term.stop()
        term.close()

if __name__ == "__main__":
    main()
