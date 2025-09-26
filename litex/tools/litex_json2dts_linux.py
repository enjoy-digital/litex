#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import os
import sys
import json
import argparse

from litex.gen.common import KILOBYTE, MEGABYTE

def generate_dts(d, initrd_start=None, initrd_size=None, initrd=None, root_device=None, polling=False):
    aliases = {}

    # CPU Parameters -------------------------------------------------------------------------------
    cpu_count  = int(d["constants"].get("config_cpu_count", 1))
    cpu_name   = d["constants"].get("config_cpu_name")
    cpu_family = d["constants"].get("config_cpu_family")
    cpu_isa    = d["constants"].get("config_cpu_isa", None)
    cpu_mmu    = d["constants"].get("config_cpu_mmu", None)

    # Header ---------------------------------------------------------------------------------------
    platform = d["constants"]["config_platform_name"]
    dts = """
/dts-v1/;

/ {{
        compatible = "litex,{platform}", "litex,soc";
        model = "{identifier}";
        #address-cells = <1>;
        #size-cells    = <1>;

""".format(
        platform=platform,
        identifier=d["constants"].get("identifier", platform),
    )

    # Boot Arguments -------------------------------------------------------------------------------

    # Init Ram Disk.
    default_initrd_start = {
        "or1k":   8 * MEGABYTE,
        "riscv": 16 * MEGABYTE,
    }
    default_initrd_size = 8 * MEGABYTE

    if initrd_start is None:
        initrd_start = default_initrd_start[cpu_family]

    if initrd_size is None:
        initrd_size = default_initrd_size

    if initrd == "enabled" or initrd is None:
        initrd_enabled = True
    elif initrd == "disabled":
        initrd_enabled = False
    else:
        initrd_enabled = True
        initrd_size = os.path.getsize(initrd)

    # Root Filesystem.
    if root_device is None:
        root_device = "ram0"

    # Ethernet IP Address.
    def get_eth_ip_config():
        def get_ip_address(prefix):
            return '.'.join(str(d["constants"][f"{prefix}{i+1}"]) for i in range(4))
        ip_config = ""
        if all(f"localip{i + 1}" in d["constants"] for i in range(4)):
            local_ip  = get_ip_address("localip")
            remote_ip = get_ip_address("remoteip")
            ip_config = f" ip={local_ip}:{remote_ip}:{remote_ip}:255.255.255.0::eth0:off:::"
        return ip_config

    # Bootargs Generation.
    dts += """
        chosen {{
            bootargs = "{console} {rootfs}{ip}";""".format(
    console = "console=liteuart earlycon=liteuart,0x{:x}".format(d["csr_bases"]["uart"]),
    rootfs  = "rootwait root=/dev/{}".format(root_device),
    ip      = get_eth_ip_config())

    if initrd_enabled is True:
        dts += """
            linux,initrd-start = <0x{linux_initrd_start:x}>;
            linux,initrd-end   = <0x{linux_initrd_end:x}>;""".format(
        linux_initrd_start = d["memories"]["main_ram"]["base"] + initrd_start,
        linux_initrd_end   = d["memories"]["main_ram"]["base"] + initrd_start + initrd_size)

    dts += """
        };
"""

    # Clocks ---------------------------------------------------------------------------------------

    for c in [c for c in d["constants"].keys() if c.endswith("config_clock_frequency")]:
        name = c[:len(c) - len("config_clock_frequency")] + "sys_clk"
        dts += """
        {name}: clock-{freq} {{
            compatible = "fixed-clock";
            #clock-cells = <0>;
            clock-frequency  = <{freq}>;
        }};
""".format(
            name=name,
            freq=d["constants"][c],
        )

    # CPU ------------------------------------------------------------------------------------------

    # RISC-V
    # ------
    if cpu_family == "riscv":

        def get_riscv_cpu_isa_base(cpu_isa):
            return cpu_isa[:5]

        def get_riscv_cpu_isa_extensions(cpu_isa, cpu_name):
            isa_extensions = set(["i"])

            # Collect common extensions.
            common_extensions = {'i', 'm', 'a', 'f', 'd', 'c'}
            for extension in cpu_isa[5:]:
                if extension in common_extensions:
                    isa_extensions.update({extension})

            # Add rocket-specific extensions.
            if cpu_name == "rocket":
                isa_extensions.update({"zicsr", "zifencei", "zihpm"})

            # Format extensions.
            return ", ".join(f"\"{extension}\"" for extension in sorted(isa_extensions))

        # Cache description.
        cache_desc = ""
        if "config_cpu_dcache_size" in d["constants"]:
            dcache_sets = int(d["constants"]["config_cpu_dcache_size"] /
                              d["constants"]["config_cpu_dcache_block_size"] /
                              d["constants"]["config_cpu_dcache_ways"])
            cache_desc += """
                d-cache-size = <{d_cache_size}>;
                d-cache-sets = <{d_cache_sets}>;
                d-cache-block-size = <{d_cache_block_size}>;
""".format(
    d_cache_size       = d["constants"]["config_cpu_dcache_size"],
    d_cache_sets       = dcache_sets,
    d_cache_block_size = d["constants"]["config_cpu_dcache_block_size"])
        if "config_cpu_icache_size" in d["constants"]:
            icache_sets = int(d["constants"]["config_cpu_icache_size"] /
                              d["constants"]["config_cpu_icache_block_size"] /
                              d["constants"]["config_cpu_icache_ways"])
            cache_desc += """
                i-cache-size = <{i_cache_size}>;
                i-cache-sets = <{i_cache_sets}>;
                i-cache-block-size = <{i_cache_block_size}>;
""".format(
    i_cache_size       = d["constants"]["config_cpu_icache_size"],
    i_cache_sets       = icache_sets,
    i_cache_block_size = d["constants"]["config_cpu_icache_block_size"])
        if "config_cpu_l2cache_size" in d["constants"]:
            cache_desc += """
                next-level-cache = <&cluster0_l2_cache>;
"""

        # TLB description.
        tlb_desc = ""
        if "config_cpu_dtlb_size" in d["constants"]:
            tlb_desc += """
                tlb-split;
                d-tlb-size = <{d_tlb_size}>;
                d-tlb-sets = <{d_tlb_ways}>;
""".format(
    d_tlb_size = d["constants"]["config_cpu_dtlb_size"],
    d_tlb_ways = d["constants"]["config_cpu_dtlb_ways"])
        if "config_cpu_itlb_size" in d["constants"]:
            tlb_desc += """
                i-tlb-size = <{i_tlb_size}>;
                i-tlb-sets = <{i_tlb_ways}>;
""".format(
    i_tlb_size = d["constants"]["config_cpu_itlb_size"],
    i_tlb_ways = d["constants"]["config_cpu_itlb_ways"])

        # Rocket specific attributes
        if (cpu_name == "rocket"):
            extra_attr = """
                hardware-exec-breakpoint-count = <1>;
                next-level-cache = <&memory>;
                riscv,pmpgranularity = <4>;
                riscv,pmpregions = <8>;
"""
        else:
            extra_attr = ""

        # CPU(s) Topology.
        cpu_map = ""
        if cpu_count > 1:
            cpu_map += """
            cpu-map {
                cluster0 {"""
            for cpu in range(cpu_count):
                cpu_map += """
                    core{cpu} {{
                        cpu = <&CPU{cpu}>;
                    }};""".format(cpu=cpu)
            cpu_map += """
                };
            };"""

        l2cache = ""
        if "config_cpu_l2cache_size" in d["constants"]:
            l2_size=d["constants"]["config_cpu_l2cache_size"]
            l2_ways=d["constants"]["config_cpu_l2cache_ways"]
            l2_block_size = d["constants"]["config_cpu_l2cache_block_size"]
            l2_sets = int(l2_size / l2_block_size / l2_ways)
            l2cache += """
	    cluster0_l2_cache: l2-cache0 {{
		compatible = "cache";
		cache-block-size = <{l2block}>;
		cache-level = <2>;
		cache-size = <{l2size}>;
		cache-sets = <{l2sets}>;
		cache-unified;
	    }};""".format(l2size=l2_size, l2block=l2_block_size, l2sets=l2_sets)

        dts += """
        cpus {{
            #address-cells = <1>;
            #size-cells    = <0>;
            timebase-frequency = <{sys_clk_freq}>;
""".format(sys_clk_freq=d["constants"]["config_clock_frequency"])
        for cpu in range(cpu_count):
            dts += """
            CPU{cpu}: cpu@{cpu} {{
                device_type = "cpu";
                compatible = "riscv";
                riscv,isa = "{cpu_isa}";
                riscv,isa-base = "{cpu_isa_base}";
                riscv,isa-extensions = {cpu_isa_extensions};
                mmu-type = "riscv,{cpu_mmu}";
                reg = <{cpu}>;
                clock-frequency = <{sys_clk_freq}>;
                status = "okay";
                {cache_desc}
                {tlb_desc}
                {extra_attr}
                L{irq}: interrupt-controller {{
                    #address-cells = <0>;
                    #interrupt-cells = <0x00000001>;
                    interrupt-controller;
                    compatible = "riscv,cpu-intc";
                }};
            }};
""".format(cpu=cpu, irq=cpu,
    sys_clk_freq       = d["constants"]["config_clock_frequency"],
    cpu_isa            = cpu_isa,
    cpu_isa_base       = get_riscv_cpu_isa_base(cpu_isa),                 # Required for kernel >= 6.6.0
    cpu_isa_extensions = get_riscv_cpu_isa_extensions(cpu_isa, cpu_name), # Required for kernel >= 6.6.0
    cpu_mmu            = cpu_mmu,
    cache_desc         = cache_desc,
    tlb_desc           = tlb_desc,
    extra_attr         = extra_attr)
        dts += """
            {cpu_map}
            {l2cache}
        }};
""".format(cpu_map=cpu_map, l2cache=l2cache)

    # Or1k
    # ----
    elif cpu_family == "or1k":
        dts += """
        cpus {{
            #address-cells = <1>;
            #size-cells = <0>;
            cpu@0 {{
                compatible = "opencores,or1200-rtlsvn481";
                reg = <0>;
                clock-frequency = <{sys_clk_freq}>;
            }};
        }};
""".format(sys_clk_freq=d["constants"]["config_clock_frequency"])

    # Memory ---------------------------------------------------------------------------------------

    dts += """
        memory: memory@{main_ram_base:x} {{
            device_type = "memory";
            reg = <0x{main_ram_base:x} 0x{main_ram_size:x}>;
        }};
""".format(
    main_ram_base = d["memories"]["main_ram"]["base"],
    main_ram_size = d["memories"]["main_ram"]["size"])

    if (("opensbi" in d["memories"]) or ("video_framebuffer" in d["csr_bases"])):
        dts += """
        reserved-memory {
            #address-cells = <1>;
            #size-cells    = <1>;
            ranges;
"""
        if "opensbi" in d["memories"]:
            dts += """
            opensbi@{opensbi_base:x} {{
                reg = <0x{opensbi_base:x} 0x{opensbi_size:x}>;
            }};
""".format(
    opensbi_base = d["memories"]["opensbi"]["base"],
    opensbi_size = d["memories"]["opensbi"]["size"])
        if "video_framebuffer" in d["csr_bases"]:
            dts += """
            framebuffer@{framebuffer_base:x} {{
                reg = <0x{framebuffer_base:x} 0x{framebuffer_size:x}>;
            }};
""".format(
    framebuffer_base = d["constants"]["video_framebuffer_base"],
    framebuffer_size = (d["constants"]["video_framebuffer_hres"] * d["constants"]["video_framebuffer_vres"] * (d["constants"]["video_framebuffer_depth"]//8)))

        dts += """
        };
"""

    # Voltage Regulator for LiteSDCard (if applicable) --------------------------------------------
    if "sdcard" in d["csr_bases"]:
        dts += """
        vreg_mmc: vreg_mmc {{
            compatible = "regulator-fixed";
            regulator-name = "vreg_mmc";
            regulator-min-microvolt = <3300000>;
            regulator-max-microvolt = <3300000>;
            regulator-always-on;
        }};
""".format()

    # SoC ------------------------------------------------------------------------------------------

    dts += """
        soc {{
            #address-cells = <1>;
            #size-cells    = <1>;
            compatible = "simple-bus";
            interrupt-parent = <&intc0>;
            ranges;
""".format()

    # SoC Controller -------------------------------------------------------------------------------

    dts += """
            soc_ctrl0: soc_controller@{soc_ctrl_csr_base:x} {{
                compatible = "litex,soc-controller";
                reg = <0x{soc_ctrl_csr_base:x} 0xc>;
                status = "okay";
            }};
""".format(soc_ctrl_csr_base=d["csr_bases"]["ctrl"])

    # Interrupt Controller -------------------------------------------------------------------------

    if (cpu_family == "riscv") and "clint" in d["memories"]:
        # FIXME  : L4 definitiion?
        # CHECKME: interrupts-extended.
        dts += """
            lintc0: clint@{clint_base:x} {{
                compatible = "riscv,clint0";
                interrupts-extended = <
                    {cpu_mapping}>;
                reg = <0x{clint_base:x} 0x10000>;
                reg-names = "control";
            }};
""".format(
        clint_base  = d["memories"]["clint"]["base"],
        cpu_mapping = ("\n" + " "*20).join(["&L{} 3 &L{} 7".format(cpu, cpu) for cpu in range(cpu_count)]))
    if cpu_family == "riscv":
        if cpu_name == "rocket":
            extra_attr = """
                reg-names = "control";
                riscv,max-priority = <7>;
"""
        else:
            extra_attr = ""

        dts += """
            intc0: interrupt-controller@{plic_base:x} {{
                compatible = "sifive,fu540-c000-plic", "sifive,plic-1.0.0";
                reg = <0x{plic_base:x} 0x400000>;
                #address-cells = <0>;
                #interrupt-cells = <1>;
                interrupt-controller;
                interrupts-extended = <
                    {cpu_mapping}>;
                riscv,ndev = <32>;
                {extra_attr}
            }};
""".format(
        plic_base   = d["memories"]["plic"]["base"],
        cpu_mapping = ("\n" + " "*20).join(["&L{} 11 &L{} 9".format(cpu, cpu) for cpu in range(cpu_count)]),
        extra_attr  = extra_attr)

    elif cpu_family == "or1k":
        dts += """
            intc0: interrupt-controller {
                interrupt-controller;
                #interrupt-cells = <1>;
                compatible = "opencores,or1k-pic";
                status = "okay";
            };
"""
    if (cpu_family == "riscv") and (cpu_name == "rocket"):
        dts += """
            dbg_ctl: debug-controller@0 {{
                compatible = "sifive,debug-013", "riscv,debug-013";
                interrupts-extended = <
                    {cpu_mapping}>;
                reg = <0x0 0x1000>;
                reg-names = "control";
            }};
            err_dev: error-device@3000 {{
                compatible = "sifive,error0";
                reg = <0x3000 0x1000>;
            }};
            ext_it: external-interrupts {{
                interrupts = <1 2 3 4 5 6 7 8>;
            }};
            rom: rom@10000 {{
                compatible = "sifive,rom0";
                reg = <0x10000 0x10000>;
                reg-names = "mem";
            }};
""".format(
        cpu_mapping =("\n" + " "*20).join(["&L{} 0x3F".format(cpu) for cpu in range(cpu_count)]))
    # UART -----------------------------------------------------------------------------------------

    if "uart" in d["csr_bases"]:
        aliases["serial0"] = "liteuart0"
        it_incr = {True: 1, False: 0}[cpu_name == "rocket"]
        dts += """
            liteuart0: serial@{uart_csr_base:x} {{
                compatible = "litex,liteuart";
                reg = <0x{uart_csr_base:x} 0x100>;
                {uart_interrupt}
                status = "okay";
            }};
""".format(
    uart_csr_base  = d["csr_bases"]["uart"],
    uart_interrupt = "" if polling else "interrupts = <{}>;".format(int(d["constants"]["uart_interrupt"]) + it_incr))

    # Ethernet -------------------------------------------------------------------------------------
    for i in [''] + list(range(0, 10)):
        idx = (0 if i == '' else i)
        ethphy_name = "ethphy" + str(i)
        ethmac_name = "ethmac" + str(i)
        it_incr = {True: 1, False: 0}[cpu_name == "rocket"]
        if ethphy_name in d["csr_bases"] and ethmac_name in d["csr_bases"]:
            dts += """
            mac{idx}: mac@{ethmac_csr_base:x} {{
                compatible = "litex,liteeth";
                reg = <0x{ethmac_csr_base:x} 0x7c>,
                      <0x{ethphy_csr_base:x} 0x0a>,
                      <0x{ethmac_mem_base:x} 0x{ethmac_mem_size:x}>;
                reg-names = "mac", "mdio", "buffer";
                litex,rx-slots = <{ethmac_rx_slots}>;
                litex,tx-slots = <{ethmac_tx_slots}>;
                litex,slot-size = <{ethmac_slot_size}>;
                {ethmac_interrupt}
                {local_mac_addr}
                status = "okay";
            }};
""".format(
    idx = idx,
    ethphy_csr_base  = d["csr_bases"][ethphy_name],
    ethmac_csr_base  = d["csr_bases"][ethmac_name],
    ethmac_mem_base  = d["memories"][ethmac_name]["base"],
    ethmac_mem_size  = d["memories"][ethmac_name]["size"],
    ethmac_rx_slots  = d["constants"][ethmac_name + "_rx_slots"],
    ethmac_tx_slots  = d["constants"][ethmac_name + "_tx_slots"],
    ethmac_slot_size = d["constants"][ethmac_name + "_slot_size"],
    ethmac_interrupt = "" if polling else "interrupts = <{}>;".format(int(d["constants"][ethmac_name + "_interrupt"]) + it_incr),
    local_mac_addr   = "" if not "macaddr1" in d["constants"] else "local-mac-address = [{mac_addr}];".format(
        mac_addr     = "{a1:02X} {a2:02X} {a3:02X} {a4:02X} {a5:02X} {a6:02X}".format(
            a1       = d["constants"]["macaddr1"],
            a2       = d["constants"]["macaddr2"],
            a3       = d["constants"]["macaddr3"],
            a4       = d["constants"]["macaddr4"],
            a5       = d["constants"]["macaddr5"],
            a6       = d["constants"]["macaddr6"])))

    # USB OHCI -------------------------------------------------------------------------------------

    if "usb_ohci_ctrl" in d["memories"]:
        dts += """
            usb0: usb@{usb_ohci_mem_base:x} {{
                compatible = "generic-ohci";
                reg = <0x{usb_ohci_mem_base:x} 0x1000>;
                {usb_ohci_interrupt}
                status = "okay";
            }};
""".format(
    usb_ohci_mem_base  = d["memories"]["usb_ohci_ctrl"]["base"],
    usb_ohci_interrupt = "" if polling else "interrupts = <{}>;".format(16)) # FIXME

    # SPI Flash ------------------------------------------------------------------------------------

    if "spiflash" in d["csr_bases"]:
        aliases["spiflash"] = "litespiflash"
        dts += """
            litespiflash: spiflash@{spiflash_csr_base:x} {{
                #address-cells = <1>;
                #size-cells    = <1>;
                compatible = "litex,spiflash";
                reg = <0x{spiflash_csr_base:x} 0x100>;
                flash: flash@0 {{
                    compatible = "jedec,spi-nor";
                    reg = <0x0 0x{spiflash_size:x}>;
                }};
            }};
""".format(spiflash_csr_base=d["csr_bases"]["spiflash"], spiflash_size=d["memories"]["spiflash"]["size"])

    # SPI-SDCard -----------------------------------------------------------------------------------

    if "spisdcard" in d["csr_bases"]:
        aliases["sdcard0"] = "litespisdcard0"
        dts += """
            litespisdcard0: spi@{spisdcard_csr_base:x} {{
                compatible = "litex,litespi";
                reg = <0x{spisdcard_csr_base:x} 0x100>;
                status = "okay";

                litespi,max-bpw = <8>;
                litespi,sck-frequency = <1500000>;
                litespi,num-cs = <1>;

                #address-cells = <1>;
                #size-cells    = <0>;

                mmc-slot@0 {{
                    compatible = "mmc-spi-slot";
                    reg = <0>;
                    voltage-ranges = <3300 3300>;
                    spi-max-frequency = <1500000>;
                    status = "okay";
                    }};
            }};
""".format(spisdcard_csr_base=d["csr_bases"]["spisdcard"])


    # SDCard ---------------------------------------------------------------------------------------

    if "sdcard" in d["csr_bases"]:
        dts += """
            mmc0: mmc@{mmc_csr_base:x} {{
                compatible = "litex,mmc";
                reg = <0x{sdcard_phy_csr_base:x} 0x{sdcard_phy_csr_size:x}>,
                      <0x{sdcard_core_csr_base:x} 0x{sdcard_core_csr_size:x}>,
                      <0x{sdcard_block2mem:x} 0x{sdcard_block2mem_size:x}>,
                      <0x{sdcard_mem2block:x} 0x{sdcard_mem2block_size:x}>,
                      <0x{sdcard_irq:x} 0x100>;
                reg-names = "phy", "core", "reader", "writer", "irq";
                clocks = <&sys_clk>;
                vmmc-supply = <&vreg_mmc>;
                bus-width = <0x04>;
                {sdcard_irq_interrupt}
                status = "okay";
            }};
""".format(
        mmc_csr_base         = d["csr_bases"]["sdcard"],
        sdcard_phy_csr_base  = d["csr_registers"]["sdcard_phy_card_detect"]['addr'],
        sdcard_phy_csr_size  = d["csr_registers"]["sdcard_core_cmd_argument"]['addr'] - d["csr_registers"]["sdcard_phy_card_detect"]['addr'],
        sdcard_core_csr_base = d["csr_registers"]["sdcard_core_cmd_argument"]['addr'],
        sdcard_core_csr_size = d["csr_registers"]["sdcard_block2mem_dma_base"]['addr'] - d["csr_registers"]["sdcard_core_cmd_argument"]['addr'],
        sdcard_block2mem     = d["csr_registers"]["sdcard_block2mem_dma_base"]['addr'],
        sdcard_block2mem_size = d["csr_registers"]["sdcard_mem2block_dma_base"]['addr'] - d["csr_registers"]["sdcard_block2mem_dma_base"]['addr'],
        sdcard_mem2block     = d["csr_registers"]["sdcard_mem2block_dma_base"]['addr'],
        sdcard_mem2block_size = d["csr_registers"]["sdcard_ev_status"]['addr'] - d["csr_registers"]["sdcard_mem2block_dma_base"]['addr'],
        sdcard_irq           = d["csr_registers"]["sdcard_ev_status"]['addr'],
        sdcard_irq_interrupt = "" if polling else "interrupts = <{}>;".format(d["constants"]["sdcard_interrupt"])
)
    # Leds -----------------------------------------------------------------------------------------

    if "leds" in d["csr_bases"]:
        dts += """
            leds: gpio@{leds_csr_base:x} {{
                compatible = "litex,gpio";
                reg = <0x{leds_csr_base:x} 0x4>;
                gpio-controller;
                #gpio-cells = <2>;
                litex,direction = "out";
                status = "disabled";
            }};
""".format(leds_csr_base=d["csr_bases"]["leds"])

    # RGB Leds -------------------------------------------------------------------------------------

    for name in ["rgb_led_r0", "rgb_led_g0", "rgb_led_b0"]:
        if name in d["csr_bases"]:
            dts += """
            {pwm_name}: pwm@{pwm_csr_base:x} {{
                compatible = "litex,pwm";
                reg = <0x{pwm_csr_base:x} 0x24>;
                clock = <100000000>;
                #pwm-cells = <3>;
                status = "okay";
            }};
""".format(pwm_name=name, pwm_csr_base=d["csr_bases"][name])

    # Switches -------------------------------------------------------------------------------------

    if "switches" in d["csr_bases"]:
        dts += """
            switches: gpio@{switches_csr_base:x} {{
                compatible = "litex,gpio";
                reg = <0x{switches_csr_base:x} 0x4>;
                gpio-controller;
                #gpio-cells = <2>;
                litex,direction = "in";
                {switches_interrupt}
                status = "disabled";
            }};
""".format(
    switches_csr_base  = d["csr_bases"]["switches"],
	switches_interrupt = "" if polling else "interrupts = <{}>;".format(d["constants"]["switches_interrupt"]))

    # SPI ------------------------------------------------------------------------------------------

    if "spi" in d["csr_bases"]:
        aliases["spi0"] = "litespi0"
        dts += """
            litespi0: spi@{spi_csr_base:x} {{
                compatible = "litex,litespi";
                reg = <0x{spi_csr_base:x} 0x100>;
                status = "okay";

                litespi,max-bpw = <8>;
                litespi,sck-frequency = <1000000>;
                litespi,num-cs = <1>;

                #address-cells = <1>;
                #size-cells    = <0>;

                spidev0: spidev@0 {{
                    compatible = "linux,spidev";
                    reg = <0>;
                    spi-max-frequency = <1000000>;
                    status = "okay";
                }};
            }};
""".format(spi_csr_base=d["csr_bases"]["spi"])

    # I2C ------------------------------------------------------------------------------------------

    if "i2c0" in d["csr_bases"]:
        dts += """
            i2c0: i2c@{i2c0_csr_base:x} {{
                compatible = "litex,i2c";
                reg = <0x{i2c0_csr_base:x} 0x5>;
                #address-cells = <1>;
                #size-cells = <0>;
                status = "okay";
            }};
""".format(i2c0_csr_base=d["csr_bases"]["i2c0"])

    # XADC -----------------------------------------------------------------------------------------

    if "xadc" in d["csr_bases"]:
        dts += """
            hwmon0: xadc@{xadc_csr_base:x} {{
                compatible = "litex,hwmon-xadc";
                reg = <0x{xadc_csr_base:x} 0x20>;
                status = "okay";
            }};
""".format(xadc_csr_base=d["csr_bases"]["xadc"])

    # CAN ------------------------------------------------------------------------------------------

    for mem in d["memories"]:
        if "can" in mem:
            dts += """
            {name}: can@{can_mem_base:x} {{
                compatible = "ctu,ctucanfd";
                reg = <0x{can_mem_base:x} 0x{can_mem_size:x}>;
                interrupt-parent = <&intc0>;
                interrupts = <{can_interrupt}>;
                clocks = <&sys_clk>;
                status = "okay";
            }};
""".format(name=mem,
                can_mem_base=d["memories"][mem]["base"],
                can_mem_size=d["memories"][mem]["size"],
                can_interrupt = int(d["constants"][f"{mem}_interrupt"]),
            )

    # Framebuffer ----------------------------------------------------------------------------------

    if "video_framebuffer" in d["csr_bases"]:
        framebuffer_base   = d["constants"]["video_framebuffer_base"]
        framebuffer_width  = d["constants"]["video_framebuffer_hres"]
        framebuffer_height = d["constants"]["video_framebuffer_vres"]
        framebuffer_depth  = d["constants"]["video_framebuffer_depth"]
        framebuffer_format = "a8b8g8r8"
        if (framebuffer_depth == 16):
            framebuffer_format = "r5g6b5"
        dts += """
            framebuffer0: framebuffer@{framebuffer_base:x} {{
                compatible = "simple-framebuffer";
                reg = <0x{framebuffer_base:x} 0x{framebuffer_size:x}>;
                width = <{framebuffer_width}>;
                height = <{framebuffer_height}>;
                stride = <{framebuffer_stride}>;
                format = "{framebuffer_format}";
            }};
""".format(
    framebuffer_base   = framebuffer_base,
    framebuffer_width  = framebuffer_width,
    framebuffer_height = framebuffer_height,
    framebuffer_size   = framebuffer_width * framebuffer_height * (framebuffer_depth//8),
    framebuffer_stride = framebuffer_width * (framebuffer_depth//8),
    framebuffer_format = framebuffer_format)

    # ICAP Bitstream -------------------------------------------------------------------------------

    if "icap_bit" in d["csr_bases"]:
        dts += """
            fpga0: icap@{icap_csr_base:x} {{
                compatible = "litex,fpga-icap";
                reg = <0x{icap_csr_base:x} 0x14>;
                status = "okay";
            }};
""".format(icap_csr_base=d["csr_bases"]["icap_bit"])

    # Clocking  ------------------------------------------------------------------------------------

    def add_clkout(clkout_nr, clk_f, clk_p, clk_dn, clk_dd, clk_margin, clk_margin_exp):
        return """
                CLKOUT{clkout_nr}: CLKOUT{clkout_nr} {{
                    compatible = "litex,clk";
                    #clock-cells = <0>;
                    clock-output-names = "CLKOUT{clkout_nr}";
                    reg = <{clkout_nr}>;
                    litex,clock-frequency = <{clk_f}>;
                    litex,clock-phase = <{clk_p}>;
                    litex,clock-duty-num = <{clk_dn}>;
                    litex,clock-duty-den = <{clk_dd}>;
                    litex,clock-margin = <{clk_margin}>;
                    litex,clock-margin-exp = <{clk_margin_exp}>;
                }};
""".format(
    clkout_nr      = clkout_nr,
    clk_f          = clk_f,
    clk_p          = clk_p,
    clk_dn         = clk_dn,
    clk_dd         = clk_dd,
    clk_margin     = clk_margin,
    clk_margin_exp = clk_margin_exp)

    if "mmcm" in d["csr_bases"]:
        nclkout = d["constants"]["nclkout"]
        dts += """
            clk0: clk@{mmcm_csr_base:x} {{
                compatible = "litex,clk";
                reg = <0x{mmcm_csr_base:x} 0x100>;
                #clock-cells = <1>;
                #address-cells = <1>;
                #size-cells = <0>;
                clock-output-names =
""".format(mmcm_csr_base=d["csr_bases"]["mmcm"])
        for clkout_nr in range(nclkout - 1):
            dts += """
                    "CLKOUT{clkout_nr}",
""".format(clkout_nr=clkout_nr)
        dts += """
                    "CLKOUT{nclkout}";
""".format(nclkout=(nclkout - 1))
        dts += """
                litex,lock-timeout = <{mmcm_lock_timeout}>;
                litex,drdy-timeout = <{mmcm_drdy_timeout}>;
                litex,sys-clock-frequency = <{sys_clk}>;
                litex,divclk-divide-min = <{divclk_divide_range[0]}>;
                litex,divclk-divide-max = <{divclk_divide_range[1]}>;
                litex,clkfbout-mult-min = <{clkfbout_mult_frange[0]}>;
                litex,clkfbout-mult-max = <{clkfbout_mult_frange[1]}>;
                litex,vco-freq-min = <{vco_freq_range[0]}>;
                litex,vco-freq-max = <{vco_freq_range[1]}>;
                litex,clkout-divide-min = <{clkout_divide_range[0]}>;
                litex,clkout-divide-max = <{clkout_divide_range[1]}>;
                litex,vco-margin = <{vco_margin}>;
""".format(
    mmcm_lock_timeout    =  d["constants"]["mmcm_lock_timeout"],
    mmcm_drdy_timeout    =  d["constants"]["mmcm_drdy_timeout"],
    sys_clk              =  d["constants"]["config_clock_frequency"],
    divclk_divide_range  = (d["constants"]["divclk_divide_range_min"], d["constants"]["divclk_divide_range_max"]),
    clkfbout_mult_frange = (d["constants"]["clkfbout_mult_frange_min"], d["constants"]["clkfbout_mult_frange_max"]),
    vco_freq_range       = (d["constants"]["vco_freq_range_min"], d["constants"]["vco_freq_range_max"]),
    clkout_divide_range  = (d["constants"]["clkout_divide_range_min"], d["constants"]["clkout_divide_range_max"]),
    vco_margin           =  d["constants"]["vco_margin"])
        for clkout_nr in range(nclkout):
            dts += add_clkout(clkout_nr,
                d["constants"]["clkout_def_freq"],
                d["constants"]["clkout_def_phase"],
                d["constants"]["clkout_def_duty_num"],
                d["constants"]["clkout_def_duty_den"],
                d["constants"]["clkout_margin"],
                d["constants"]["clkout_margin_exp"])
        dts += """
            };"""

    dts += """
        };
"""

    # Aliases --------------------------------------------------------------------------------------

    if aliases:
        dts += """
        aliases {
"""
        for alias in aliases:

            dts += """
                {} = &{};
""".format(alias, aliases[alias])

        dts += """
        };
"""

    dts += """
};
"""

    # Leds & switches ------------------------------------------------------------------------------

    if "leds" in d["csr_bases"]:
        dts += """
&leds {{
        litex,ngpio = <{ngpio}>;
        status = "okay";
}};
""".format(ngpio=d["constants"].get('leds_ngpio', 4))

    if "switches" in d["csr_bases"]:
        dts += """
&switches {{
        litex,ngpio = <{ngpio}>;
        status = "okay";
}};
""".format(ngpio=d["constants"].get('switches_ngpio', 4))

    return dts

def main():

    parser = argparse.ArgumentParser(description="LiteX's CSR JSON to Linux DTS generator")
    parser.add_argument("csr_json", help="CSR JSON file")
    parser.add_argument("--initrd-start", type=int,            help="Location of initrd in RAM (relative, default depends on CPU).")
    parser.add_argument("--initrd-size",  type=int,            help="Size of initrd (default=8MB).")
    parser.add_argument("--initrd",       type=str,            help="Supports arguments 'enabled', 'disabled' or a file name. Set to 'disabled' if you use a kernel built in rootfs or have your rootfs on an SD card partition. If a file name is provied the size of the file will be used instead of --initrd-size. (default=enabled).")
    parser.add_argument("--root-device",  type=str,            help="Device that has our rootfs, if using initrd use the default. For SD card's use something like mmcblk0p3. (default=ram0).")
    parser.add_argument("--polling",      action="store_true", help="Force polling mode on peripherals.")
    args = parser.parse_args()

    d = json.load(open(args.csr_json))
    r = generate_dts(d,
        initrd_start = args.initrd_start,
        initrd_size  = args.initrd_size,
        initrd       = args.initrd,
        root_device  = args.root_device,
        polling      = args.polling,
    )
    print(r)

if __name__ == "__main__":
    main()
