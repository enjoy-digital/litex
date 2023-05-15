[> 2023.04, released on May 8th 2023
------------------------------------

	[> Fixed
	--------
	- build/xilinx/vivado : Fixed Verilog include path.
	- builder/meson       : Fixed version comparison.
	- liblitedram         : Fixed write leveling with x4 modules.
	- integration/soc     : Fixed alignment of origin on size.
	- litex_sim           : Fixed ram_init.
	- libbase/i2c         : Fixed various issues.
	- integration/soc     : Fixed/Removed soc_region_cls workaround.
	- cores/gpio          : Fixed IRQ generation.
	- litex_sim           : Fixed --with-etherbone.
	- build/efinix        : Fixed iface.py execution order.
	- cpu/Vex/NaxRiscv    : Fixed IRQ numbering (0 reserved).
	- cpu/rocket          : Fixed compilation with newer binutils.
	- cpu/soc             : Fixed CPU IRQ reservation.
	- litepcie/software   : Fixed compilation with DMA_CHECK_DATA commented.
	- litedram/dma        : Fixed rdata connection (omit list update since LiteX AXI changes).
	- litepcie/US(P)      : Fixed possible MSI deadlock.
	- cores/usb_ohci      : Fixed build issue (usb_clk_freq wrapped as int).

	[> Added
	--------
	- clock/intel         : Added StratixVPLL.
	- cores/dma           : Added FIFO on WishboneDMAReader to pipeline reads and allow bursting.
	- liblitedram         : Improved SPD read with sdram_read_spd function.
	- bios/liblitedram    : Added utils and used them to print memory sizes.
	- build/parser        : Added a method to search default value for an argument.
	- litex_setup         : Added Arch Linux RISC-V/OR1K/POWER-PC GCC toolchain install.
	- cores/pwm           : Added reset signal (to allow external reset/synchronization).
	- cpu/cva6            : Updated.
	- cores/prbs          : Improved timings.
	- litex_sim           : Allowed enabling SDRAM BIST.
	- liblitedram         : Refactored BIST functions and added sdram_hw_test.
	- soc/software        : Added extern C (required to link with cpp code).
	- cpu/VexRiscv-SMP    : Avoided silent generation failure.
	- cores/spi_flash     : Added Ultrascale support.
	- clock/gowin_gw1n    : Fixed simulation warnings.
	- liblitedram         : Various improvements/cleanups.
	- cpu/Naxriscv        : Exposed FPU parameter.
	- cores/xadc          : Refactored/Cleaned up.
	- cores/dna           : Added initial Ultrascale(+) support and reduced default clk_divider to 2.
	- cores/usb_ohci      : Added support for multiple ports.
	- litex_cli           : Added binary support for register dump.
	- cpu/NaxRiscv        : Enabled FPU in crt0.S.
	- core/icap           : Added initial Ultrascale(+) support and clk_divider parameter.
	- litex_sim           : Added initial video support.
	- soc/add_video       : Added framebuffer region definition.
	- litex_term          : Avoided use of multiprocessing.
	- cores/esc           : Added initial ESC core with DSHOT 150/300/600 support.
	- litex_json2dts      : Allowed/Prepared Rocket support and made it more generic.
	- gen/common          : Added Open/Unsigned/Signed signal definition and updated cores to use it.
	- global              : Added initial list of sponsors/partners.
	- build/xilinx        : Improved Xilinx US/US+ support.
	- build/platform      : Added get_bitstream_extension method.
	- cpu/VexRiscvSMP     : Added standard variant.
	- cpu/cva6            : Added 32-bit variant support and various improvements.
	- clock/gowin         : Added GW2AR support.
	- build/efinix        : Added option to select active/passive SPI mode.
	- cores/bitbang       : Added documentation.
	- litex_term          : Improved connection setup.
	- clock/gowin         : Improved VCO config computation and added CLKOUTP/CLKOUTD/CLKOUTD3 support.
	- cpu/rocket          : Reworked variants.
	- liblitesdcard       : Avoided use of stop transmission for writes when only one block.
	- installation        : Simplified/Improved ci.yml/MANIFEST.in/setup.py.
	- cores/pwm           : Added MultiChannelPWM support.
	- soc/add_pcie        : Exposed more DMA parameters.
	- litepcie/dma        : Improved LitePCIeDMAStatus timings.
	- litepcie_gen        : Exposed 64-bit support.
	- litepcie/dma        : Better configuration decoupling between DMAWriter/Reader.
	- litepcie/dma        : Allowed software to get DMA status.
	- litepcie/phy        : Replaced Xilinx generated core on 7-series Verilog with Migen/LiteX code.
	- litepcie/msi        : Improved MSI filtering.
	- litepcie_gen        : Added MSI rate limiting on Ultrascale(+) to avoid stall issues.
	- liteiclink/prbs     : Improved PRBS RX timings.
	- liteiclink/gty/gth  : Added power-down signal on GTYQuadPLL and GTHQuadPLL.
	- litelclink/gty/gth  : Integrated 7-series improvements.
	- litelclink/gty/gth  : Added DRP interface on QuadPLL.
	- litedram/bist       : Ensured proper completion of writes.
	- litedram/bist       : Replicated data for large data-width.
	- litedram/ci         : Allowed tests to run in parallel.
	- litedram/gw2ddrphy  : Improvements to remove warnings in simulation.
	- liblitespi/spiflash : Add erasee and write functions.
	- liblitespi/Spiflash : Add write from sdcard file function.

	[> Changed
	----------
	- builder/export      : Added soc-csv/-json/--svd arguments (in addition to csr-xy).
	- litepcie/phy        : Retained only Gen3/4 support and removed Gen2.

[> 2022.12, released on January 2th 2023
----------------------------------------

	[> Fixed
	--------
	- bios                              : Fix missing CONFIG_BIOS_NO_DELAYS update.
	- axi/AXIDownConverter              : Fix unaligned accesses.
	- cpu/rocket                        : Fix fulld/fullq variants typos.
	- cores/video                       : Fix red/blue channel swap (and apply similar changes to litex_boards).
	- software/demo                     : Fix compilation with Nix.
	- cpu/cv32e41p                      : Fix IRQs.
	- interconnect/csr                  : Allow CSR collection at the top-level.
	- interconnect/csr                  : Fix CSR with 64-bit bus width.
	- build/sim                         : Disable more useless warnings (-Wno-COMBDLY and -Wno-CASEINCOMPLETE).
	- intel                             : Fix constraints issues preventing the build with some boards/versions.
	- axi/axi_lite                      : Fix combinatorial loop on ax.valid/ax.ready.
	- soc/cores/video/VideoS7GTPHDMIPHY : Fix typo.
	- integration/export                : Fix CSR base address definition when with_csr_base_define=False.


	[> Added
	--------
	- soc                        : Add new "x" (executable) mode to SoCRegion.
	- cpu/NaxRiscv               : Update to latest and add parameters.
	- soc                        : Propagate address_width on dynamically created interfaces.
	- get_mem_data               : Add data_width support.
	- cores/dma                  : Allow defining ready behavior on idle.
	- axi                        : Improvements/Simplifications.
	- axi_stream                 : Improvements/Simplifications.
	- yosys_nextpnr              : Add flow3 option to abc9 mode.
	- yosys_nextpnr              : Refactor args.
	- vivado                     : Allow directive configuration.
	- jtag                       : Add Efinix JTAG support.
	- clock/intel                : Improve pll calculation.
	- stream/ClockDomainCrossing : Expose buffered parameter.
	- tools/remote               : Add Etherbone packets retransmisson.
	- build                      : Add VHDL2VConverter to simplify GHDL->Verilog conversion.
	- cpu/microwatt              : Switch to VHDL2VConverter.
	- cpu/neorv32                : Switch to VHDL2VConverter.
	- axi                        : Differentiate AXI3/AXI4.
	- stream/Monitor             : Add packet count and add reset/latch control from logic.
	- spi                        : Create spi directory and integrate SPIBone + improvements.
	- interconnect/csr           : Add optional fixed CSR mapping.
	- fhdl/verilog               : Improve code presentation/attribute generation.
	- gen/common                 : Add new LiteXModule to simplify user designs and avoid some Migen common issues.
	- soc/SoCBusHandler          : Integrate interconnect code to simplify reuse.
	- gen/common                 : Add reduction functions.
	- vhd2v                      : Use GHDL directly (Instead of GHDL + Yosys).
	- cpu/openc906               : Update, add more peripherals to mem_map and add debug variant.
	- soc/software/i2c           : Add non 8bit i2c mem address support.
	- gen/fhdl                   : Add LiteXHierarchyExplorer to generate SoC hierarchy.
	- gen/fhd                    : Add timescale generation.
	- build                      : Add LitexArgumentParser to customize/simplify argument parsing.
	- json2renode                : Update.
	- logging                    : Allow logging level to be configured from user scripts.
	- soc/cores/cpu              : Allow enabling/disabling reset address check.
	- integration/export         : Directly generate extract/replace mask from Python.
	- cpu/zync7000               : Add axi_gp_slave support.

	[> Changed
	----------
	- ci       : Bump to Ubutu 22.04.
	- soc_core : Move add_interrupt/add_wb_master/add_wb_slave/register_mem/register_rom to compat.
	- software : Do not build software as PIE.
	- ci       : Add microwatt/neorv32 test + requirements (GHDL).
	- ci       : Switch GCC toolchain installs to distro install.


[> 2022.08, released on September 12th 2022
-------------------------------------------

	[> Fixed
	--------
	- cpu/vexriscv:               Fix compilation with new binutils.
	- soc/LiteXSocArgumentParser: Fix --cpu-type parsing.
	- litex_sim:                  Fix --with-ethernet.
	- liblitesdcard:              Fix SDCard initialization corner cases.
	- liblitedram:                Enable sdram_init/mr_write for SDRAM.
	- export/get_memory_x:        Replace SPIFlash with ROM.
	- soc/cores/video:            Fix operation with some monitors (set data to 0 during blanking).
	- tools/remote/comm_usb:      Fix multi-word reads/writes.
	- build/lattice/oxide:        Fix ES posfix on device name.
	- interconnect/axi:           Fix AXIArbiter corner case.
	- litex_server/client:        Fix remapping over CommPCIe.
	- LitePCIe:                   Fix LiteUART support with multi-boards.

	[> Added
	--------
	- litex_setup:            Add -tag support for install/update.
	- tools:                  Add initial LiteX standalone SoC generator.
	- cores/ram:              Add Xilinx's FIFO_SYNC_MACRO equivalent.
	- LitePCIe:               Always use 24-bit depth fields on LitePCIeBuffering to simplify software.
	- gen/fhdl:               Integrate Migen namer to give us more flexibility.
	- fhdl/memory:            Prefix memory files with build name to simplify reuse/integration.
	- cpu/rocket:             Add more variants.
	- cores/video:            Enable driving both + and - diff outs to compensate hardware issues.
	- build:                  Add intial OSFPGA Foedag/Raptor build backend.
	- cpu/cva5:               Add initial CVA5 CPU support (ex Taiga).
	- LiteSATA:               Add IRQ and Identify support.
	- clock/intel:            Improve to find the best PLL config.
	- cpu/cva6:               Add initial CVA6 CPU support (ex Ariane).
	- bios:                   Improve config flags.
	- tools:                  Add I2s/MMCM support to litex_json2dts_zephyr.
	- clock/gowin:            Add GW2A support.
	- bios:                   Disable LTO (does not work in all cases, needs to be investigated).
	- CI:                     Test more RISC-V CPUs and OpenRisc CPUs in CI.
	- bios:                   Add CONFIG_NO_BOOT to allow disabling boot sequence.
	- export:                 Allow disabling CSR_BASE define in csr.h.
	- build/openocd:          Update for compatibility with upstream OpenOCD.
	- cpu/openc906:           Add initial OpenC906 support (open version of the Allwinner's D1 chip).
	- soc:                    Add automatic bridging between AXI <-> AXI-Lite <-> Wishbone.
	- soc:                    Add AXI-Full bus support.
	- interconnect:           Add AXI DownConverted and Interconnect/Crossbar.
	- interconnect:           Create axi directory and split code.
	- soc:                    Modify SoC finalization order for more flexibility.
	- soc:                    Add --bus-interconnect parameter to select interconect: shared/crossbar.
	- valentyusb:             Package and install it with LiteX.
	- bios/mem_list:          Align Mem Regions.
	- build:                  Introduce GenericToolchain to cleanup/simplify build backends.
	- soc/etherbone:          Expose broadcast capability.
	- build/lattice:          Add MCLK frequency support.
	- cpu/cva6:               Add IRQ support.
	- cores/clock:            Add manual placement support to ECP5PLL.
	- cores/leds:             Add polarity support.
	- cpu/neorv32:            Switch to new NeoRV32 LiteX Core Complex and add variants support.
	- cores/gpio:             Add optional reset value.
	- litex_client:           Add --host support for remote operation.
	- sim/verilator:          Add jobs number support (to limit RAM usage with large SoCs/CPUs).
	- soc/SocBusHandler       Add get_address_width method to simplify peripheral integration.
	- bios:                   Expose BIOS console parameters (to enable/disable history/autocomplete).
	- bios:                   Expose BIOS LTO configuration.
	- litex_json2renode:      Update.
	- build:                  Introduce YosysNextPNRToolchain to cleanup/simplify Yosys support.
	- bios:                   Add buttons support/command.
	- litex_client:           Add XADC/Identifier/Leds/Buttons support to GUI.
	- cpu/NaxRiscv:           Update.
	- build/generic_platofrm: Add add_connector methode to allow extending connectors.
	- litex_server/client:    Add initial information exchange between server/client.
	- LitePCIe:               Improve 64-bit support.
	- interconnect/axi:       Add missing optional signals.
	- interconnect/wishbone:  Improve DownConverter efficiency.

	[> Changed
	----------
	- LiteX-Boards : Remove short import support on platforms/targets.
	- tools:         Rename litex_gen to litex_periph_gen.
	- LiteX-Boards:  Only generate SoC/Software headers when --build is set
	- Symbiflow:     Rename to F4PGA.
	- mkmsscimg:     Rename to crcfbigen.

[> 2022.04, released on May 3th 2022
------------------------------------

	[> Fixed
	--------
	- software/bios/mem_write: Fix write address increment.
	- software/liblitedram:    Improve calibration corner case on 7-series (SDRAM_PHY_DELAY_JUMP).
	- software/liblitedram:    Fix delay reconfiguration issue on ECP5/DDR3.
	- cores/jtag:              Fix chain parameter on XilinxJTAG.
	- soc/arguments:           Fix l2_size handling.
	- cpu/vexriscv_smp:        Fix pbus_width when using direct LiteDRAM interface.
	- libbase/i2c/i2c_poll:    Also check for write in i2c_scan (some chips are write only).
	- build/vivado:            Fix timing constraints application on nets/ports.

    [> Added
	--------
	- litex_setup:        Add minimal/standard/full install configs.
	- soc/arguments:      Improve default/help, add parser groups.
	- LiteSPI/phy:        Simplify integration on targets.
	- openocd/stream:     Simplify ECP5 JTAG-UART/JTAGBone use.
	- tools/litex_cli:    Allow passing reg name to --read/--write.
	- soc/add_spi_sdcard: Allow optional Tristate (useful on ULX3S).
	- software/bios:      Add new mem_cmd memory comparison command.
	- cpu/rocket:         Increase IRQ lines to 8.
	- cpu/serv:           Add MDU support.
	- cpu/marocchino:     Add initial support.
	- cpu/eos_s3:         Add LiteX BIOS/Bare Metal software support.
	- litex_sim:          Add .json support for --rom/ram/sdram-init.
	- soc/add_uart:       Allow multiple UARTs in the same design.
	- cores/cpu:          Add out-of-tree support.
	- build/xilinx:       Add initial Yosys/NextPnr support on Artix7 (and Zynq7000 with Artix7 fabric).
	- add_source:         Add optional copy to gateware directory.
	- cores/jtag:         Add initial JTAG-UART/JTAGBone Altera/Intel support.
	- LiteScope:          Add Samplerate support.
	- cores/bitbang:      Add optional I2C initialization by CPU.
	- libliteeth/tftp:    Add blocksize support an increase to 1024 bytes (allow 64MB filesize).
	- soc/add_sdram:      Make AXI integration more flexible (remove some specific Rocket hardcoding).
	- cpu/neorv32:        Add initial support (RV32I, VHDL converted to Verilog through GHDL-Yosys-synth).
	- cpu/naxriscv:       Add initial support (RV32IMA & RV64IMA, already able to run Linux).
	- interconnect/axi:   Add AXI UpConverter.
	- soc/add_sdram:      Allow data_width upconversion directly on AXI (avoid switching to Wishbone).
	- bios/memtest:       Optimize memspeed loop for better accuracy.
	- build/sim:          Allow custom modules to be in custom path.
	- build/OpenFPGA:     Add initial OpenFPGA build backend (Currently targeting SOFA chips).
	- build/efinix:       Add initial MIPI TX/RX support (and test on Trion/Titanium).
	- cores/video:        VTG improvements to support more Video chips.
	- cores/xadc:         Improve Zynq Ultrascale+ support.
	- LiteScope:          Optimize waveform upload speed.
	- LitePCIe:           Add LTSSM tracer capability to debug PCIe bringup issues.
	- cores/hyperbus:     Refactor core and improve performances (Automatic burst detection).
	- cores/jtag:         Add Zynq UltraScale+.
	- cores/ram:          Add Ultrascale+ HBM2 wrapper.
	- litex_json2renode:  Improve and add support for more CPUs.
	- cores/cpu:          Add initial FireV support.
	- litex_cli:          Add --csr-csv support and minimal GUI (based on DearPyGui).
	- litescope_cli:      Add minimal GUI (based on DearPyGui).
	- build/gowin:        Add powershell support.
	- LitePCIe:           Add initial 64-bit addressing support (Only for 64-bit datapath for now).
	- software/bios:      Add Main RAM test (when not pre-initialized).
	- build/trellis:      Enable bitstream compression on ECP5 by default.
	- soc/add_etherbone:  Increase buffer_depth to 16 (to improve etherbone bursting).
	- builder:            Add get_bios_filename/get_bitstream_filename methods to simplify targets.
	- cpu/vexriscv_smp:   Re-integrate Linux-on-LiteX−VexRiscv specific changes/mapping.
	- tools/litex_sim:    Allow RAM/SDRAM initialization from .json files (similar to hardware).
	- soc/cpu:            Expose optional CPU configuration parameters to users (ex VexRiscv-SMP/NaxRiscv).
	- soc:                Improve logs.
	- build/Efinix:       Add Atmel programmer.
	- stream/cdc:         Add optional common reset.
	- LiteDRAM:           Decouple DQ/DQS widths on S7DDRPHY.
	- cores/ws2812:       Improve timings at low sys_clk_freq.
	- soc/builder:        Add --no-compile (similar to --no-compile-gateware --no-compile-software).
	- software/demo:      Add --mem parameter to allow compilation for execution in ROM/RAM.
	- cpu/naxrsicv:       Add JTAG debug support.
	- cores/usb_fifo:     Re-implement FT245PHYSYnchronous.
	- cores/jtag:         Add JTAGBone/JTAG-UART support on Zynq/ZynqMP.
	- interconnect/sram:  Add SRAM burst support.
	- liblitesata:        Improve SATA init.
	- soc/cpu:            Improve command line listing.
	- soc/cores/uart:     Decouple data/address width on Stream2Wishbone.

	[> Changed
	----------
	- Fully deprecate SoCSDRAM/SPIFlash core (replaced by LiteSPI).
	- UART "bridge" name deprecated in favor of "crossover" (already supported).
	- "external" CPU class support deprecated (replaced by out-of-tree support).
	- lxterm/lxserver/lxsim short names deprecated (used long litex_xy names).
	- Deprecate JTAG-Atlantic support (Advantageously replaced by JTAG-UART).

[> 2021.12, released on January 5th 2022
----------------------------------------

	[> Fixed
	--------
	- software/linker:      Fix initialized global variables.
	- build/xilinx:         Fix Ultrascale SDROutput/Input.
	- cpu/rocket/crt0.s:    Fix alignements.
	- core/video:           Fix missing ClockDomainsRenamer in specific DRAM's width case.
	- mor1kx:               Fix --cpu-type=None --with-ethernet case.
	- build/lattice:        Fix LatticeiCE40SDROutputImpl.
	- soc/interconnect/axi: Fix 4KB bursts.

	[> Added
	--------
	- integration/builder:      Check if full software re-build is required when a CPU is used.
	- cores/clock:              Add Gowin PLL support.
	- build/gowin:              Add initial HyperRam support.
	- build/gowin:              Add differential Input/Output support.
	- build/lattice:            Add DDRTristate support.
	- cores/gpio:               Add external Tristate support.
	- tools/json2dts:           Make it more generic (now also used with OpenRisc/Mor1kx).
	- cpu/rocket:               Add SMP support (up to quad-core).
	- software/bios/boot:       Allow frame reception to time out (for litex_term auto-calibration).
	- tools/litex_term:         Add automatic settings calibration and --safe mode.
	- build/quicklogic:         Add initial support.
	- cores/icap/7-Series:      Add register read capability.
	- cores/video:              Add RGB565 support to VideoFrameBuffer.
	- soc:                      Raise custom SoCError Exception and disable traceback/exception.
	- soc/add_pcie:             Automatically set Endpoint's endianness to PHY's endianness.
	- build/efinix:             Add initial Trion and Titanium support.
	- fhdl/verilog:             Cleanup/Simplify verilog generation.
	- fhdl/memory:              Cleanup/Simplify and add support for Efinix case.
	- cpu/ibex:                 Add interrupt support.
	- tools/litex_client:       Add --length parameter for MMAP read accesses.
	- software/bios/cpu:        Add CPU tests in CI.
	- litex_sim/xgmii_ethernet: Improve models.
	- litex_setup:              Cleanup/Simplify and switch to proper "--" commands (with retro-compat).
	- cores/jtag:               Add ECP5 support.
	- cores/led:                Add WS2812/NeoPixel core.
	- cpu/femtorv:              Finish integration and add variants support.
	- cpu/eos-s3:               Add initial support.
	- build/anlogic:            Add initial support.
	- cpu/microwatt:            Add Xilinx multiplier support.
	- cpu/vexriscv/cfu:         Improve integration.
	- soc/interconnect:         Add initial AHB support (AHB2Wishbone).
	- cpu/gowin_emcu:           Add initial Gowin EMCU support.
	- cpu/zynq7000:             Add initial BIOS/software support.
	- cpu/zynq7000:             Add TCL support.
	- core/prbs:                Add error behaviour configuration on saturation.
	- software/bios:            Add write size option to mem_write cmd.
	- LitePCIe/phy:             Cleanup 7-Series PHY integration.
	- LitePCIe/dma              Add LitePCIeDMAStatus module.
	- LitePCIe/software:        Improve kernel/user-space utilities.
	- LiteDRAM/litedram_gen:    Improve ECP5 support.
	- LiteDRAM/phy:             Add initial LPDDR5 support.
	- LiteDRAM/frontend:        Refactor DRAM FIFO and add optional bypass mode.
	- LiteEth/core:             Add 32-bit/64-bit datapath support.
	- LiteEth/phy:              Add 10Gbps / Xilinx XGMII support.
	- LiteEth/phy:              Add 1Gbps  / Efinix RGMII support.
	- LiteSPI/phy:              Simplify SDR/DDR PHYs.
	- LiteHyperBus:             Add 16-bit support.

	[> Changed
	----------
	- software: Replace libbase with picolibc (new requirements: meson/ninja).
	- amaranth: Switch from nMigen to Amaranth HDL.

[> 2021.08, released on September 15th 2021
-------------------------------------------

	[> Fixed
	--------
	- wishbone/UpConverter: Fix SEL propagation.
	- cores/i2s:            Fix SYNC sampling.
	- BIOS/lib*:            Fix GCC warnings.
	- cpu/software:         Fix stack alignment issues.
	- cpu/blackparrot:      Fix integration.
	- interconnect/axi:     Fix valid signal in connect_to_pads for axi lite.
	- software/hw/common:   Fix _csr_rd_buf/_csr_wr_buf for sizeof(buf[0]) < CSR_DW_BYTES case.
	- software/soc.h:       Fix interoperability with assembly.
	- interconnect/stream:  Fix n=1 case on Multiplexer/Demultiplexer.
	- interconnect/axi:     Fix BURST_WRAP case on AXIBurst2Beat.
	- cpu/VexRiscv-SMP:     Fix build without a memory bus.
	- cpu/software:         Fix CLANG detection.
	- build/software:       Force a fresh software build when cpu-type/variant is changed.
	- cores/uart:           Fix TX reset level.
	- BIOS:                 Fix PHDR link error.
	- BIOS:                 Fix build-id link error.
	- LiteDRAM:             Fix Artix7/DDR3 calibraiton at low speed.

	[> Added
	--------
	- cores/video:               Add 7-Series HDMI PHY over GTPs.
	- cores/jtagbone:            Allow JTAG chain selection.
	- programmer:                Add iCESugar programmer.
	- cpu/vexriscv:              Add CFU support.
	- soc/controller:            Add separate SoC/CPU reset fields.
	- BIOS/liblitedram:          Add debug capabilities, minor improvements.
	- cpu/femtoRV:               Add initial FemtoRV support.
	- cores/uart:                Cleaned-up, Add optional TX-Flush.
	- cores/usb_ohci:            Add initial SpinalHDL's USB OHCI support (integrated in Linux-on-LiteX-Vexriscv).
	- stream:                    Add Gate Module.
	- soc/builder:               Allow linking external software packages.
	- soc/software:              Allow registering init functions.
	- cores/ram:                 Add init support to Nexus LRAM.
	- cores/spi:                 Add Manual CS Mode for bulk transfers.
	- cores/VexRiscv-SMP:        Make [ID]TLB size configurable.
	- dts:                       Add GPIO IRQ support.
	- programmer/DFUProg:        Allow to specify alt interace and to not reboot.
	- cores/clock/ecp5:          Add dynamic phase adjustment signals.
	- tools/litex_sim:           Mode SDRAM settings to LiteDRAM's DFI model.
	- build/gowin:               Add AsyncResetSynchronizer/DDRInput/DDROutput implementations.
	- build/gowin:               Add On-Chip-Oscillator support.
	- build/gowin:               Add initial timing constraints support.
	- build/attr_translate:      Simplify/Cleanup.
	- programmer/OpenFPGALoader: Add cable and freq options.
	- interconnect/packet:       Improve PacketFIFO to handle payload/param separately.
	- clock/ecp5:                Add 4-output support.
	- LiteSPI:                   Simplified/Cleaned-up, new MMAP architecture, applied to LiteX-Boards.
	- soc:                       Add LiteSPI integration code.
	- LitePCIe:                  DMA/Controller Simplified/Cleaned-up.
	- soc/add_cpu:               Add memory mapping overrides to build log and make an exception for the CPUNone case.
	- programmer:                Add ECPprogProgrammer.
	- soc/software:              Add Random access option to memtest.
	- tools:                     Add Renode generator script.
	- tools:                     Add Zephyr DTS generator script.
	- build/io:                  Add DDRTristate.
	- cpu/VexRiscv:              Restructure config flags for dcache/icache presence.
	- litex_sim:                 Improve RAM/SDRAM integration and make it closer to LiteX-Boards targets.
	- build/sim:                 Add ODDR/IDDR/DDRSTristate simulation models.
	- litex_sim:                 Add SPIFlash support.
	- LiteSPI:                   Add DDR support and integration in LiteX (rate=1:1, 1:2).
	- build/Vivado:              Make pre_synthesis/placement/routing commands similar to platform_commands.
	- LiteDRAM:                  Refactor C code generator.
	- LiteDRAM:                  Improve LPDDR4 support.
	- LiteDRAM:                  Reduce ECC granularity.

	[> Changed
	----------
	- soc_core: --integrated-rom-file argument renamed to --integrated-rom-init.


[> 2021.04, released on May 3th 2021
------------------------------------

	[> Fixed
	--------
	- litex_term:         Fix Windows/OS-X support.
	- soc/USB-ACM:        Fix reset clock domain.
	- litex_json2dts:     Various fixes/improvements.
	- cores/clock:        Fix US(P)IDELAYCTRL reset sequence.
	- cpu/Vexriscv:       Fix Lite variant ABI (has multiplier so can use rv32im).
	- BIOS:               Fix various compiler warnings.
	- LiteSDCard:         Fix various issues, enable multiblock reads/writes and improve performance.
	- CSR:                Fix address wrapping within a CSRBank.
	- soc/add_etherbone:  Fix UDPIPCore clock domain.
	- stream/Gearbox:     Fix some un-supported cases.
	- cpu/VexRiscv-SMP:   Fix build on Intel/Altera devices with specific RAM implementation.
	- timer:              Fix AutoDoc.
	- Microwatt/Ethernet: Fix build.
	- soc/software:       Link with compiler instead of ld.

	[> Added
	--------
	- Lattice-NX:             Allow up to 320KB RAMs.
	- BIOS:                   Allow compilation with UART disabled.
	- litex_json2dts:         Simplify/Improve and allow VexRiscv/Mor1kx support.
	- BIOS/i2c:               Improve cmd_i2c.
	- BIOS/liblitedram:       Various improvements for DDR4/LPDDR.
	- cores/Timer:            Add initial unit test.
	- cores:                  Add initial JTAGBone support on Xilinx FPGAs.
	- litex_term:             Improve JTAG-UART support.
	- litex_server:           Add JTAGBone support.
	- VexRiscv-SMP:           Add --without-out-of-order and --with-wishbone-memory capabilities.
	- BIOS:                   Allow specify TRIPLE with LITEX_ENV_CC_TRIPLE.
	- litex_client:           Add simple --read/--write support.
	- OpenFPGALoader:         Add flash method.
	- litex_sim:              Add GTKWave savefile generator.
	- litex_term:             Add nios2-terminal support.
	- cpu/mor1kx:             Add initial SMP support.
	- interconnect/axi:       Add tkeep support.
	- cores/gpio:             Add IRQ support to GPIOIn.
	- cpu:                    Add initial lowRISC's Ibex support.
	- build/xilinx/Vivado:    Allow tcl script to be added as ip.
	- cores/uart:             Rewrite PHYs to reduce resource usage and improve readability.
	- cores/pwm:              Add configurable default enable/width/period values.
	- cores/leds:             Add optional dimming (through PWM).
	- soc/add_pcie:           Allow disabling MSI when not required.
	- export/svd:             Add constants to SVD export.
	- BIOS:                   Allow dynamic Ethernet IP address.
	- BIOS:                   Add boot command to boot from memory.
	- cores:                  Add simple VideoOut core with Terminal, ColorBards, Framebuffer + various PHYs (VGA, DVI, HDMI, etc...).
	- csr/EventSourceProcess: Add rising edge support and edge selection.
	- soc/integration:        Cleanup/Simplify soc_core/builder.
	- soc/integrated_rom:     Add automatic BIOS ROM resize to minimize blockram usage and improve flexibility.
	- interconnect/axi:       Add AXILite Clock Domain Crossing.
	- cores/xadc:             Add Ultrascale support.
	- soc/add_ethernet:       Allow nrxslots/ntxslots configuration.
	- cpu/VexRiscv-SMP:       Integrate FPU/RVC support.
	- soc/add_csr:            Add auto-allocation mode and switch to it in LiteX's code base.
	- soc/BIOS:               Add method to check BIOS requirements during the build and improve error message when not satisfied.
	- LiteEth:                Add initial timestamping support.
	- litex_client:           Add optional filter to --regs.
	- LiteDRAM:               Add LPDDR4 support.
	- BIOS/netboot:           Allow specifying .json file.
	- cores/clock:            Add initial Gowin GW1N PLL support.
	- LiteSDCard:             Add IRQ support.

	[> Changed
	----------
	- platforms/targets: Move all platforms/targets to https://github.com/litex-hub/litex-boards.
	- litex_term:        Remove flashing capability.
	- cores/uart:        Disable dynamic baudrate by default (Unused and save resources).

[> 2020.12, released on December 30th 2020
------------------------------------------

	[> Fixed
	--------
	- fix SDCard writes.
	- fix crt0 .data initialize on SERV/Minerva.
	- fix Zynq7000 AXI HP Slave integration.

	[> Added
	--------
	- Wishbone2CSR: Add registered version and use it on system with SDRAM.
	- litex_json2dts: Add Mor1kx DTS generation support.
	- Build: Add initial Radiant support for NX FPGA family.
	- SoC: Allow ROM to be optionally writable (for contents overwrite over UARTBone/Etherbone).
	- LiteSDCard: Improve BIOS support.
	- UARTBone: Add clock domain support.
	- Clocking: Uniformize reset on iCE40PLL/ECP5PLL.
	- LiteDRAM: Improve calibration and add BIOS debug commands.
	- Clocking: Add initial Ultrascale+ support.
	- Sim: Allow dynamic enable/disable of tracing.
	- BIOS: Improve memtest and report.
	- BIOS: Rename/reorganize commands.
	- litex_server: Simplify usage with PCIe and add debug parameter.
	- LitePCIe: Add Ultrascale(+) support up to Gen3 X16.
	- LiteSATA: Add BIOS/Boot integration.
	- Add litex_cli to provides common RemoteClient functions: get identifier, dump regs, etc...
	- LiteDRAM: Simplify BIST integration.
	- Toolchains/Programmers: Improve checks/error reporting.
	- BIOS: add leds command.
	- SoC: Do a full reset of the SoC on reboot (not only the CPU).
	- Etherbone: Improve efficiency/performance.
	- LiteDRAM: Improve DDR4/DDR3 calibration.
	- Build: Add initial Oxide support for NX FPGA family.
	- Clock/RAM: Reorganize for better modularity.
	- SPI-OPI: Various improvements for Betrusted.
	- litex_json2dts: Improvements to use it with mor1kx and VexRiscv-SMP.
	- Microwatt: Add IRQ support.
	- BIOS: Add i2c_scan command.
	- Builder: Simplify Documentation generation with --doc args on targets.
	- CSR: Add documentation to EventManager registers.
	- BIOS: Allow disabling timestamp for reproducible builds.
	- Symbiflow: Remove workarounds on targets.
	- litex_server: Simplify use on PCIe, allow direct CommXY use in scripts to bypass litex_server.
	- Zynq7000: Improve PS7 configuration support (now supporting .xci/preset/dict)
	- CV32E40P: Improve OBI efficiency.
	- litex_term: Improve upload speed with CRC check enabled, deprecate --no-crc (no longer useful).
	- BIOS: Add mem_list command to list available memory and use mem_xy commands on them.
	- litex_term: Add Crossover and JTAG_UART support.
	- Software: Add minimal bare metal demo app.
	- UART: Add Crossover+Bridge support.
	- VexRiscv-SMP: Integrate AES support.
	- LitePCIe: Allow AXI mastering from FPGA (AXI-Lite and Full).
	- mor1kx: Add standard+fpu and linux+fpu variants.

	[> Changed
	----------
	- BIOS: commands have been renamed/reorganized.
	- LiteDRAM: rdcmdphase/wrcmdphase no longer exposed.
	- CSR: change default csr_data_width from 8 to 32.

[> 2020.08, released on August 7th 2020
---------------------------------------

	[> Fixed
	--------
	- Fix flush_cpu_icache on VexRiscv.
	- Fix `.data` section placed in rom (#566)

	[> Added
	--------
	- Properly integrate Minerva CPU.
	- Add nMigen dependency.
	- Pluggable CPUs.
	- BIOS history, autocomplete.
	- Improve boards's programmers.
	- Add Microwatt CPU support (with GHDL-Yosys-plugin support for FOSS toolchains).
	- Speedup Memtest using an LFSR.
	- Add LedChaser on boards.
	- Improve WishboneBridge.
	- Improve Diamond constraints.
	- Use InterconnectPointToPoint when 1 master,1 slave and no address translation.
	- Add CV32E40P CPU support (ex RI5CY).
	- JTAG UART with uart_name=jtag_uart (validated on Spartan6, 7-Series, Ultrascale(+)).
	- Add Symbiflow experimental support on Arty.
	- Add SDCard (SPI and SD modes) boot from FAT/exFAT filesystems with FatFs.
	- Simplify boot with boot.json configuration file.
	- Revert to a single crt0 (avoid ctr/xip variants).
	- Add otional DMA bus for Cache Coherency on CPU(s) with DMA/Cache Coherency interface.
	- Add AXI-Lite bus standard support.
	- Add VexRiscv SMP CPU support.

	[> Changed
	----------
	- Add --build --load arguments to targets.
	- Deprecate soc.interconnect.wishbone.UpConverter (will be rewritten if useful).
	- Deprecate soc.interconnect.wishbone.CSRBank (Does not seem to be used by anyone).
	- Move soc.interconnect.wishbone2csr.WB2CSR to soc.interconnect.wishbone.Wishbone2CSR.
	- Move soc.interconnect.wishbonebridge.WishboneStreamingBridge to soc.cores.uart.Stream2Wishbone.
	- Rename --gateware-toolchain target parameter to --toolchain.
	- Integrate Zynq's PS7 as a regular CPU (zynq7000) and deprecate SoCZynq.

[> 2020.04, released on April 28th, 2020
----------------------------------------

	[> Description
	--------------
	First release of LiteX and the ecosystem of cores!

	LiteX is a Migen/MiSoC based Core/SoC builder that provides the infrastructure to easily create
	Cores/SoCs (with or without CPU).

	The common components of a SoC are provided directly:
	- Buses and Streams (Wishbone, AXI, Avalon-ST)
	- Interconnect
	- Common cores (RAM, ROM, Timer, UART, etc...)
	- CPU wrappers/integration
	- etc...
	And SoC creation capabilities can be greatly extended with the ecosystem of LiteX cores (DRAM,
	PCIe, Ethernet, SATA, etc...) that can be integrated/simulated/build easily with LiteX.

	It also provides build backends for open-source and vendors toolchains.

	[> Fixed
	--------
	- NA

	[> Added
	--------
	- NA

	[> Changed
	----------
	- https://github.com/enjoy-digital/litex/pull/399: Converting LiteX to use Python modules.
