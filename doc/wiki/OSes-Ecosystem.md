# LiteX OSes Ecosystem

The LiteX ecosystem provides extensive support for a wide array of operating systems, allowing you to choose the one that best fits your development needs. The framework can automatically generate software headers that match the hardware configuration. This powerful feature allows developers to generate software headers(C, Rust, .csv, .json) or OS device trees automatically, ensuring seamless hardware-software interaction and simplifying the development process.

## Bare Metal
If you're aiming to run code directly on hardware without an intervening OS, LiteX supports Bare Metal development. This setup is ideal for high-performance, low-overhead applications:
- [LiteX C BIOS](https://github.com/enjoy-digital/litex/tree/master/litex/soc/software)
- [LiteX C Demo App](https://github.com/enjoy-digital/litex/tree/master/litex/soc/software/demo)

## Bootloader
LiteX also supports Barebox, a versatile bootloader designed to handle robust and complex boot scenarios, offering you maximum control over your system startup process.
- [Barebox](https://github.com/litex-hub/barebox)

## RTOS
When it comes to real-time operating systems (RTOS), LiteX has you covered with Zephyr and NuttX. These lightweight RTOS are perfect for managing real-time tasks, offering a balance between compactness and functionality.
- [NuttX](https://github.com/apache/nuttx)
- [Zephyr](https://github.com/zephyrproject-rtos/zephyr)

## MicroPython
LiteX supports MicroPython, a lean version of Python 3 designed for microcontrollers and constrained systems. This offers developers the simplicity of Python, ideal for systems where a full OS might be excessive.
- [MicroPython](https://github.com/litex-hub/micropython)

## Linux
For more sophisticated applications, you can take advantage of LiteX's support for the Linux operating system. With Linux's extensive software ecosystem, you'll have access to a wide range of tools, libraries, and services.
- [Linux-on-LiteX-VexRiscv](https://github.com/litex-hub/linux-on-litex-vexriscv)
- [Linux-on-LiteX-Rocket](https://github.com/litex-hub/linux-on-litex-rocket)

For more information on each operating system, please refer to their individual project pages. Whether you're starting a new project or looking to integrate LiteX into your existing workflow, our ecosystem is designed to offer you the flexibility you need.
