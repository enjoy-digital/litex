#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2019-2020 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2020 Antmicro <www.antmicro.com>
# SPDX-License-Identifier: BSD-2-Clause

import sys
import json
import argparse


def generate_dts(d, initrd_start=None, initrd_size=None, polling=False):

    kB = 1024
    mB = kB*1024

    cpu_name = d["constants"]["config_cpu_human_name"]

    aliases = {}

    # Header ---------------------------------------------------------------------------------------
    dts = """
/dts-v1/;

/ {
        #address-cells = <1>;
        #size-cells    = <1>;

"""

    # Boot Arguments -------------------------------------------------------------------------------
    default_initrd_start = {
        "mor1kx":               8*mB,
        "vexriscv smp-linux" : 16*mB,
    }
    default_initrd_size = 8*mB

    if initrd_start is None:
        initrd_start = default_initrd_start[cpu_name]

    if initrd_size is None:
        initrd_size = default_initrd_size

    dts += """
        chosen {{
            bootargs = "mem={main_ram_size_mb}M@0x{main_ram_base:x} rootwait console=liteuart earlycon=sbi root=/dev/ram0 init=/sbin/init swiotlb=32";
            linux,initrd-start = <0x{linux_initrd_start:x}>;
            linux,initrd-end   = <0x{linux_initrd_end:x}>;
        }};
""".format(
    main_ram_base      = d["memories"]["main_ram"]["base"],
    main_ram_size      = d["memories"]["main_ram"]["size"],
    main_ram_size_mb   = d["memories"]["main_ram"]["size"] // mB,
    linux_initrd_start = d["memories"]["main_ram"]["base"] + initrd_start,
    linux_initrd_end   = d["memories"]["main_ram"]["base"] + initrd_start + initrd_size)

    # CPU ------------------------------------------------------------------------------------------

    # VexRiscv-SMP
    if cpu_name == "vexriscv smp-linux":
        # cache description
        cache_desc = ""
        if "cpu_dcache_size" in d["constants"]:
            cache_desc += """
                d-cache-size = <{d_cache_size}>;
                d-cache-sets = <{d_cache_ways}>;
                d-cache-block-size = <{d_cache_block_size}>;
""".format(d_cache_size=d["constants"]["cpu_dcache_size"], d_cache_ways=d["constants"]["cpu_dcache_ways"], d_cache_block_size=d["constants"]["cpu_dcache_block_size"])
        if "cpu_icache_size" in d["constants"]:
            cache_desc += """
                i-cache-size = <{i_cache_size}>;
                i-cache-sets = <{i_cache_ways}>;
                i-cache-block-size = <{i_cache_block_size}>;
""".format(i_cache_size=d["constants"]["cpu_icache_size"], i_cache_ways=d["constants"]["cpu_icache_ways"], i_cache_block_size=d["constants"]["cpu_icache_block_size"])

        # tlb description
        tlb_desc = ""
        if "cpu_dtlb_size" in d["constants"]:
            tlb_desc += """
                d-tlb-size = <{d_tlb_size}>;
                d-tlb-sets = <{d_tlb_ways}>;
""".format(d_tlb_size=d["constants"]["cpu_dtlb_size"], d_tlb_ways=d["constants"]["cpu_dtlb_ways"])
        if "cpu_itlb_size" in d["constants"]:
            tlb_desc += """
                i-tlb-size = <{i_tlb_size}>;
                i-tlb-sets = <{i_tlb_ways}>;
""".format(i_tlb_size=d["constants"]["cpu_itlb_size"], i_tlb_ways=d["constants"]["cpu_itlb_ways"])

        cpus = range(int(d["constants"]["config_cpu_count"]))

        # topology
        cpu_map = ""
        if int(d["constants"]["config_cpu_count"]) > 1:
            cpu_map += """
            cpu-map {
                cluster0 {"""
            for cpu in cpus:
                cpu_map += """
                    core{cpu} {{
                        cpu = <&CPU{cpu}>;
                    }};""".format(cpu=cpu)
            cpu_map += """
                };
            };"""

        dts += """
        cpus {{
            #address-cells = <1>;
            #size-cells    = <0>;
            timebase-frequency = <{sys_clk_freq}>;
""".format(sys_clk_freq=d["constants"]["config_clock_frequency"])
        for cpu in cpus:
            dts += """
            CPU{cpu}: cpu@{cpu} {{
                device_type = "cpu";
                compatible = "riscv";
                riscv,isa = "{cpu_isa}";
                mmu-type = "riscv,sv32";
                reg = <{cpu}>;
                clock-frequency = <{sys_clk_freq}>;
                status = "okay";
                {cache_desc}
                {tlb_desc}
                L{irq}: interrupt-controller {{
                    #interrupt-cells = <0x00000001>;
                    interrupt-controller;
                    compatible = "riscv,cpu-intc";
                }};
            }};
""".format(cpu=cpu, irq=cpu, sys_clk_freq=d["constants"]["config_clock_frequency"], cpu_isa=d["constants"]["cpu_isa"], cache_desc=cache_desc, tlb_desc=tlb_desc)
        dts += """
            {cpu_map}
        }};
""".format(cpu_map=cpu_map)

    # mor1kx
    elif cpu_name == "mor1kx":
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
        memory@{main_ram_base:x} {{
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
    framebuffer_size = (d["constants"]["video_framebuffer_hres"] * d["constants"]["video_framebuffer_vres"] * 4))

        dts += """
        };
"""

    # SoC ------------------------------------------------------------------------------------------

    dts += """
        soc {{
            #address-cells = <1>;
            #size-cells    = <1>;
            bus-frequency  = <{sys_clk_freq}>;
            compatible = "simple-bus";
            interrupt-parent = <&intc0>;
            ranges;
""".format(sys_clk_freq=d["constants"]["config_clock_frequency"])

    # SoC Controller -------------------------------------------------------------------------------

    dts += """
            soc_ctrl0: soc_controller@{soc_ctrl_csr_base:x} {{
                compatible = "litex,soc-controller";
                reg = <0x{soc_ctrl_csr_base:x} 0xc>;
                status = "okay";
            }};
""".format(soc_ctrl_csr_base=d["csr_bases"]["ctrl"])

    # Interrupt Controller -------------------------------------------------------------------------

    if cpu_name == "vexriscv smp-linux":
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
            }};
""".format(
        plic_base   =d["memories"]["plic"]["base"],
        cpu_mapping =("\n" + " "*20).join(["&L{} 11 &L{} 9".format(cpu, cpu) for cpu in cpus]))

    elif cpu_name == "mor1kx":
        dts += """
            intc0: interrupt-controller {
                interrupt-controller;
                #interrupt-cells = <1>;
                compatible = "opencores,or1k-pic";
                status = "okay";
            };
"""
    # UART -----------------------------------------------------------------------------------------

    if "uart" in d["csr_bases"]:
        aliases["serial0"] = "liteuart0"
        dts += """
            liteuart0: serial@{uart_csr_base:x} {{
                compatible = "litex,liteuart";
                reg = <0x{uart_csr_base:x} 0x100>;
                {uart_interrupt}
                status = "okay";
            }};
""".format(
    uart_csr_base  = d["csr_bases"]["uart"],
    uart_interrupt = "" if polling else "interrupts = <{}>;".format(d["constants"]["uart_interrupt"]))

    # Ethernet -------------------------------------------------------------------------------------

    if "ethphy" in d["csr_bases"] and "ethmac" in d["csr_bases"]:
        dts += """
            mac0: mac@{ethmac_csr_base:x} {{
                compatible = "litex,liteeth";
                reg = <0x{ethmac_csr_base:x} 0x7c>,
                      <0x{ethphy_csr_base:x} 0x0a>,
                      <0x{ethmac_mem_base:x} 0x{ethmac_mem_size:x}>;
                tx-fifo-depth = <{ethmac_tx_slots}>;
                rx-fifo-depth = <{ethmac_rx_slots}>;
                {ethmac_interrupt}
                status = "okay";
            }};
""".format(
    ethphy_csr_base  = d["csr_bases"]["ethphy"],
    ethmac_csr_base  = d["csr_bases"]["ethmac"],
    ethmac_mem_base  = d["memories"]["ethmac"]["base"],
    ethmac_mem_size  = d["memories"]["ethmac"]["size"],
    ethmac_tx_slots  = d["constants"]["ethmac_tx_slots"],
    ethmac_rx_slots  = d["constants"]["ethmac_rx_slots"],
    ethmac_interrupt = "" if polling else "interrupts = <{}>;".format(d["constants"]["ethmac_interrupt"]))

   # SPI Flash -------------------------------------------------------------------------------------

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

    if "sdcore" in d["csr_bases"]:
        dts += """
            mmc0: mmc@{mmc_csr_base:x} {{
                compatible = "litex,mmc";
                reg = <0x{sdphy_csr_base:x} 0x100>,
                      <0x{sdcore_csr_base:x} 0x100>,
                      <0x{sdblock2mem:x} 0x100>,
                      <0x{sdmem2block:x} 0x100>,
                      <0x{sdirq:x} 0x100>;
                bus-width = <0x04>;
                {sdirq_interrupt}
                status = "okay";
            }};
""".format(
        mmc_csr_base    = d["csr_bases"]["sdphy"],
        sdphy_csr_base  = d["csr_bases"]["sdphy"],
        sdcore_csr_base = d["csr_bases"]["sdcore"],
        sdblock2mem     = d["csr_bases"]["sdblock2mem"],
        sdmem2block     = d["csr_bases"]["sdmem2block"],
        sdirq           = d["csr_bases"]["sdirq"],
        sdirq_interrupt = "" if polling else "interrupts = <{}>;".format(d["constants"]["sdirq_interrupt"])
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
                status = "disabled";
            }};
""".format(switches_csr_base=d["csr_bases"]["switches"])

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

    # Framebuffer ----------------------------------------------------------------------------------

    if "video_framebuffer" in d["csr_bases"]:
        framebuffer_base   = d["constants"]["video_framebuffer_base"]
        framebuffer_width  = d["constants"]["video_framebuffer_hres"]
        framebuffer_height = d["constants"]["video_framebuffer_vres"]
        dts += """
            framebuffer0: framebuffer@{framebuffer_base:x} {{
                compatible = "simple-framebuffer";
                reg = <0x{framebuffer_base:x} 0x{framebuffer_size:x}>;
                width = <{framebuffer_width}>;
                height = <{framebuffer_height}>;
                stride = <{framebuffer_stride}>;
                format = "a8b8g8r8";
            }};
""".format(
    framebuffer_base   = framebuffer_base,
    framebuffer_width  = framebuffer_width,
    framebuffer_height = framebuffer_height,
    framebuffer_size   = framebuffer_width * framebuffer_height * 4,
    framebuffer_stride = framebuffer_width * 4)

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
    mmcm_lock_timeout    = d["constants"]["mmcm_lock_timeout"],
    mmcm_drdy_timeout    = d["constants"]["mmcm_drdy_timeout"],
    sys_clk              = d["constants"]["config_clock_frequency"],
    divclk_divide_range  = (d["constants"]["divclk_divide_range_min"], d["constants"]["divclk_divide_range_max"]),
    clkfbout_mult_frange = (d["constants"]["clkfbout_mult_frange_min"], d["constants"]["clkfbout_mult_frange_max"]),
    vco_freq_range       = (d["constants"]["vco_freq_range_min"], d["constants"]["vco_freq_range_max"]),
    clkout_divide_range  = (d["constants"]["clkout_divide_range_min"], d["constants"]["clkout_divide_range_max"]),
    vco_margin           = d["constants"]["vco_margin"])
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
&leds {
        litex,ngpio = <4>;
        status = "okay";
};
"""

    if "switches" in d["csr_bases"]:
        dts += """
&switches {
        litex,ngpio = <4>;
        status = "okay";
};
"""

    return dts

def main():
    parser = argparse.ArgumentParser(description="LiteX's CSR JSON to Linux DTS generator")
    parser.add_argument("csr_json", help="CSR JSON file")
    parser.add_argument("--initrd-start", type=int,            help="Location of initrd in RAM (relative, default depends on CPU)")
    parser.add_argument("--initrd-size",  type=int,            help="Size of initrd (default=8MB)")
    parser.add_argument("--polling",      action="store_true", help="Force polling mode on peripherals")
    args = parser.parse_args()

    d = json.load(open(args.csr_json))
    r = generate_dts(d,
        initrd_start = args.initrd_start,
        initrd_size  = args.initrd_size,
        polling      = args.polling,
    )
    print(r)

if __name__ == "__main__":
    main()
