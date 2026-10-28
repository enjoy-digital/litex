# Firmware

LiteX is normally used with custom firmware running on the Soft-CPU inside the gateware (although in some cases it can be used with software running on a computer connected to the FPGA). 

This firmware can either be custom bare metal C code or be built on top of an existing real time operating system or even full operating system. All Soft-CPUs let you write your own bare metal firmware, but only some configurations work with operating systems.

[Firmware which runs on LiteX Google Doc](https://docs.google.com/document/d/11uzjWRWk9-KuBFc7chUNUluL5ajysY2qfXvt1vttl7k/edit)

# Baremetal

## Support Soft-CPU Configurations

**All** Soft-CPUs let you write your own bare metal firmware.

 * `lm32` (any variant)
 * `or1k` (any variant)
 * `vexriscv` (any variant)
 * `picorv32` (any variant)
 * `minerva` (any variant)

---

# MicroPython via [FuPy Project](https://fupy.github.io)

From the FuPy website;
> The aim of this project is to make MicroPython run on FPGAs using the LiteX & Migen+MiSoC technologies. This allows you to do full stack development (FPGA gateware & soft CPU firmware) in Python!

## When to use?

MicroPython is great to use when ease and speed of development is more important than performance. When coupled with LiteX you can push MicroPython even further by moving performance critical parts into FPGA gateware.

## Hardware Requirements

MicroPython is very light on requirements;
 * 32 kilobytes memory - can normally use internal block ram inside FPGA.
 * 128 kilobytes of storage - can normally use spare space in SPI flash used to configure the FPGA.

## Support Soft-CPU Configurations

 * `lm32` (any variant), in FuPy repository
 * `or1k` (any variant), in FuPy repository
 * (in progress) `vexriscv` (any variant), in FuPy repository
 * (in progress) `picorv32` (any variant), in FuPy repository

---

# [NuttX](http://www.nuttx.org/)

From the NuttX website;
> NuttX is a real-time operating system (RTOS) with an emphasis on standards compliance and small footprint. Scalable from 8-bit to 32-bit microcontroller environments, the primary governing standards in NuttX are Posix and ANSI standards. Additional standard APIs from Unix and other common RTOS's (such as VxWorks) are adopted for functionality not available under these standards, or for functionality that is not appropriate for deeply-embedded environments (such as fork()).

## When to use?

NuttX is a good option if you are already using NuttX or need to use a function that is already available in the NuttX ecosystem.

## Hardware Requirements

Unknown. 

LiteEth networking is supported.

## Support Soft-CPU Configurations

 * `lm32` (any variant), in upstream repository

---

# [Zephyr](https://www.zephyrproject.org/)

From the Zephyr website;
> The Zephyr Project is a scalable real-time operating system (RTOS) supporting multiple hardware architectures, optimized for resource constrained devices, and built with safety and security in mind.

## When to use?

Zephyr is a great choice if you don't want to write your own bare metal firmware. It is under active development and moving forward quickly.

It also has a coding style which makes it easy to move to Linux at a later state if you outgrow the abilities of Zephyr.

## Hardware Requirements

Zephyr is very light on requirements;
 * 32 kilobytes memory - can normally use internal block ram inside FPGA.
 * Some storage - can normally use spare space in SPI flash used to configure the FPGA.

## Support Soft-CPU Configurations

 * `vexriscv` (any variant), in upstream repository
 * `picorv32` (any variant), out of tree port

---

# [Linux](https://en.wikipedia.org/wiki/Linux)

From Wikipedia;
> Linux is a family of free and open-source software operating systems based on the Linux kernel, an operating system kernel first released on September 17, 1991 by Linus Torvalds. ...
> Linux also runs on embedded systems, i.e. devices whose operating system is typically built into the firmware and is highly tailored to the system. This includes routers, automation controls, televisions, digital video recorders, video game consoles, and smartwatches. Many smartphones and tablet computers run Android and other Linux derivatives.[30] Because of the dominance of Android on smartphones, Linux has the largest installed base of all general-purpose operating systems.

## When to use?

Linux tends to run quite slowly on the soft-CPUs supported by LiteX and needs hardware acceleration to do most useful operations. Linux makes the most sense were the existing large pool of Linux drivers or software is helpful.

## Hardware Requirements

Linux operating support generally needs;
 * Large and fast FPGA, something like Lattice ECP5 or Xilinx Artix 7 / Spartan 6.
 * 32+ megabytes memory, generally meaning external SDRAM or DDR RAM.
 * UART serial console.
 * Fast Ethernet (100 Megabit or 1 Gigabit Ethernet).
 * Some type of storage, large SPI flash or SD Card or SATA hard drives potential options.

## Support Soft-CPU Configurations

 * `or1k` (`linux` variant), out of tree port being upstreamed
 * `vexriscv` (`linux` variant), out of tree port being upstreamed
