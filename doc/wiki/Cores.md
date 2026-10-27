# Cores

The cores shipped with LiteX itself, in `litex/soc/cores/`: the building blocks every SoC needs
(UART, timer, GPIO, SPI, I2C, clocking...) and a number of specialized ones (video, USB,
HyperRAM, CAN, PSRAM, audio...). The large protocol cores live in their own repositories: see the
[Cores ecosystem](Cores-Ecosystem.md) (LiteDRAM, LiteEth, LitePCIe, LiteSATA, LiteSDCard,
LiteICLink, LiteJESD204, LiteSPI, LiteI2C, LiteScope, LiteNVMe, LiteDSP).

A core is a `LiteXModule` (a Migen `Module` with `AutoCSR` and `AutoDoc`): its control/status
registers are declared as `CSRStorage`/`CSRStatus` attributes and collected automatically on the
[CSR bus](CSR-Bus.md); its interrupts come from an `EventManager`; its data flows through
[streams](Streams.md) (`sink`/`source` endpoints) and memory-mapped traffic through
[Wishbone](Wishbone-Bus.md) or [AXI](AXI-Bus.md) interfaces. How to write one: [Add a new core](Add-A-New-Core.md).

Two ways to use a core in a SoC ([SoC-builder](SoC-builder.md)):

```python
# 1. With the SoC helper when there is one: it instantiates, connects and names the core.
self.add_timer(name="timer1")
self.add_i2c_master(name="i2c0", pads=platform.request("i2c"))
self.add_video_framebuffer(phy=self.videophy, timings="800x600@60Hz", clock_domain="dvi")

# 2. Directly: the module becomes a submodule, its CSRs and IRQs are picked up by name.
self.leds = LedChaser(pads=platform.request_all("user_led"), sys_clk_freq=sys_clk_freq)
self.irq.add("leds")      # only for cores with an EventManager
```

The tables below say what each core does, the interfaces it exposes (CSRs, EventManager
interrupts, streams, bus) and the SoC helper when there is one. Everything is in
`litex/soc/cores/<file>.py` unless a directory is given.

## Control and status

| Core | Classes | What it does | Interfaces | Helper |
| --- | --- | --- | --- | --- |
| `timer.py` | `Timer` | Countdown timer with reload, optional uptime counter (`add_uptime()`) | CSRs, IRQ | `add_timer`, `--timer-uptime` |
| `watchdog.py` | `Watchdog` | Watchdog resetting the SoC (or halting) when not fed | CSRs, IRQ | `add_watchdog`, `--with-watchdog` |
| `gpio.py` | `GPIOIn`, `GPIOOut`, `GPIOInOut`, `GPIOTristate` | GPIOs, with one interrupt per input pin | CSRs, IRQ | |
| `led.py` | `LedChaser`, `WS2812`, `SK2812RGBW` | LED chaser (the usual "it is alive"), serial RGB/RGBW LEDs | CSRs; Wishbone (serial LEDs) | |
| `pwm.py` | `PWM`, `MultiChannelPWM` | PWM outputs (enable, width, period) | CSRs | |
| `identifier.py` | `Identifier` | The SoC identification string (read by `litex_cli --ident` and the BIOS) | memory on the CSR bus | `add_identifier`, `--ident` |
| `freqmeter.py` | `FreqMeter` | Measures the frequency of a clock | CSRs | |
| `dna.py` | `S7DNA`, `USDNA` | Xilinx device DNA (unique ID) | CSRs | |
| `xadc.py` | `S7SystemMonitor`, `USSystemMonitor`, `USPSystemMonitor`, `ZynqUSPSystemMonitor` | Xilinx XADC/SYSMON: temperature, voltages, optional DRP access | CSRs | |
| `hwmon.py` | `GowinAroraVTemperatureSensor`, `IntelTemperatureSensor`, `IntelLegacyTemperatureSensor` | Temperature sensors of Gowin and Intel FPGAs, common `LiteXTemperatureMonitor` CSRs | CSRs | |
| `icap.py` | `ICAP`, `ICAPBitstream` | Xilinx ICAP: configuration registers, warm reboot (IPROG), bitstream loading | CSRs | |
| `seven_seg.py` | `SevenSegmentDisplay` | Multiplexed 7-segment displays | CSRs | |
| `esc.py` | `ESCDShot` | DShot ESC (motor controller) output | CSRs | |
| `dac.py` | `DAC` | First-order sigma-delta 1-bit DAC | CSRs | |

## Communication

| Core | Classes | What it does | Interfaces | Helper |
| --- | --- | --- | --- | --- |
| `uart.py` | `UART`, `RS232PHY`, `UARTCrossover`, `UARTBone`, `UARTMultiplexer`, `UARTPHY` | The serial console: UART with FIFOs and interrupts, RS232 PHY, crossover UART (console through a bridge), FT245 PHY; UARTBone and `Stream2Wishbone` (serial to Wishbone master, see [Host-Bridges](Host-Bridges.md)) | CSRs, IRQ, 8-bit streams | `add_uart` (`--uart-name`: `serial`, `crossover`, `crossover+uartbone`, `jtag_uart`, `usb_acm`, `sim`, `stub`, `stream`), `add_uartbone` |
| `jtag.py` | `JTAGPHY`, `XilinxJTAG`, `AlteraJTAG`, `ECP5JTAG`, `GowinJTAG`, `EfinixJTAG`, `JTAGBitbang` | Access to the FPGA's JTAG TAP from the design (JTAGBone, JTAG UART, CPU debug) | streams, CSRs (bitbang) | `add_jtagbone`, `add_cpu_jtag_debug` |
| `spi/` | `SPIMaster`, `SPISlave`, `SPIMMAP`, `SPIBone` | SPI master and slave, memory-mapped multi-slave SPI engine, SPI to Wishbone bridge | CSRs, IRQ, Wishbone, streams | `add_spi_master` |
| `i2c.py`, `bitbang.py` | `I2CMaster`; bitbang `I2CMaster`, `SPIMaster` | I2C master (and bit-banged I2C/SPI for the BIOS and simple software drivers) | CSRs, IRQ, Wishbone | `add_i2c_master` |
| `spi_flash.py`, `spi_opi.py`, `bpi_flash.py` | `S7SPIFlash`, `USSPIFlash`, `ECP5SPIFlash`; `S7SPIOPI`; `BPIFlash` | Access to the configuration flash clock pin (Xilinx STARTUPE2/E3, ECP5 USRMCLK), Octal SPI flash, parallel BPI NOR flash | CSRs, Wishbone | `add_spi_flash` uses LiteSPI, `add_spi_ram` |
| `usb_fifo.py` | `FT245PHYSynchronous`, `FT245PHYAsynchronous` | FTDI FT245/FT600-style FIFO interface | streams | |
| `usb_ohci.py` | `USBOHCI` | USB 1.1 OHCI host (SpinalHDL generated), used by Linux | Wishbone control, Wishbone DMA, IRQ | |
| `luna_cdc_acm.py` | `LunaCDCACM` | USB 2.0 CDC-ACM serial port with LUNA | 8-bit streams | `--uart-name=usb_acm` |
| `usb2_phy/` | `USB2PHY`, `USBHSPHY`, `USBFSPHY`, `GW5AUSB2PHYCRG` | Soft USB 2.0 UTMI PHY (high speed and full/low speed) in the fabric, no external PHY | UTMI | |
| `can/ctu_can_fd.py` | `CTUCANFD` | CAN-FD controller (CTU CAN FD VHDL core, converted with GHDL) | Wishbone, CSRs, IRQ | |
| `emif.py` | `EMIF` | TI EMIF external memory interface to Wishbone master bridge (a DSP as bus master) | Wishbone | |
| `code_8b10b.py`, `prbs.py` | `Encoder`, `Decoder`, `StreamEncoder`, `StreamDecoder`; `PRBSGenerator`, `PRBSChecker` | 8b/10b coding, PRBS7/15/31 generators and checkers for link tests | streams | |

## Memory

| Core | Classes | What it does | Interfaces | Helper |
| --- | --- | --- | --- | --- |
| `hyperbus.py` | `HyperRAM` | HyperRAM controller with Wishbone, AXI-Lite or AXI frontend, SDR PHY | bus, CSRs | `add_hyperram` |
| `hyperram/` | `HyperRAMController`, `TitaniumHyperRAMPHY` | Newer AXI HyperRAM controller with calibration (Efinix Titanium PHY) | AXI, CSRs | `add_hyperram(controller=...)` |
| `ram/` | `Up5kSPRAM`, `NXLRAM`, `AsyncSRAM`, `APMemory`, `OPIPSRAM`, `GowinHyperRAM`, `EfinixHyperRAM`, `EfinixHyperRAMIP`, `EfinixTrionDDR`/`EfinixDDR`, `USPHBM2` | On-chip and vendor memories: iCE40 SPRAM, Lattice Nexus LRAM, asynchronous SRAM, AP Memory and Octal PSRAM, Gowin/Efinix HyperRAM and HyperRAM IP, Efinix hard DDR, Xilinx UltraScale+ HBM2 | Wishbone or AXI | used by the targets (`add_ram` with the module's bus) |
| `dma.py` | `WishboneDMAReader`, `WishboneDMAWriter` | Memory to stream and stream to memory DMAs | Wishbone master, streams, CSRs | |
| `ecc.py` | `ECCEncoder`, `ECCDecoder` | Hamming SECDED error correction | | |

The main memories are added by the SoC helpers: `add_rom`/`add_ram` (block RAM), `add_sdram`
(LiteDRAM), `add_spi_flash` (LiteSPI, memory-mapped), `add_spi_ram`.

## Video and imaging

| Core | Classes | What it does | Interfaces | Helper |
| --- | --- | --- | --- | --- |
| `video.py` | `VideoTimingGenerator`, `VideoFrameBuffer`, `VideoTerminal`, `ColorBarsPattern` | Video timings (CSR configurable), framebuffer read by DMA from main RAM, text terminal fed by the UART stream, test pattern | streams, CSRs, Wishbone DMA | `add_video_framebuffer`, `add_video_terminal`, `add_video_colorbars` |
| `video.py` | `VideoVGAPHY`, `VideoDVIPHY`, `VideoLCDPHY`, `VideoHDMIPHY`, `VideoS6HDMIPHY`, `VideoS7HDMIPHY`, `VideoS7GTPHDMIPHY`, `VideoUSPGTHHDMIPHY`, `VideoGowinHDMIPHY` | The output PHYs: parallel RGB (VGA DAC, LCD, DVI transmitter chips) and HDMI/DVI TMDS serializers (generic, Spartan-6, 7-Series OSERDES or GTP, UltraScale+ GTH, Gowin) | video stream | |
| `code_tmds.py` | `TMDSEncoder` | TMDS 8b/10b encoding for HDMI/DVI | | |
| `spilcd.py` | `SPILCD` | SPI LCD displays (ST7789...) | CSRs, pixel stream | |
| `ov5640.py` | `OV5640Camera` | OV5640 camera control (SCCB) and DVP capture | CSRs, pixel stream | |

## Audio

| Core | Classes | What it does | Interfaces |
| --- | --- | --- | --- |
| `i2s.py` | `S7I2S` | I2S receiver/transmitter with FIFOs | Wishbone, CSRs, IRQ |
| `i2saudio.py` | `I2SAudio` | Simple I2S transmitter fed by a stereo stream | stream, CSRs |

## Clocking

`litex/soc/cores/clock/` wraps the PLLs and clock managers of every vendor behind one API:
`register_clkin(clk, freq)`, `create_clkout(cd, freq, phase=0, margin=...)` and the
configuration is computed at build time (`compute_config`), with an error when the requested
frequencies cannot be reached. A target's CRG (clock and reset generator) is usually ten lines
around one of these:

| Vendor | Classes |
| --- | --- |
| Xilinx | `S6PLL`, `S6DCM`, `S7PLL`, `S7MMCM`, `S7IDELAYCTRL`, `USPLL`, `USMMCM`, `USIDELAYCTRL`, `USPPLL`, `USPMMCM`, `USPIDELAYCTRL` (optional DRP access, `expose_drp()`) |
| Intel | `CycloneIVPLL`, `CycloneVPLL`, `Cyclone10LPPLL`, `Max10PLL`, `StratixVPLL`, `Agilex3PLL`, `Agilex5PLL`, `Agilex7PLL` |
| Lattice | `ECP5PLL`, `ECP5DynamicDelay`, `iCE40PLL`, `NXPLL`, `NXOSCA` |
| Gowin | `GW1NPLL`, `GW1NOSC`, `GW2APLL`, `GW5APLL` |
| Efinix | `TRIONPLL`, `TITANIUMPLL` |
| CologneChip | `GateMatePLL` |

```python
self.cd_sys = ClockDomain()
self.pll = pll = S7PLL(speedgrade=-1)
pll.register_clkin(platform.request("clk100"), 100e6)
pll.create_clkout(self.cd_sys, sys_clk_freq)
```

## Interrupts: the EventManager

A core raises an interrupt by owning an `EventManager` (`litex/soc/interconnect/csr_eventmanager.py`)
with one or more event sources: `EventSourcePulse` (set by a pulse, cleared by software),
`EventSourceProcess` (an edge of a signal: `edge="rising"|"falling"|"any"`), `EventSourceLevel`
(follows a level). The manager provides the `status`, `pending` (write 1 to clear) and `enable`
CSRs and the `irq` output; `soc.irq.add("<name>")` (or the helper) assigns the line to the CPU and
exports it to `soc.h`, `SharedIRQ` ORs several managers on one line when the CPU has few.

```python
self.ev = EventManager()
self.ev.done = EventSourcePulse(description="Transfer done.")
self.ev.finalize()
self.comb += self.ev.done.trigger.eq(transfer_done)
```

## Helpers for core authors (`litex/gen`)

- `LiteXModule`: `self.x = Module()` adds a submodule (no `self.submodules +=` needed), likewise
  for specials and clock domains; `add_module()`, `get_module()`, `get_signals()`.
- `litex/gen/genlib/cdc.py`: `MultiReg`, `PulseSynchronizer`, `BusSynchronizer`, `AsyncResetSynchronizer`,
  `ElasticBuffer`; `litex/gen/genlib/misc.py`: `WaitTimer`, `BitSlip`, `timeline`, `chooser`, `displacer`.
- `litex/gen/fhdl/`: the Verilog generation (`verilog.py`), `Instance` helpers, memory and
  hierarchy utilities (`--hierarchical-verilog`), naming.
- The style to follow: [coding_style.md](https://github.com/enjoy-digital/litex/blob/master/doc/coding_style.md),
  and for portability across vendors [architectural_style.md](https://github.com/enjoy-digital/litex/blob/master/doc/architectural_style.md).
