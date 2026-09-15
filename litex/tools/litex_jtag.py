#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import time
import socket
import argparse

from litex import RemoteClient

# JTAG Remote Bitbang ------------------------------------------------------------------------------

class JTAGRemoteBitbang:
    """Expose JTAGBitbang CSRs through OpenOCD's remote_bitbang protocol."""
    def __init__(self, bus, csr_name="cpu_jtag_debug"):
        self.control = getattr(bus.regs, f"{csr_name}_control")
        self.status  = getattr(bus.regs, f"{csr_name}_status")
        self.value   = self.control.read()

    def process(self, command):
        if ord("0") <= command <= ord("7"):
            # OpenOCD encodes TCK/TMS/TDI as bits 2/1/0; the CSR uses bits 0/1/2.
            pins = command - ord("0")
            self.value = (self.value & 8) | ((pins >> 2) & 1) | (pins & 2) | ((pins & 1) << 2)
            self.control.write(self.value)
        elif command == ord("R"):
            return b"1" if self.status.read() & 1 else b"0"
        elif ord("r") <= command <= ord("u"):
            reset = command - ord("r")
            if reset & 1:
                raise ValueError("JTAGBitbang does not provide SRST; use reset_config trst_only.")
            self.value = (self.value & 7) | (0 if reset & 2 else 8)
            self.control.write(self.value)
        elif command in [ord("B"), ord("b")]:
            pass # Activity LED is not connected.
        elif command in [ord("Z"), ord("z")]:
            time.sleep(1e-3 if command == ord("Z") else 1e-6)
        else:
            raise ValueError(f"Unsupported remote_bitbang command: 0x{command:02x}.")

    def serve(self, connection):
        while True:
            commands = connection.recv(4096)
            if not commands:
                return
            for command in commands:
                if command == ord("Q"):
                    return
                response = self.process(command)
                if response is not None:
                    connection.sendall(response)

# Run ----------------------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="OpenOCD remote_bitbang server for LiteX JTAG CSRs.")
    parser.add_argument("--host",      default="localhost",       help="LiteX server host.")
    parser.add_argument("--port",      default=1234,    type=int, help="LiteX server port.")
    parser.add_argument("--timeout",   default=2.0,   type=float, help="LiteX server timeout in seconds.")
    parser.add_argument("--csr-csv",   default="csr.csv",         help="CSR CSV file.")
    parser.add_argument("--csr-name",  default="cpu_jtag_debug",  help="JTAG CSR prefix.")
    parser.add_argument("--bind-ip",   default="127.0.0.1",       help="OpenOCD bind address.")
    parser.add_argument("--bind-port", default=3335,    type=int, help="OpenOCD bind port.")
    args = parser.parse_args()

    try:
        with RemoteClient(host=args.host, port=args.port, csr_csv=args.csr_csv,
                          timeout=args.timeout, raise_on_timeout=True) as bus:
            bus.socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            jtag = JTAGRemoteBitbang(bus, csr_name=args.csr_name)
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
                server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                server.bind((args.bind_ip, args.bind_port))
                server.listen(1)
                print(f"JTAG remote_bitbang listening on {args.bind_ip}:{args.bind_port}.", flush=True)
                while True:
                    connection, address = server.accept()
                    print(f"Connected with {address[0]}:{address[1]}.", flush=True)
                    with connection:
                        connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
                        try:
                            jtag.serve(connection)
                        except (ConnectionError, ValueError) as error:
                            print(f"JTAG connection closed: {error}", flush=True)
    except KeyboardInterrupt:
        pass
    except (AttributeError, OSError, ValueError) as error:
        parser.exit(1, f"JTAG error: {error}\n")

if __name__ == "__main__":
    main()
