#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import json
import shlex
import shutil
import subprocess

from litex.soc.integration.soc import SoCRegion, auto_int


# Helpers ------------------------------------------------------------------------------------------

def qemu_xlen(cpu_variant):
    return 64 if cpu_variant == "rv64" else 32


def qemu_default_binary(cpu_variant):
    name = "qemu-system-riscv{}".format(qemu_xlen(cpu_variant))
    repo_binary = os.path.abspath(os.path.join(
        os.path.dirname(__file__),
        "..", "..", "..", "..",
        "build", "qemu-litex", "bin",
        name,
    ))
    return repo_binary if os.path.exists(repo_binary) else name


def qemu_resolve_binary(binary, cpu_variant):
    binary = binary or qemu_default_binary(cpu_variant)
    return os.path.abspath(binary) if os.path.exists(binary) else binary


def qemu_binary(args):
    if hasattr(args, "qemu_binary_resolved"):
        return args.qemu_binary_resolved
    return qemu_resolve_binary(args.qemu_binary, qemu_variant(args))


def qemu_variant(args):
    return "rv32" if args.cpu_variant in [None, "standard"] else args.cpu_variant


def qemu_shared_ram_default_path(args):
    output_dir = args.output_dir or os.path.join("build", "sim")
    return os.path.abspath(os.path.join(output_dir, "qemu-main-ram.bin"))


def qemu_shared_ram_path(args):
    return os.path.abspath(args.qemu_shared_ram_path or qemu_shared_ram_default_path(args))


def qemu_prepare_shared_ram_file(path, size, init_data=None, data_width=32):
    bytes_per_data = data_width//8

    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.truncate(size)

    if not init_data:
        return

    with open(path, "r+b") as f:
        for n, data in enumerate(init_data):
            offset = n*bytes_per_data
            if offset + bytes_per_data > size:
                raise ValueError("RAM init data is larger than QEMU shared RAM.")
            f.seek(offset)
            f.write(int(data).to_bytes(bytes_per_data, byteorder="little"))


# Arguments ----------------------------------------------------------------------------------------

def qemu_add_args(parser):
    parser.add_argument("--qemu-bind",         default="127.0.0.1", help="Bind address for the QEMU transaction bridge.")
    parser.add_argument("--qemu-port",         default=1235, type=int, help="TCP port for the QEMU transaction bridge.")
    parser.add_argument("--qemu-binary",       default=None, help="QEMU binary to launch (default: qemu-system-riscv32/64).")
    parser.add_argument("--qemu-firmware",     default=None, help="Firmware/BIOS passed to QEMU -bios; use 'none' to disable.")
    parser.add_argument("--qemu-kernel",       default=None, help="Kernel image passed to QEMU -kernel.")
    parser.add_argument("--qemu-dtb",          default=None, help="Device tree blob passed to QEMU -dtb.")
    parser.add_argument("--qemu-initrd",       default=None, help="Initrd image passed to QEMU -initrd.")
    parser.add_argument("--qemu-append",       default=None, help="Kernel command line passed to QEMU -append.")
    parser.add_argument("--qemu-ram-size",     default=None, type=auto_int, help="QEMU RAM size in bytes.")
    parser.add_argument("--qemu-shared-ram-path", default=None,        help="Shared RAM backing file used with QEMU integrated main RAM.")
    parser.add_argument("--qemu-extra-args",   default="", help="Extra arguments appended to the QEMU command line.")
    parser.add_argument("--qemu-wait-timeout", default=120.0, type=float, help="Seconds to wait for the QEMU transaction bridge before launching QEMU; <= 0 waits forever.")
    parser.add_argument("--qemu-irq-poll-us",  default=1000, type=int, help="QEMU-side LiteX IRQ polling interval in microseconds; 0 disables polling.")
    parser.add_argument("--qemu-no-run",       action="store_true", help="Do not auto-launch QEMU when using --cpu-type=qemu.")


def qemu_configure(args, parser, soc_kwargs):
    qemu_enabled = soc_kwargs.get("cpu_type", None) == "qemu"
    args.qemu_shared_ram_enabled = (
        qemu_enabled and
        bool(args.integrated_main_ram_size)
    )
    args.qemu_shared_ram_path_resolved = qemu_shared_ram_path(args)
    args.qemu_binary_resolved          = qemu_resolve_binary(args.qemu_binary, qemu_variant(args))
    if args.qemu_shared_ram_enabled:
        if args.qemu_ram_size is not None and args.qemu_ram_size != args.integrated_main_ram_size:
            parser.error("--qemu-ram-size must match --integrated-main-ram-size when shared RAM is enabled.")
        soc_kwargs["integrated_main_ram_size"] = 0
    return qemu_enabled


# Simulation Modules -------------------------------------------------------------------------------

def qemu_add_sim_modules(sim_config, args, parser):
    interfaces = ["qemu_axi", "qemu_irq", "qemu_reset"]
    module_args = {
        "bind" : args.qemu_bind,
        "port" : args.qemu_port,
    }
    if args.qemu_shared_ram_enabled:
        interfaces.append("qemu_axi_shared_ram")
        module_args.update({
            "path" : args.qemu_shared_ram_path_resolved,
            "size" : args.integrated_main_ram_size,
        })
    sim_config.add_module("qemu_axi", interfaces, clocks="sys_clk", args=module_args)
    if not args.qemu_no_run:
        binary = qemu_binary(args)
        if shutil.which(binary) is None and not os.path.exists(binary):
            parser.error("{} not found; install a patched QEMU or use --qemu-no-run.".format(binary))


def qemu_add_shared_ram(soc, args, init_data=None, data_width=32):
    from litex.soc.cores.cpu.qemu.core import QEMUSharedRAM

    qemu_prepare_shared_ram_file(
        path       = args.qemu_shared_ram_path_resolved,
        size       = args.integrated_main_ram_size,
        init_data  = init_data,
        data_width = data_width,
    )
    soc.add_module(name="main_ram", module=QEMUSharedRAM(soc.platform))
    soc.bus.add_slave(name="main_ram", slave=soc.main_ram.bus, region=SoCRegion(
        origin = soc.mem_map["main_ram"],
        size   = args.integrated_main_ram_size,
        mode   = "rwx",
    ))
    soc.integrated_main_ram_size = args.integrated_main_ram_size


# QEMU Command -------------------------------------------------------------------------------------

def qemu_machine_arg(soc, args):
    def region_origin(name, default=0):
        if name in soc.bus.regions:
            return soc.bus.regions[name].origin
        return soc.mem_map.get(name, default)

    def region_size(name, default=0):
        if name in soc.bus.regions:
            return soc.bus.regions[name].size
        return default

    def bridge_region():
        if soc.cpu.io_regions:
            return sorted(soc.cpu.io_regions.items())[0]
        return region_origin("csr"), region_size("csr")

    bridge_base, bridge_size = bridge_region()
    props = [
        "litex-sim",
        "xlen={}".format(qemu_xlen(qemu_variant(args))),
        "bridge-host={}".format(args.qemu_bind),
        "bridge-port={}".format(args.qemu_port),
        "bridge-base=0x{:x}".format(bridge_base),
        "bridge-size=0x{:x}".format(bridge_size),
        "irq-poll-us={}".format(args.qemu_irq_poll_us),
        "reset-addr=0x{:x}".format(getattr(soc.cpu, "reset_address", region_origin("rom"))),
        "rom-base=0x{:x}".format(region_origin("rom")),
        "sram-base=0x{:x}".format(region_origin("sram")),
        "main-ram-base=0x{:x}".format(region_origin("main_ram")),
        "clint-base=0x{:x}".format(region_origin("clint")),
        "clint-size=0x{:x}".format(region_size("clint", 0x1_0000)),
        "plic-base=0x{:x}".format(region_origin("plic")),
        "plic-size=0x{:x}".format(region_size("plic", 0x40_0000)),
        "timebase-freq={}".format(getattr(soc, "sys_clk_freq", 1000000)),
        "csr-base=0x{:x}".format(region_origin("csr")),
        "csr-size=0x{:x}".format(region_size("csr")),
    ]
    if getattr(args, "qemu_shared_ram_enabled", False):
        props.append("memory-backend=litex_main_ram")
    return ",".join(props)


def qemu_command(builder, soc, args):
    qemu_ram_size = args.qemu_ram_size or args.integrated_main_ram_size or 64*1024*1024
    bios          = args.qemu_firmware
    if bios is None:
        bios = args.rom_init or builder.get_bios_filename()

    cmd = [qemu_binary(args)]
    if getattr(args, "qemu_shared_ram_enabled", False):
        cmd += [
            "-object",
            "memory-backend-file,id=litex_main_ram,mem-path={},size={},share=on".format(
                args.qemu_shared_ram_path_resolved,
                qemu_ram_size,
            ),
        ]
    cmd += [
        "-M", qemu_machine_arg(soc, args),
        "-m", "{}B".format(qemu_ram_size),
        "-nographic",
        "-serial", "none",
        "-monitor", "none",
    ]
    if bios:
        cmd += ["-bios", bios]
    if args.qemu_kernel:
        cmd += ["-kernel", args.qemu_kernel]
    if args.qemu_dtb:
        cmd += ["-dtb", args.qemu_dtb]
    if args.qemu_initrd:
        cmd += ["-initrd", args.qemu_initrd]
    if args.qemu_append:
        cmd += ["-append", args.qemu_append]
    if args.qemu_extra_args:
        cmd += shlex.split(args.qemu_extra_args)
    return cmd


def qemu_spawn_when_bridge_ready(cmd, host, port, timeout):
    waiter = r"""
import os
import sys
import json
import time
import socket

cmd = json.loads(sys.argv[1])
host = sys.argv[2]
port = int(sys.argv[3])
timeout = float(sys.argv[4])
deadline = None if timeout <= 0 else time.time() + timeout

while True:
    try:
        s = socket.create_connection((host, port), timeout=0.25)
        s.close()
        break
    except OSError:
        if deadline is not None and time.time() >= deadline:
            print("[litex_sim] ERROR: timed out waiting for QEMU transaction bridge", file=sys.stderr)
            sys.exit(1)
        time.sleep(0.05)

print("[litex_sim] Starting QEMU: {}".format(" ".join(cmd)))
os.execvp(cmd[0], cmd)
"""
    return subprocess.Popen([
        sys.executable,
        "-c", waiter,
        json.dumps(cmd),
        host,
        str(port),
        str(timeout),
    ])
