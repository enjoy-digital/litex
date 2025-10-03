[> 2025.08, released on October 3th 2025
----------------------------------------

[> Fixed
--------
- **tools/json2dts**                               : Fixed sdcard support in device tree generation ([PR #2292](https://github.com/enjoy-digital/litex/pull/2292), [29a8c3cdb](https://github.com/enjoy-digital/litex/commit/29a8c3cdb)).
- **software/litesdcard**                          : Fixed warnings in litesdcard software ([PR #2273](https://github.com/enjoy-digital/litex/pull/2273)).
- **cpu/ibex**                                     : Fixed missing add_sources calls ([PR #2268](https://github.com/enjoy-digital/litex/pull/2268)).
- **tests/test_integration**                       : Fixed file mode to allow reading logs on boot failure ([PR #2264](https://github.com/enjoy-digital/litex/pull/2264)).
- **build/efinix**                                 : Fixed programmer compatibility and bitstream file copying, added CLKOUT_DYNPHASE_EN support ([PR #2247](https://github.com/enjoy-digital/litex/pull/2247)).
- **tools/litex_json2dts_linux**                   : Fixed USB OHCI DT naming (mac->usb) and L1 cache size reporting ([PR #2251](https://github.com/enjoy-digital/litex/pull/2251)).
- **build/colognechip**                            : Fixed DDR inversion issue ([PR #2274](https://github.com/enjoy-digital/litex/pull/2274)).
- **tests/test_integration**                       : Temporarily disabled coreblocks due to pipx issue ([bc25ed7fd](https://github.com/enjoy-digital/litex/commit/bc25ed7fd)).
- **platforms/xilinx_zcu106**                      : Fixed user button pin according to user guide ([PR #681](https://github.com/litex-hub/litex-boards/pull/681)).
- **targets/hyvision_pcie_opt01_revf**             : Fixed J9 pinout for correct board edge alignment ([PR #682](https://github.com/litex-hub/litex-boards/pull/682)).
- **platforms/berkeleylab_marble**                 : Removed IOSTANDARD from mgtrefclk pins to resolve Vivado warnings ([3e77bc6](https://github.com/litex-hub/litex-boards/commit/3e77bc6)).
- **litepcie/frontend/dma**                        : Added FIFO resets to LitePCIeDMABuffering to prevent incorrect behavior ([PR #148](https://github.com/enjoy-digital/litepcie/pull/148)).
- **litesdcard/phy/SDPHYClocker**                  : Fixed clock divider logic for div 0,1,2,3,4,5,8 cases ([PR #40](https://github.com/enjoy-digital/litesdcard/pull/40)).
- **soc/cores/naxriscv**                           : Fixed git submodule not being set to the right hash ([PR #2332](https://github.com/enjoy-digital/litex/pull/2332)).
- **bios/isr**                                     : Removed warning for "no previous prototype for 'plic_init' [-Wmissing-prototypes]" ([PR #2333](https://github.com/enjoy-digital/litex/pull/2333)).
- **tools/litex_json2dts_linux**                   : Fixed clint addition to DTS by checking memory map instead of CPU type ([PR #2335](https://github.com/enjoy-digital/litex/pull/2335)).
- **soc/interconnect/axi**                         : Fixed AXIInterfaces initialization with correct id_width ([PR #2320](https://github.com/enjoy-digital/litex/pull/2320)).
- **build/gowin/gowin.py**                         : Fixed WSL issue with Gowin toolchain detection ([PR #2308](https://github.com/enjoy-digital/litex/pull/2308)).
- **build/efinix**                                 : Fixed get_pad_name_xml for Topaz ([PR #2297](https://github.com/enjoy-digital/litex/pull/2297)).
- **build/io/efinix**                              : Fixed DDR Input timing ([PR #2311](https://github.com/enjoy-digital/litex/pull/2311)).
- **build/altera/common**                          : Fixed Agilex5SDRTristateImpl parameters and reset synchronizer ([PR #2318](https://github.com/enjoy-digital/litex/pull/2318)).
- **soc/cores/ram/efinix_hyperram**                : Fixed clkout frequency and TristateImpl for TSTriple ([PR #2295](https://github.com/enjoy-digital/litex/pull/2295)).
- **build/vivado**                                 : Fixed synth_ip warning by switching to non-project mode ([PR #2294](https://github.com/enjoy-digital/litex/pull/2294)).
- **build/vhd2v_converter**                        : Fixed mutable defaults in __init__ ([f8a1a213d](https://github.com/enjoy-digital/litex/commit/f8a1a213d)).
- **soc/doc**                                      : Fixed CSR register calculation for little endian ordering ([PR #2270](https://github.com/enjoy-digital/litex/pull/2270)).
- **build/[colognechip,gowin]/common**             : Fixed SDRInput parameters order in SDRTristateImpl ([PR #2328](https://github.com/enjoy-digital/litex/pull/2328)).
- **soc/cores/clock/intel_agilex**                 : Fixed clkin_name if signal type is ClockSignal ([587b1b374](https://github.com/enjoy-digital/litex/commit/587b1b374)).
- **bios/litedram**                                : Fixed indexes of csr_rd_buf_uint8 ([420591a1a](https://github.com/enjoy-digital/litex/commit/420591a1a)).
- **litepcie/phy/xilinx_usp/m_axis_rc_adapt_512b** : Fixed cq/rc typo ([51da1ba](https://github.com/enjoy-digital/litepcie/commit/51da1ba)).
- **litepcie/phy/s7pciephy**                       : Added false path constraint on pclk_sel signal ([44362da](https://github.com/enjoy-digital/litepcie/commit/44362da)).
- **litei2c/phy**                                  : Fixed truncating complaint from toolchain ([6fbef5b](https://github.com/enjoy-digital/litei2c/commit/6fbef5b)).
- **liteeth/phy/titanium_lvds_1000basex**          : Fixed regression on presented data to Decoder8b10bIdleChecker ([fec700b](https://github.com/enjoy-digital/liteeth/commit/fec700b)).
- **platforms/berkeleylab_obsidian**               : Fixed configuration of SPI flash ([PR #692](https://github.com/litex-hub/litex-boards/pull/692)).
- **platforms/colorlight_5a_75e**                  : Fixed typo in connectors ([PR #685](https://github.com/litex-hub/litex-boards/pull/685)).
- **targets/arrow_axe5000**                        : Fixed call to Agilex5PLL after litex core changes ([PR #694](https://github.com/litex-hub/litex-boards/pull/694)).

[> Added
--------
- **sim/verilator**                                : Added state save and load functions for Verilator simulation ([PR #2261](https://github.com/enjoy-digital/litex/pull/2261)).
- **build/xilinx/vivado**                          : Added Device Image (pdi) generation support for Vivado builds ([PR #2272](https://github.com/enjoy-digital/litex/pull/2272)).
- **software/bios/liteeth**                        : Added ping command and BIOS support for responding to ping requests ([PR #2287](https://github.com/enjoy-digital/litex/pull/2287)).
- **cores/cpu/vexiiriscv**                         : Added architecture details in human-readable name ([PR #2286](https://github.com/enjoy-digital/litex/pull/2286)).
- **tools/json2dts_zephyr**                        : Added default IRQ priority of 1 for PLIC ([PR #2285](https://github.com/enjoy-digital/litex/pull/2285)).
- **software/litesdcard**                          : Added support for changing PHY modes (x1, x4, x8) ([PR #2275](https://github.com/enjoy-digital/litex/pull/2275)).
- **soc/cores/prbs**                               : Added errors_width parameter to improve timing in some designs ([bc6a6f015](https://github.com/enjoy-digital/litex/commit/bc6a6f015)).
- **software/bios/liteeth/udp**                    : Added broadcast support ([PR #2263](https://github.com/enjoy-digital/litex/pull/2263)).
- **tools/json2dts_zephyr**                        : Updated interrupt naming for SPI flash core ([PR #2271](https://github.com/enjoy-digital/litex/pull/2271)).
- **soc/cores/spi**                                : Added interrupt support for LiteSPI and moved PHY to core for single CSR slot usage ([2438c558e](https://github.com/enjoy-digital/litex/commit/2438c558e), [befcbbc9b](https://github.com/enjoy-digital/litex/commit/befcbbc9b)).
- **soc/cores/i2c**                                : Added interrupt support for LiteI2C ([3b4708db4](https://github.com/enjoy-digital/litex/commit/3b4708db4)).
- **tests/test_integration**                       : Added ibex and vexiiriscv CPUs to boot tests ([d170f08dd](https://github.com/enjoy-digital/litex/commit/d170f08dd), [e3b8bf653](https://github.com/enjoy-digital/litex/commit/e3b8bf653)).
- **build/tools**                                  : Added _tail_file function and tail_log parameter to subprocess_call_filtered for colored build log output ([f5e5514b3](https://github.com/enjoy-digital/litex/commit/f5e5514b3)).
- **soc/integration**                              : Exposed check_duplicate argument in add_ip_address_constants and add_mac_address_constants ([PR #2259](https://github.com/enjoy-digital/litex/pull/2259)).
- **build/lattice/icestorm**                       : Added support for pin pull-up configuration ([PR #2256](https://github.com/enjoy-digital/litex/pull/2256)).
- **cores/usb_ohci**                               : Added InterruptPin class for standard IRQ allocation ([PR #2252](https://github.com/enjoy-digital/litex/pull/2252)).
- **tools/litex_json2dts_linux**                   : Added local MAC address to ethernet device tree and L2 cache topology support ([a3b36c125](https://github.com/enjoy-digital/litex/commit/a3b36c125), [2781b0124](https://github.com/enjoy-digital/litex/commit/2781b0124)).
- **cpu/naxriscv**                                 : Added support for generating cache sections in DTS ([e1986d554](https://github.com/enjoy-digital/litex/commit/e1986d554)).
- **soc/cores/clock**                              : Added CologneChip GateMatePLL import ([eda4e49b7](https://github.com/enjoy-digital/litex/commit/eda4e49b7)).
- **litesdcard/phy**                               : Added support for changing modes (x1, x4, x8) ([PR #38](https://github.com/enjoy-digital/litesdcard/pull/38)).
- **liteiclink/serdes/gtp_7series**                : Added rx_prbs_errors_width parameter to add_prbs_control and add_controls ([ef9c295](https://github.com/enjoy-digital/liteiclink/commit/ef9c295)).
- **litei2c/master**                               : Added interrupt option ([ad7ec63](https://github.com/enjoy-digital/litei2c/commit/ad7ec63)).
- **litepcie/gen**                                 : Added support for specifying DMA data_width in .yml configuration ([2682042](https://github.com/enjoy-digital/litepcie/commit/2682042)).
- **litepcie/frontend/ptm**                        : Added named Time Clock Domain to avoid conflicts in larger designs ([029a578](https://github.com/enjoy-digital/litepcie/commit/029a578)).
- **soc/cores/cpu/zynq7000**                       : Added UART, SPI, I2C, and GPIO support with EMIO/PS configurations ([PR #2340](https://github.com/enjoy-digital/litex/pull/2340)).
- **soc/cores/cpu/coreblocks**                     : Added small_linux config and CoreSoCks wrapper support ([PR #2339](https://github.com/enjoy-digital/litex/pull/2339)).
- **soc/cores/clock/intel_agilex**                 : Added Altera Agilex PLL core ([PR #2324](https://github.com/enjoy-digital/litex/pull/2324)).
- **build/altera/quartus**                         : Added noprune attribute support and clock_constraints object ([PR #2336](https://github.com/enjoy-digital/litex/pull/2336)).
- **build/lattice/trellis**                        : Added argument to override bitstream's IDCODE ([PR #2309](https://github.com/enjoy-digital/litex/pull/2309)).
- **build/altera/common**                          : Added specials for Agilex DifferentialInput/Output and Tristate Implementation ([PR #2318](https://github.com/enjoy-digital/litex/pull/2318)).
- **build/lattice**                                : Added SDR tristate specialisation for ECP5 ([PR #2326](https://github.com/enjoy-digital/litex/pull/2326)).
- **build/altera/quartus**                         : Added selection between quartus_cpf and quartus_pfg for file conversion ([PR #2318](https://github.com/enjoy-digital/litex/pull/2318)).
- **software/system**                              : Added functions to clean/invalidate/flush cache ([PR #2325](https://github.com/enjoy-digital/litex/pull/2325)).
- **soc/cores/cpu/vexiiriscv**                     : Added cache management functions ([PR #2325](https://github.com/enjoy-digital/litex/pull/2325)).
- **liteeth/mac/core**                             : Allowed using core_dw smaller than phy_dw ([PR #177](https://github.com/enjoy-digital/liteeth/pull/177)).
- **liteeth/mac**                                  : Used one CRC engine for Checker ([PR #183](https://github.com/enjoy-digital/liteeth/pull/183)).
- **liteeth/phy/rmii**                             : Added use of rx_er if it exists ([PR #194](https://github.com/enjoy-digital/liteeth/pull/194)).
- **liteeth/phy/titanium/trion rgmii**             : Added improvements and multibit IO support ([PR #181](https://github.com/enjoy-digital/liteeth/pull/181)).
- **litesdcard/phy**                               : Added CSRs for timeout configuration ([PR #43](https://github.com/enjoy-digital/litesdcard/pull/43)).
- **litespi/phy/sdr**                              : Added extra_latency like in DDR phy ([PR #89](https://github.com/enjoy-digital/litespi/pull/89)).
- **litespi/modules**                              : Added MX25U25645G flash ([PR #88](https://github.com/enjoy-digital/litespi/pull/88)).
- **litedram/modules**                             : Added W989D6DBGX6 ([PR #366](https://github.com/enjoy-digital/litedram/pull/366)).
- **litei2c/clkgen**                               : Added scl_o/oe signals for code simplification and external access ([166e2f6](https://github.com/enjoy-digital/litei2c/commit/166e2f6)).
- **liteiclink/serdes/gtx_7series**                : Added rx_prbs_errors_width parameter ([1cddcd4](https://github.com/enjoy-digital/liteiclink/commit/1cddcd4)).
- **build/radiant**                                : Added false paths to .pdc file generation ([PR #2312](https://github.com/enjoy-digital/litex/pull/2312)).
- **build/efinix/clock/pll**                       : Added nclkout argument to create_clkout ([PR #2300](https://github.com/enjoy-digital/litex/pull/2300)).
- **Boards/targets**                               : Added support for **Machdyne Kolsch** ([PR #679](https://github.com/litex-hub/litex-boards/pull/679)).
- **Boards/targets**                               : Added support for **Alinx AX7203** with platform and target ([PR #678](https://github.com/litex-hub/litex-boards/pull/678)).
- **Boards/targets**                               : Added HDMI support for Alinx AX7203 ([PR #680](https://github.com/litex-hub/litex-boards/pull/680)).
- **Boards/targets**                               : Added USB option using PMOD connector JB for Digilent Nexys Video (2 USB-OHCI ports) ([PR #672](https://github.com/litex-hub/litex-boards/pull/672)).
- **Boards/targets**                               : Added SD card support for CologneChip GateMate EVB ([PR #673](https://github.com/litex-hub/litex-boards/pull/673)).
- **Boards/targets**                               : Added HyperRAM support for CologneChip GateMate EVB ([PR #670](https://github.com/litex-hub/litex-boards/pull/670)).
- **Boards/targets**                               : Added missing enable pin for 20 MHz VCXO on BerkeleyLab Marble ([PR #676](https://github.com/litex-hub/litex-boards/pull/676)).
- **Boards/targets**                               : Added support for **Icepi Zero** ([PR #693](https://github.com/litex-hub/litex-boards/pull/693)).
- **Boards/targets**                               : Added support for **Berkeley Lab Obsidian A35** ([PR #686](https://github.com/litex-hub/litex-boards/pull/686)).
- **Boards/targets**                               : Added support for **Efinix TZ170 J484 Dev Kit** ([PR #691](https://github.com/litex-hub/litex-boards/pull/691)).
- **Boards/targets**                               : Added support for **Arrow AXE5000** (Altera Agilex 5) ([PR #689](https://github.com/litex-hub/litex-boards/pull/689)).
- **Boards/targets**                               : Added support for **ULX5M-GS** ([PR #688](https://github.com/litex-hub/litex-boards/pull/688)).
- **Boards/targets**                               : Added support for **QMTech Cyclone10 Starter Kit - 10CL080** ([PR #683](https://github.com/litex-hub/litex-boards/pull/683)).

[> Changed
----------
- **soc/litesdcard**                               : Moved litesdcard modules to a parent class for add_sdcard(), renamed irq to ev ([PR #2281](https://github.com/enjoy-digital/litex/pull/2281), [b46e06182](https://github.com/enjoy-digital/litex/commit/b46e06182)).
- **software/litesdcard**                          : Removed limitations for clock divider ([PR #2276](https://github.com/enjoy-digital/litex/pull/2276)).
- **cpu/vexiiriscv**                               : Updated recommended commit to latest dev ([ee6c3102b](https://github.com/enjoy-digital/litex/commit/ee6c3102b)).
- **build/efinix/efinity**                         : Updated to use efx_run for builds, added tail_log parameter for log redirection, and set CLKOUT_DYNPHASE_EN ([PR #2247](https://github.com/enjoy-digital/litex/pull/2247), [83a14dd64](https://github.com/enjoy-digital/litex/commit/83a14dd64)).
- **build/colognechip**                            : Removed forced ram_style=distributed ([PR #2254](https://github.com/enjoy-digital/litex/pull/2254)).
- **ci/tooling**                                   : Updated to use GHDL from OSS CAD Suite and bumped to latest version ([5e58ab1ba](https://github.com/enjoy-digital/litex/commit/5e58ab1ba)).
- **platforms/digilent_nexys_video**               : Added PMOD connectors ([6bbca0e](https://github.com/litex-hub/litex-boards/commit/6bbca0e)).
- **targets/berkeleylab_marble**                   : Made max I2C interface optional ([74cd48d](https://github.com/litex-hub/litex-boards/commit/74cd48d)).
- **platforms/berkeleylab_marble/marblemini**      : Removed redundant files ([PR #675](https://github.com/litex-hub/litex-boards/pull/675)).
- **litesdcard/phy/SDPHYClocker**                  : Reworked clock divider to use down-counter, simplified logic, and ensured frequency <= configured ([PR #40](https://github.com/enjoy-digital/litesdcard/pull/40)).
- **litesdcard/phy**                               : Set default data_width to 4x ([PR #38](https://github.com/enjoy-digital/litesdcard/pull/38)).
- **soc/cores/cpu/coreblocks**                     : Updated to 2025-09 with small_linux config and Vivado hacks ([PR #2339](https://github.com/enjoy-digital/litex/pull/2339)).
- **soc/cores/clock/intel_agilex**                 : Refactored PLL core and updated SDC constraints ([PR #2336](https://github.com/enjoy-digital/litex/pull/2336)).
- **build/altera/platform**                        : Refactored Agilex special overrides for Agilex 3 support ([PR #2334](https://github.com/enjoy-digital/litex/pull/2334)).
- **soc/interconnect/axi**                         : Optimized AXI bus with mode, split read/write, and faster read ([PR #2289](https://github.com/enjoy-digital/litex/pull/2289)).
- **build/colognechip**                            : Enabled multipliers with peppercorn toolchain ([PR #2319](https://github.com/enjoy-digital/litex/pull/2319)).
- **soc/cores/uart**                               : Switched to EventSourceLevel irq and exposed rx_fifo_rx_we ([PR #2319](https://github.com/enjoy-digital/litex/pull/2319)).
- **soc/integration/csr**                          : Improved read/write handling for big/little endian ordering ([PR #2270](https://github.com/enjoy-digital/litex/pull/2270)).
- **soc/ethernet**                                 : Used phy_cd name directly from phy for multiple PHY support ([PR #2163](https://github.com/enjoy-digital/litex/pull/2163)).
- **soc/litespi**                                  : Improved add_spi_flash with QPI activation, kwargs, and wait for quad mode ([PR #2313](https://github.com/enjoy-digital/litex/pull/2313)).
- **build/io/Tristate**                            : Added support for i/i1/i2 being None in SDR/DDR Tristate ([PR #2310](https://github.com/enjoy-digital/litex/pull/2310)).
- **build/efinix/common**                          : Updated to use add_iface_io ([PR #2293](https://github.com/enjoy-digital/litex/pull/2293)).
- **build/xilinx/vivado**                          : Switched to non-project mode and made verilog headers global ([PR #2294](https://github.com/enjoy-digital/litex/pull/2294)).
- **soc/cores/ram/efinix_hyperram**                : Modernized PLL uses and exposed CTOR params ([PR #2295](https://github.com/enjoy-digital/litex/pull/2295)).
- **build/efinix/clock/pll**                       : Used margin for frequency check ([PR #2299](https://github.com/enjoy-digital/litex/pull/2299)).
- **liteeth/mac/core**                             : Added docstrings and allowed smaller core_dw ([PR #177](https://github.com/enjoy-digital/liteeth/pull/177)).
- **liteeth/mac/sram**                             : Simplified logic and named memory ([PR #191](https://github.com/enjoy-digital/liteeth/pull/191)).
- **liteeth/phy/titanium_lvds_1000basex**          : Cleaned up and refactored for readability and reduced resources ([PR #192](https://github.com/enjoy-digital/liteeth/pull/192)).
- **litesdcard/phy**                               : Made use of LiteXModule ([PR #46](https://github.com/enjoy-digital/litesdcard/pull/46)).
- **litesdcard/crc16**                             : Moved CRC16 check to phy and reworked tests ([PR #45](https://github.com/enjoy-digital/litesdcard/pull/45)).
- **litesdcard/core**                              : Moved block delimiter into core ([PR #44](https://github.com/enjoy-digital/litesdcard/pull/44)).
- **litespi/core/mmap**                            : Excluded write code when disabled ([PR #87](https://github.com/enjoy-digital/litespi/pull/87)).
- **litespi/phy**                                  : Added kwargs support ([ef806bd](https://github.com/enjoy-digital/litespi/commit/ef806bd)).
- **litei2c/phy/clkgen**                           : Made scl_o a Constant again and removed unused i from SDRTristate ([8b6f5e8](https://github.com/enjoy-digital/litei2c/commit/8b6f5e8), [c34fdb8](https://github.com/enjoy-digital/litei2c/commit/c34fdb8)).
- **ci/github_actions**                            : Bumped actions/setup-python from 5 to 6 ([PR #690](https://github.com/litex-hub/litex-boards/pull/690)).
- **ci/github_actions**                            : Bumped actions/checkout from 4 to 5 ([PR #687](https://github.com/litex-hub/litex-boards/pull/687)).


[> 2025.04, released on May 26th 2025
-------------------------------------

[> Fixed
--------
- **build/io**                               : Fixed length check after wrapping for SDRIO/Tristate to handle int and bool types correctly ([PR #2105](https://github.com/enjoy-digital/litex/pull/2105)).
- **soc/integration/soc/add_slave**          : Fixed crash when `strip_origin` is *None* by correctly using `self.regions[name]` ([86b052e41](https://github.com/enjoy-digital/litex/commit/86b052e41)).
- **build/anlogic**                          : Fixed Tang Dynasty programmer exit-hang and corrected “TangDinasty” typo → **TangDynasty** ([79d206fc2](https://github.com/enjoy-digital/litex/commit/79d206fc2), [6f8e65e10](https://github.com/enjoy-digital/litex/commit/6f8e65e10)).
- **build/io / gen/fhdl/expression**         : Fixed slice-resolution regression introduced by PR #2161 ([666c9b430](https://github.com/enjoy-digital/litex/commit/666c9b430)).
- **soc/software/bios/litedram**             : Fixed write-levelling helpers being called on DDR2 parts ([e88fbfb95](https://github.com/enjoy-digital/litex/commit/e88fbfb95)).
- **gcc flags**                              : Fixed wrong `-march` value for *Minerva* and *Sentinel* CPUs ([866d04025](https://github.com/enjoy-digital/litex/commit/866d04025)).
- **litedram/phy/s7ddrphy**                  : Fixed unintended write-leveling on DDR2 modules ([632e921](https://github.com/enjoy-digital/litedram/commit/632e921)).
- **liteeth/phy/rmii**                       : Fixed speed-detect FSM corner cases and RX-path glitches ([6e7a70c](https://github.com/enjoy-digital/liteeth/commit/6e7a70c)).
- **litepcie/software/kernel**               : Fixed `liteuart` build on Linux ≥ 6.10/6.11 ([3b5c70f](https://github.com/enjoy-digital/litepcie/commit/3b5c70f), [be0abeb](https://github.com/enjoy-digital/litepcie/commit/be0abeb)).
- **tools/json2dts_zephyr**                  : Fixed missing interrupt 0, MDIO handling, and buffer split issues ([2a97b0308](https://github.com/enjoy-digital/litex/commit/2a97b0308)).
- **misc**                                   : Fixed uptime counter width (now `uint64`) and removed assorted static-analysis warnings ([724034564](https://github.com/enjoy-digital/litex/commit/724034564)).

[> Added
--------
- **cores/cpu/ibex**                         : Aligned with latest RTL, fixed file paths, and addressed Verilator parameter type limitation ([PR #2160](https://github.com/enjoy-digital/litex/pull/2160)).
- **cores/cpu/openc906**                     : Aligned with latest RTL, removed unused file lists, and updated bus conversion logic ([PR #2159](https://github.com/enjoy-digital/litex/pull/2159)).
- **build/io**                               : Added multibit/bus variants of SDR and DDR IO for Efinix and other platforms ([PR #2105](https://github.com/enjoy-digital/litex/pull/2105)).
- **gen/fhdl/expression**                    : Resolved slice handling completely to reduce complexity in Verilog files ([PR #2161](https://github.com/enjoy-digital/litex/pull/2161)).
- **cores/cpu/coreblocks**                   : Added new open-source RISC-V “Coreblocks” CPU support ([fb6d78c92](https://github.com/enjoy-digital/litex/commit/fb6d78c92)).
- **build/vhd2v_converter**                  : Added `CTOR` argument to bypass source-flattening when desired ([138379f3d](https://github.com/enjoy-digital/litex/commit/138379f3d)).
- **fhdl/verilog/slice_lowerer**             : Added inversion support and lowering of specials ([7efbd0535](https://github.com/enjoy-digital/litex/commit/7efbd0535), [32041f21c](https://github.com/enjoy-digital/litex/commit/32041f21c)).
- **build/anlogic**                          : Added *TangDynastyProgrammer* backend and DR1V90 MEG484 device support ([c77f2e834](https://github.com/enjoy-digital/litex/commit/c77f2e834), [2387bc6be](https://github.com/enjoy-digital/litex/commit/2387bc6be)).
- **build/colognechip**                      : Added native *CC_IOBUF* tristate and open-source *Peppercorn* flow ([62c9b9eb3](https://github.com/enjoy-digital/litex/commit/62c9b9eb3), [1e259f5ef](https://github.com/enjoy-digital/litex/commit/1e259f5ef)).
- **soc/cores/clock/xilinx_common**          : Added Dynamic-Phase-Shift (DPS) interface exposure ([2c98fed25](https://github.com/enjoy-digital/litex/commit/2c98fed25)).
- **soc/cores/clock/efinix**                 : Added on-chip flash programmer and *Topaz* FPGA family support ([761184110](https://github.com/enjoy-digital/litex/commit/761184110), [a0159e18a](https://github.com/enjoy-digital/litex/commit/a0159e18a)).
- **axi/Wishbone2AXILite**                   : Added one-cycle faster implementation ([d631d810b](https://github.com/enjoy-digital/litex/commit/d631d810b)).
- **litepcie PHYs**                          : Added *Certus Pro-NX* PCIe PHY ([e157d1e](https://github.com/enjoy-digital/litepcie/commit/e157d1e)) and *Gowin Arora V* PCIe PHY ([e14cf57](https://github.com/enjoy-digital/litepcie/commit/e14cf57)).
- **litepcie/frontend/wishbone**             : Added 64-bit addressing and byte-addressable mode ([5f15aa7](https://github.com/enjoy-digital/litepcie/commit/5f15aa7)).
- **litescope**                              : Added automatic group data-width padding and `--port` CLI flag ([021a834](https://github.com/enjoy-digital/litescope/commit/021a834)).
- **litedram**                               : Added DDR2 device *K4T1G164QGBCE7* definition ([118e291](https://github.com/enjoy-digital/litedram/commit/118e291)).
- **liteeth/phy/rmii**                       : Added automatic 10/100 Mb/s speed-detect FSM ([bbc4eb7](https://github.com/enjoy-digital/liteeth/commit/bbc4eb7)).
- **litespi**                                : Added unified bus abstraction (PR #81) and offset-less mmap mode (PR #82).
- **Boards/targets**                         : Added support for **mlkpai FS01 DR1V90M**, **HyVision PCIe opt01 revF**, **Alinx AX7020/7010** (PS7 DDR), **Kintex-7 Base C**, **Colorlight 5A-75E v8.2**, **Certus-Pro-NX Versa**, **Sipeed Tang Console / Mega 138k Pro / Nano 20k**, **Efinix Ti375 C529** (2× SFP, DDR, FMC-LPC) and several others (see commit history).

[> Changed
----------
- **gen/fhdl/instance**                      : Switched to using `expression.py` for expression generation ([e71e404ef](https://github.com/enjoy-digital/litex/commit/e71e404ef)).
- **gen/fhdl**                               : Moved expression generation functions to `expression.py` for better organization ([0bfaf39d5](https://github.com/enjoy-digital/litex/commit/0bfaf39d5)).
- **build/yosys_nextpnr/xilinx**             : Injects `--freq` automatically from reported Fmax ([fce56fae8](https://github.com/enjoy-digital/litex/commit/fce56fae8)).
- **tools/json2dts_zephyr**                  : Rewritten for modularity; adds optional overlay and buffer splitting ([778d39d5c](https://github.com/enjoy-digital/litex/commit/778d39d5c)…).
- **build/common/TristateImpl**              : Added wide-`oe` support and stricter signal-length checks ([913a70962](https://github.com/enjoy-digital/litex/commit/913a70962), [a019fd4ed](https://github.com/enjoy-digital/litex/commit/a019fd4ed)).
- **Clocking cores**                         : Exposed DPS on Xilinx, enabled PLLA on GW5AT, improved async DDR I/O.
- **CI/tooling**                             : Migrated CI to Ubuntu 22.04, switched to OSS-CAD-Suite, added Python 3.11 compatibility.

[> 2024.12, released on January 7th 2025
----------------------------------------

[> Fixed
--------
- **tools/litex_client**                     : Fixed error handling and timeout management ([1225bf45](https://github.com/enjoy-digital/litex/commit/1225bf45), [fc529dca](https://github.com/enjoy-digital/litex/commit/fc529dca), [b9cc5c58](https://github.com/enjoy-digital/litex/commit/b9cc5c58)).
- **soc/cores/led**                          : Fixed WS2812 LED count calculation ([PR #2142](https://github.com/enjoy-digital/litex/pull/2142)).
- **build/vhd2v_converter**                  : Fixed instance handling and robustness ([PR #2145](https://github.com/enjoy-digital/litex/pull/2145), [8254a349f](https://github.com/enjoy-digital/litex/commit/8254a349f)).
- **soc/cores/jtag**                         : Fixed ECP5JTAG initialization for Diamond/Trellis toolchains ([4368d5a9e](https://github.com/enjoy-digital/litex/commit/4368d5a9e)).
- **litespi**                                : Fixed SPI Flash erase functionality and debug output ([e61196b1c](https://github.com/enjoy-digital/litex/commit/e61196b1c), [63fa4fda8](https://github.com/enjoy-digital/litex/commit/63fa4fda8)).
- **liteeth/phy/pcs_1000basex**              : Fixed deadlock in AUTONEG_WAIT_ABI state and improved RX alignment ([e5746c8](https://github.com/enjoy-digital/liteeth/commit/e5746c8)).
- **liteeth/phy/pcs_1000basex**              : Fixed RX Config consistency check and cleanup pass ([20e9ea6](https://github.com/enjoy-digital/liteeth/commit/20e9ea6), [cd2274d](https://github.com/enjoy-digital/liteeth/commit/cd2274d)).
- **litepcie/software/kernel**               : Fixed compilation warnings and removed unused functions ([867c818](https://github.com/enjoy-digital/litepcie/commit/867c818)).
- **platforms/limesdr_mini_v2**              : Fixed SPI Flash pinout (MOSI <-> MISO) ([3b8c558](https://github.com/litex-hub/litex-boards/commit/3b8c558)).
- **efinix_trion_t20_bga256_dev_kit**        : Fixed ClockSignal handling ([77cb9a5](https://github.com/litex-hub/litex-boards/commit/77cb9a5)).

[> Added
--------
- **cpu/zynqmp**                             : Added SGMII support via PL and optional PTP ([PR #2095](https://github.com/enjoy-digital/litex/pull/2095)).
- **liteeth/phy**                            : Improved 1000BaseX/2500BaseX PCS/PHYs ([PR #174](https://github.com/enjoy-digital/liteeth/pull/174)).
- **cpu/urv**                                : Added uRV CPU support (RISC-V CPU use in White Rabbit project) ([PR #2098](https://github.com/enjoy-digital/litex/pull/2098)).
- **tools/litex_client**                     : Added memory regions table, auto-refresh, and binary file read/write support ([d3258a398](https://github.com/enjoy-digital/litex/commit/d3258a398), [3875a4c1f](https://github.com/enjoy-digital/litex/commit/3875a4c1f), [95f37a82e](https://github.com/enjoy-digital/litex/commit/95f37a82e)).
- **tools/litex_client**                     : Added endianness configuration for memory accesses ([71e802aec](https://github.com/enjoy-digital/litex/commit/71e802aec)).
- **cores/clock/intel**                      : Added reset support to Intel PLLs ([PR #2139](https://github.com/enjoy-digital/litex/pull/2139)).
- **cores/cpu/vexiiriscv**                   : Added PMP support and MACSG (DMA-based Ethernet) support ([PR #2130](https://github.com/enjoy-digital/litex/pull/2130)).
- **build/altera/quartus**                   : Added `.svf` generation for OpenFPGALoader compatibility ([e91d4d1a3](https://github.com/enjoy-digital/litex/commit/e91d4d1a3)).
- **build/efinix**                           : Added SEU (Single Event Upset) interface ([PR #2128](https://github.com/enjoy-digital/litex/pull/2128)).
- **soc/cores/bitbang/i2c**                  : Added `connect_pads` parameter for flexible I2C pad handling ([fdd7c97ce](https://github.com/enjoy-digital/litex/commit/fdd7c97ce)).
- **platforms/xilinx_zcu102**                : Added all SFP connectors ([0eabebf](https://github.com/litex-hub/litex-boards/commit/0eabebf)).
- **targets/sipeed_tang_nano_20k**           : Added SPI Flash and HDMI support ([2d25408](https://github.com/litex-hub/litex-boards/commit/2d25408)).
- **targets/embedfire_rise_pro**             : Added support for EmbedFire Rise Pro ([d7f2b5a](https://github.com/litex-hub/litex-boards/commit/d7f2b5a)).
- **targets/alibaba_vu13p**                  : Added support for Alibaba VU13P ([e8e833d](https://github.com/litex-hub/litex-boards/commit/e8e833d)).
- **targets/efinix_ti375_c529_dev_kit**      : Added VexII Ethernet support ([4c61bac](https://github.com/litex-hub/litex-boards/commit/4c61bac)).
- **targets/efinix_trion_t20_mipi_dev_kit**  : Added simple flash fix ([1727d30](https://github.com/litex-hub/litex-boards/commit/1727d30)).
- **targets/machdyne_mozart_mx2**            : Added support for Mozart MX2 ([399f10f](https://github.com/litex-hub/litex-boards/commit/399f10f)).
- **targets/tec0117**                        : Updated to work with Apicula ([9d68972](https://github.com/litex-hub/litex-boards/commit/9d68972)).

[> Changed
----------
- **tools/litex_client**                     : Improved GUI presentation and memory region display ([5c156b499](https://github.com/enjoy-digital/litex/commit/5c156b499), [d3258a398](https://github.com/enjoy-digital/litex/commit/d3258a398)).
- **liteeth/phy/pcs_1000basex**              : Refactored RX Config consistency check and improved timers ([b783639](https://github.com/enjoy-digital/liteeth/commit/b783639), [fe69248](https://github.com/enjoy-digital/liteeth/commit/fe69248)).
- **liteeth/phy/a7_1000basex**               : Updated ALIGN_COMMA_WORD/RXCDR_CFG settings from Xilinx wizard ([04fc888](https://github.com/enjoy-digital/liteeth/commit/04fc888)).
- **liteeth/mac/core**                       : Switched to LiteXModule for better modularity ([f30d6ef](https://github.com/enjoy-digital/liteeth/commit/f30d6ef)).

[> 2024.08, released on September 27th 2024
-------------------------------------------
	[> Fixed
	--------
	- cpu/zynq7000                  : Fixed AXI version to AXI3.
	- build/vhd2v_converter         : Fixed instance replace robustness.
	- tools/litex_json2renode       : Corrected VexRiscv variants (#1984).
	- software/liblitespi           : Fixed xor-used-pow bug (#2001).
	- soc                           : Fixed AHB2Wishbone bridge creation (#1998).
	- soc                           : Fixed parameters propagation for AXI data-width conversion (#1997).
	- soc/cores/clock/colognechip   : Fixed and reworked locked signal handling.
	- litesdcard                    : Fixed data_i sampling (https://github.com/enjoy-digital/litesdcard/pull/34).
	- litespi/mmap                  : Fixed dummy bits (https://github.com/litex-hub/litespi/pull/71).
	- sim/verilator                 : Fixed .fst empty dump with short simulation.

	[> Added
	--------
	- cpu/vexiiriscv                : Added initial support (#1923).
	- builder                       : Added default generation of exports with default names to output_dir (#1978).
	- litex.gen                     : Added byte size definitions and use them in targets/json2dts.
	- litepcie                      : Added external QPLL support/sharing for Xilinx Artix7.
	- cores/zynq7000/mp             : Improved integration, added peripherals supports (#1994).
	- software/bios                 : Generalized IRQ handling approach between CPUs.
	- cores/video                   : Added fifo_depth parameter to add_video_framebuffer (#1931).
	- gen/common                    : Added byte size definitions (KILOBYTE, MEGABYTE, GIGABYTE).
	- tools/litex_json2dts_linux    : Simplified CPU architecture/RISC-V ISA.
	- soc                           : Added add_spi_master method (#1985).
	- tools/litex_json2dts_zephyr   : Added spimaster/spiflash handlers (#1985).
	- tools/litex_json2renode       : Added .elf bios option (#1984).
	- cores                         : Added Watchdog core and Zephyr support (#1996).
	- soc                           : Added add_spi_ram method (#2028).
	- build                         : Added initial Apicula (Gowin) Platform support (#2036).
	- build                         : Added initial Agilex5 support.
	- liteeth/mac                   : Improved broadcast filtering logic in Hybrid Mode (https://github.com/enjoy-digital/liteeth/pull/165).
	- soc/cores/hyperbus            : Rewritten HyperRAM core to enhance performance and add new features (#2053).
	- litedram                      : Added bank_byte_alignement parameter for improvded address mapping (https://github.com/enjoy-digital/litedram/pull/360).
	- build/efinix                  : Added support for more primitives and improved clocking support. (#2060, #2075).
	- software/bios                 : Added spiram support (#2058).
	- liteeth/etherbone             : Added 64-bit support to Etherbone.
	- liteeth/liteeth_gen           : Added XGMII support (PHY handled externally).
	- soc/interconnect/stream       : Added optional CSR to Multiplexer/Demultiplexer and Crossbar module.
	- tools/litex_json2dts_zephyr   : Improved support/update ((#1974).
	- soc/cores/jtag                : Added Spartan7 support (#2076).
	- liteeth/phy                   : Added 1000BASEX support for Virtex7 (https://github.com/enjoy-digital/liteeth/pull/171).
	- liteeth/phy                   : Improved RGMII support on Efinix Titanium/Trion (https://github.com/enjoy-digital/liteeth/pull/168).
	- liteiclink/serdes             : Added GTH/Virtex7 support (https://github.com/enjoy-digital/liteeth/pull/23).
	- litespi/phy                   : Improved logic and cleanup (https://github.com/litex-hub/litespi/pull/73).
	- litespi/mmap                  : Added write support for SPIRAM devices (https://github.com/litex-hub/litespi/pull/70).
	- build/efinix                  : Improved name elaboration for Signals/Clocks to simplify user design.

	[> Changed
	----------
	- integration/builder           : Changed export behavior to now generate csr.csv and csr.json by default to output_dir.
	- csr_bus                       : Added .re signal (#1999).

[> 2024.04, released on June 5th 2024
-------------------------------------
	[> Fixed
	--------
	- integration/soc               : Fixed typo in cpu mem_bus axi-via-wb downconvert
	- interconnect/ahb/AHB2Wishbone : Fixed size check that was too restrictive.
	- liteeth/phy/gw5rgmii          : Fixed Clk assignments.
	- build/efinix/programmer       : Updated for compatibility with latest Efinity versions.
	- litespi/software:             : Fixed SPI Flash Clk Divider computation when with L2 Cache.
	- litepcie/us(p)pciephy         : Fixed x8 / 256-bit wide case.
	- litex_sim/serial2console      : Fixed RX backpressure handling.
	- litedram/frontend/avalon      : Fixed and cleaned-up.
	- litex_sim/video               : Fixed pixel format to RGBA.
	- build/xilinx/common           : Fixed missing clk parameter on XilinxSDRTristateImpl.
	- soc/interconnect              : Fixed CSR/LiteXModule issue on WishboneSRAM/AXILiteSRAM.

	[> Added
	--------
	- build/openfpgaloader          : Added kwargs support to flash for specific/less common cases.
	- cpu/gowin_emcu                : Improved/Cleaned-up.
	- interconnect/ahb              : Added data_width/address_width parameters.
	- interconnect/ahb              : Added proper byte/sel support to AHB2Wishbone.
	- cpu/gowin_ae350               : Added initial support.
	- cpu/naxriscv                  : Updated arch definition and added rvc configuration parameters.
	- cpu/vexriscv_smp              : Added csr/clint/plic base address configuration parameters.
	- liteeth/phy                   : Added 7-Series/Ultrascale(+) 2500BaseX PHYs.
	- litespi/sdrphy:               : Allowed flash parameter to be None.
	- litespi/integration           : Improved integration and simplifications.
	- export/builder                : Added import/merge of Sub-SoCs .json files.
	- cpu/vexriscv_smp              : Added reset_address/vector support.
	- litex_sim                     : Added jtagremote support.
	- soc/add_master                : Added region support to allow/limit access to a specific region.
	- litex_json2dts_linux          : Added ip= bootarg when local/remote ips are defined.
	- cores/jtag                    : Added JTAGBone support for Zynq.
	- cores/ram/lattice_nx          : Improved timings.
	- liteeth_gen                   : Added QPLL/BUFH/BUFG parameters for A7 1000BaseX PHY.
	- litex_sim                     : Added Video Color Bar support.
	- cpu/neorv32                   : Updated to v1.9.7.
	- cores/hyperbus                : Added latency configuration and variable latency support.
	- cpu/cv32e41p                  : Added ISR support.
	- litesdcard                    : Improved SDPHYClocker (Timings).
	- cpu/vexriscv_smp              : Added baremetal IRQ support.
	- cpu/naxriscv                  : Added baremetal IRQ support.
	- cpu/zynqmp                    : Added Ethernet, UART, I2C support and improved AXI Master.
	- build/efinix                  : Added reconfiguration interface support.
	- build/efinix                  : Added tx_output_load configuration support.
    - cpu/eos_s3                    : Updated qlal4s3b_cell_macro clock and reset signals.
    - build/quicklogic              : Updated f4pga Makefile.
    - build/microsemi               : Updated libero_soc toolchain.

	[> Changed
	----------

[> 2023.12, released on December 25th 2023
------------------------------------------
	[> Fixed
	--------
	- liteeth/arp           : Fixed response on table update.
	- litesata/us(p)sataphy : Fixed data_width=32 case.
	- clock/lattice_ecp5    : Fixed phase calculation.
	- interconnect/axi      : Fixed AXILite2CSR read access (1 CSR cycle instead of 2).

	[> Added
	--------
	- cpu/naxriscv          : Added SMP support.
	- cpu/neorv32           : Added Debug support and update core complex.
	- cpu/vexriscv_smp      : Added hardware breakpoints support.
	- build/colognechip     : Added initial support.
	- soc/cores/video       : Added VTG/DMA synchronization stage to VideoFramebuffer.
	- litepcie/dma          : Improved LitePCIeDMADescriptorSplitter timings.
	- interconnect/wishbone : Added linear burst support to DownConverter.
	- integration/SoC       : Added with_jtagbone/with_uartbone support.
	- soc/cores             : Added Ti60F100 HyperRAM support.
	- build/xilinx          : Added initial OpenXC7 support (and improved Yosys-NextPnr).
	- build/efinix          : Added JTAG-UART/JTAGBone support.
	- interconnect/wishbone : Added byte/word addressing support.
	- cores/uart            : Added 64-bit addressing support to Stream2Wishbone.
	- tools                 : Added 64-bit addressing support to litex_server/client.
	- cores/cpu             : Added 64-bit support to CPUNone.
	- cores/cpu             : Added KianV (RV32IMA) initial support.
	- litedram              : Added initial GW5DDRPHY (compiles but not yet working).
	- build/gowin           : Added GowinTristate implementation.
	- litepcie              : Simplify/Cleanup Ultrascale(+) integration and allow .xci generation from .tcl.
	- litepcie              : Initial 64-bit DMA suppport.
	- bios                  : Added bios_format / --bios-format to allow enabling float/double printf.
	- soc/cores/clock       : Added proper clock feedback support on Efinix TRIONPLL/TITANIUMPLL.
	- liteiclink/phy        : Added Efinix support/examples on Trion/Titanium.
	- liteiclink/serwb      : Reused Etherbone from LiteEth to avoid code duplication.
	- interconnect          : Added 64-bit support to Wishbone/AXI-Lite/AXI.
	- jtag                  : Fixed firmware upload over JTAG-UART.
	- jtag                  : Improved speed (~X16) on JTABone/JTAGUART on all supported devices (Xilinx, Altera, Efinix, etc...)
	- litesata/phy          : Added GTHE4 support on Ultrascale+.
	- litex_boards          : Added Machdyne's Mozart with the Sechzig ML1 module support.
	- liteiclink            : Added clk_ratio of 1:2, 1:4 on Efinix/SerWB to make clocking more flexible.

	[> Changed
	----------
	- build/osfpga          : Removed initial support (would need feedbacks/updates).
	- python3               : Updated minimum python3 version to 3.7 (To allow more than 255 arguments in functions).

[> 2023.08, released on September 14th 2023
-------------------------------------------

	[> Fixed
	--------
	- lattice/programmer  : Fixed ECPDAP frequency specification.
	- soc/add_spi_sdcard  : Fixed Tristate build.
	- csr/fields          : Fixed access type checks.
	- software/liblitespi : Fixed support with debug.
	- cpu/vexriscv_smp    : Fixed compilation with Gowin toolchain (ex for Tang Nano 20K Linux).
	- liteiclink/serwb    : Fixed 7-Series initialization corner cases.
	- liteeth/core/icmp   : Fixed length check on LiteEthICMPEcho before passing data to buffer.
	- LiteXModule/CSR     : Fixed CSR collection order causing CSR clock domain to be changed.
	- litepcie/US(P)      : Fixed root cause of possible MSI deadlock.
	- soc/add_uart        : Fixed stub behavior (sink/source swap).
	- build/efinix        : Fixed AsyncFIFO issues (Minimum of 2 buffer stages).
	- software/gcc        : Fixed Ubuntu 22.04 GCC compilation issues.
	- build/efinix        : Fixed hardcoded version.
	- litedram/gw2ddrphy  : Fixed latencies and tested on Tang Primer 20K.

	[> Added
	--------
	- soc/cores/video              : Added low resolution video modes.
	- interconnect                 : Added initial AvalonMM support.
	- soc/interconnect/packet      : Avoided bypass of dispatcher with a single slave.
	- build/add_period_constraints : Improved generic platform and simplify specific platforms.
	- gen/fhdl/verilog             : Added parameter to avoid register initialization (required for ASIC).
	- litedram                     : Added clamshell topology support.
	- stream/Pipeline              : Added dynamic pipeline creation capability.
	- build/xilinx/vivado          : Added project commands to allow adding commands just after project creation.
	- soc/software                 : Moved helpers to hw/common.h.
	- tools/litex_json2dts_linux   : Added sys_clk to device tree and fixed dts warning.
	- tools/litex_json2dts_zephyr  : Added LiteSD defines.
	- build/yosys                  : Added quiet capability.
	- build/efinix                 : Improved Titanium support (PLL, DRIVE_STRENGTH, SLEW).
	- build/openfpgaloader         : Added -fpga-part and -index-chain support.
	- soc/add_spi_flash            : Added software_debug support.
	- software/liblitespi          : Added read_id support.
	- litex_boards                 : Added QMtech XC7K325T, VCU128, SITLINV_STVL7325_V2, Enclustra XU8/PE3 support.
	- liteeth                      : Added Ultrascale+ GTY/GTH SGMII/1000BaseX PHYs.
	- soc/add_pcie                 : Added msi_type parameter to select MSI, MSI-Multi-Vector or MSI-X.
	- soc/add_pcie                 : Added msi_width parameter to select MSI width.
	- litepcie                     : Added 7-Series MSI-X capability/integration.
	- liteiclink                   : Improved GTH3/GTH4 support and similarity with Wizard's generated code.
	- liteeth_gen                  : Added SGMII/1000BaseX PHYs support.
	- litesata/dma                 : Added multi-sector support.
	- liteeth/mac                  : Added TX Slots write-only mode for improved resource usage when software does not read buffer.
	- liteeth/core                 : Added DHCP support for CPU-less hardware stack.
	- liteeth/core/icmp            : Added fifo_depth parameter on LiteEthICMPEcho.
	- gen/fhdl/verilog             : Improved signal sort by name instead of duid to improve reproducibility.
	- litedram/frontend/dma        : Added last generation on end of DMA for LiteDRAMDMAReader.
	- litepcie/frontend/dma        : Added optional integrated data-width converter and data_width parameters to simplify integration/user logic.
	- soc/add_uartbone/sata/sdcard : Added support for multiple instances in gateware as for the other cores.
	- liteeth_gen                  : Added raw UDP port support.
	- build/vivado                 : Added .dcp generation also after synthesis and placement.
	- gen:                         : Added initial LiteXContext to easily get build properties (platform, device, toolchain, etc...)
	- litepcie/endpoint/tlp        : Added optional Configuration/PTM TLP support to Packetizer/Depacketizer.
	- liteth/arp                   : Added proper multi-entries ARP table.
	- liteiclink/serdes            : Added tx/rx_clk sharing capabilities on Xilinx transceivers.
	- soc/cores/spi                : Added new SPIMMAP core allowing SPI accesses through MMAP.
	- soc/interconnect/stream      : Added pipe_valid/pipe_ready parameters to BufferizeEndpoints.
	- soc/cores/clock              : Added initial GW5A support.
	- build/efinix                 : Added initial EfinixDDROutput/Input and simplified IOs exclusion.
	- soc/interconnect             : Improved DMA Bus to use the same Bus Standard than the CPU DMA Bus.
	- liteeth/phy                  : Added Artix7 2500BASE-X PHY.
	- liteeth/phy                  : Added Gowin Arora V RGMII PHY (GW5RGMII).
	- liteeth/phy                  : Added Titanium RGMII PHY (Tested with Ti60 F225 + RGMII adapter board).
	- build/io                     : Added ClkInput/Ouput IO abstraction to simplify some Efinix designs.

	[> Changed
	----------
	- litex/gen                    : Added local version of genlib.cdc/misc to better decouple with Migen and prepare Amaranth's compat use.
	- soc/add_uartbone             : Renamed name parameter to uart_name (for consistency with other cores).

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
