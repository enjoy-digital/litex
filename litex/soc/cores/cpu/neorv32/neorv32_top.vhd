-- ================================================================================ --
-- NEORV32 SoC - Processor Top Entity                                               --
-- -------------------------------------------------------------------------------- --
-- HQ:         https://github.com/stnolting/neorv32                                 --
-- Data Sheet: https://stnolting.github.io/neorv32                                  --
-- User Guide: https://stnolting.github.io/neorv32/ug                               --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_top is
  generic (
    -- Processor Clocking --
    CLOCK_FREQUENCY       : natural                        := 0;           -- clock frequency of clk_i in Hz
    HART_BASE             : natural                        := 0;           -- offset in HART_IDs

    -- Dual-Core Configuration --
    DUAL_CORE_EN          : boolean                        := false;       -- enable dual-core homogeneous SMP

    -- Boot Configuration --
    BOOT_MODE_SELECT      : natural range 0 to 2           := 0;           -- boot configuration select (default = 0 = bootloader)
    BOOT_ADDR_CUSTOM      : std_ulogic_vector(31 downto 0) := x"00000000"; -- custom CPU boot address (if boot_config = 1)

    -- On-Chip Debugger (OCD) --
    OCD_EN                : boolean                        := false;       -- implement on-chip debugger
    OCD_AUTHENTICATION    : boolean                        := false;       -- implement on-chip debugger authentication
    OCD_JEDEC_ID          : std_ulogic_vector(10 downto 0) := "00000000000"; -- JEDEC ID: continuation codes + vendor ID

    -- RISC-V CPU Extensions --
    RISCV_ISA_C           : boolean                        := false;       -- implement compressed extension
    RISCV_ISA_E           : boolean                        := false;       -- implement embedded RF extension
    RISCV_ISA_M           : boolean                        := false;       -- implement mul/div extension
    RISCV_ISA_U           : boolean                        := false;       -- implement user mode extension
    RISCV_ISA_Zaamo       : boolean                        := false;       -- implement atomic read-modify-write operations extension
    RISCV_ISA_Zalrsc      : boolean                        := false;       -- implement atomic reservation-set operations extension
    RISCV_ISA_Zba         : boolean                        := false;       -- implement shifted-add bit-manipulation extension
    RISCV_ISA_Zbb         : boolean                        := false;       -- implement basic bit-manipulation extension
    RISCV_ISA_Zbkb        : boolean                        := false;       -- implement bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc        : boolean                        := false;       -- implement carry-less multiplication instructions
    RISCV_ISA_Zbkx        : boolean                        := false;       -- implement cryptography crossbar permutation extension
    RISCV_ISA_Zbs         : boolean                        := false;       -- implement single-bit bit-manipulation extension
    RISCV_ISA_Zfinx       : boolean                        := false;       -- implement 32-bit floating-point extension
    RISCV_ISA_Zicntr      : boolean                        := false;       -- implement base counters
    RISCV_ISA_Zicond      : boolean                        := false;       -- implement integer conditional operations
    RISCV_ISA_Zihpm       : boolean                        := false;       -- implement hardware performance monitors
    RISCV_ISA_Zknd        : boolean                        := false;       -- implement cryptography NIST AES decryption extension
    RISCV_ISA_Zkne        : boolean                        := false;       -- implement cryptography NIST AES encryption extension
    RISCV_ISA_Zknh        : boolean                        := false;       -- implement cryptography NIST hash extension
    RISCV_ISA_Zksed       : boolean                        := false;       -- implement ShangMi block cipher extension
    RISCV_ISA_Zksh        : boolean                        := false;       -- implement ShangMi hash extension
    RISCV_ISA_Zmmul       : boolean                        := false;       -- implement multiply-only M sub-extension
    RISCV_ISA_Zxcfu       : boolean                        := false;       -- implement custom (instr.) functions unit

    -- Tuning Options --
    CPU_CLOCK_GATING_EN   : boolean                        := false;       -- enable clock gating when in sleep mode
    CPU_FAST_MUL_EN       : boolean                        := false;       -- use DSPs for M extension's multiplier
    CPU_FAST_SHIFT_EN     : boolean                        := false;       -- use barrel shifter for shift operations
    CPU_RF_HW_RST_EN      : boolean                        := false;       -- implement full hardware reset for register file

    -- Physical Memory Protection (PMP) --
    PMP_NUM_REGIONS       : natural range 0 to 16          := 0;           -- number of regions (0..16)
    PMP_MIN_GRANULARITY   : natural                        := 4;           -- minimal region granularity in bytes, has to be a power of 2, min 4 bytes
    PMP_TOR_MODE_EN       : boolean                        := false;       -- implement TOR mode
    PMP_NAP_MODE_EN       : boolean                        := false;       -- implement NAPOT/NA4 modes

    -- Hardware Performance Monitors (HPM) --
    HPM_NUM_CNTS          : natural range 0 to 13          := 0;           -- number of implemented HPM counters (0..13)
    HPM_CNT_WIDTH         : natural range 0 to 64          := 40;          -- total size of HPM counters (0..64)

    -- Internal Instruction memory (IMEM) --
    MEM_INT_IMEM_EN       : boolean                        := false;       -- implement processor-internal instruction memory
    MEM_INT_IMEM_SIZE     : natural                        := 16*1024;     -- size of processor-internal instruction memory in bytes (use a power of 2)

    -- Internal Data memory (DMEM) --
    MEM_INT_DMEM_EN       : boolean                        := false;       -- implement processor-internal data memory
    MEM_INT_DMEM_SIZE     : natural                        := 8*1024;      -- size of processor-internal data memory in bytes (use a power of 2)

    -- Internal Instruction Cache (iCACHE) --
    ICACHE_EN             : boolean                        := false;       -- implement instruction cache
    ICACHE_NUM_BLOCKS     : natural range 1 to 256         := 4;           -- i-cache: number of blocks (min 1), has to be a power of 2
    ICACHE_BLOCK_SIZE     : natural range 4 to 2**16       := 64;          -- i-cache: block size in bytes (min 4), has to be a power of 2

    -- Internal Data Cache (dCACHE) --
    DCACHE_EN             : boolean                        := false;       -- implement data cache
    DCACHE_NUM_BLOCKS     : natural range 1 to 256         := 4;           -- d-cache: number of blocks (min 1), has to be a power of 2
    DCACHE_BLOCK_SIZE     : natural range 4 to 2**16       := 64;          -- d-cache: block size in bytes (min 4), has to be a power of 2

    -- External bus interface (XBUS) --
    XBUS_EN               : boolean                        := false;       -- implement external memory bus interface?
    XBUS_TIMEOUT          : natural                        := 255;         -- cycles after a pending bus access auto-terminates (0 = disabled)
    XBUS_REGSTAGE_EN      : boolean                        := false;       -- add XBUS register stage
    XBUS_CACHE_EN         : boolean                        := false;       -- enable external bus cache (x-cache)
    XBUS_CACHE_NUM_BLOCKS : natural range 1 to 256         := 64;          -- x-cache: number of blocks (min 1), has to be a power of 2
    XBUS_CACHE_BLOCK_SIZE : natural range 1 to 2**16       := 32;          -- x-cache: block size in bytes (min 4), has to be a power of 2

    -- Processor peripherals --
    IO_DISABLE_SYSINFO    : boolean                        := false;       -- disable the SYSINFO module (for advanced users only)
    IO_GPIO_NUM           : natural range 0 to 32          := 0;           -- number of GPIO input/output pairs (0..32)
    IO_CLINT_EN           : boolean                        := false;       -- implement core local interruptor (CLINT)?
    IO_UART0_EN           : boolean                        := false;       -- implement primary universal asynchronous receiver/transmitter (UART0)?
    IO_UART0_RX_FIFO      : natural range 1 to 2**15       := 1;           -- RX FIFO depth, has to be a power of two, min 1
    IO_UART0_TX_FIFO      : natural range 1 to 2**15       := 1;           -- TX FIFO depth, has to be a power of two, min 1
    IO_UART1_EN           : boolean                        := false;       -- implement secondary universal asynchronous receiver/transmitter (UART1)?
    IO_UART1_RX_FIFO      : natural range 1 to 2**15       := 1;           -- RX FIFO depth, has to be a power of two, min 1
    IO_UART1_TX_FIFO      : natural range 1 to 2**15       := 1;           -- TX FIFO depth, has to be a power of two, min 1
    IO_SPI_EN             : boolean                        := false;       -- implement serial peripheral interface (SPI)?
    IO_SPI_FIFO           : natural range 1 to 2**15       := 1;           -- RTX FIFO depth, has to be a power of two, min 1
    IO_SDI_EN             : boolean                        := false;       -- implement serial data interface (SDI)?
    IO_SDI_FIFO           : natural range 1 to 2**15       := 1;           -- RTX FIFO depth, has to be zero or a power of two, min 1
    IO_TWI_EN             : boolean                        := false;       -- implement two-wire interface (TWI)?
    IO_TWI_FIFO           : natural range 1 to 2**15       := 1;           -- RTX FIFO depth, has to be zero or a power of two, min 1
    IO_TWD_EN             : boolean                        := false;       -- implement two-wire device (TWD)?
    IO_TWD_FIFO           : natural range 1 to 2**15       := 1;           -- RTX FIFO depth, has to be zero or a power of two, min 1
    IO_PWM_NUM_CH         : natural range 0 to 16          := 0;           -- number of PWM channels to implement (0..16)
    IO_WDT_EN             : boolean                        := false;       -- implement watch dog timer (WDT)?
    IO_TRNG_EN            : boolean                        := false;       -- implement true random number generator (TRNG)?
    IO_TRNG_FIFO          : natural range 1 to 2**15       := 1;           -- data FIFO depth, has to be a power of two, min 1
    IO_CFS_EN             : boolean                        := false;       -- implement custom functions subsystem (CFS)?
    IO_CFS_CONFIG         : std_ulogic_vector(31 downto 0) := x"00000000"; -- custom CFS configuration generic
    IO_CFS_IN_SIZE        : natural                        := 32;          -- size of CFS input conduit in bits
    IO_CFS_OUT_SIZE       : natural                        := 32;          -- size of CFS output conduit in bits
    IO_NEOLED_EN          : boolean                        := false;       -- implement NeoPixel-compatible smart LED interface (NEOLED)?
    IO_NEOLED_TX_FIFO     : natural range 1 to 2**15       := 1;           -- NEOLED FIFO depth, has to be a power of two, min 1
    IO_GPTMR_EN           : boolean                        := false;       -- implement general purpose timer (GPTMR)?
    IO_ONEWIRE_EN         : boolean                        := false;       -- implement 1-wire interface (ONEWIRE)?
    IO_ONEWIRE_FIFO       : natural range 1 to 2**15       := 1;           -- RTX FIFO depth, has to be zero or a power of two, min 1
    IO_DMA_EN             : boolean                        := false;       -- implement direct memory access controller (DMA)?
    IO_SLINK_EN           : boolean                        := false;       -- implement stream link interface (SLINK)?
    IO_SLINK_RX_FIFO      : natural range 1 to 2**15       := 1;           -- RX FIFO depth, has to be a power of two, min 1
    IO_SLINK_TX_FIFO      : natural range 1 to 2**15       := 1;           -- TX FIFO depth, has to be a power of two, min 1
    IO_CRC_EN             : boolean                        := false        -- implement cyclic redundancy check unit (CRC)?
  );
  port (
    -- Global control --
    clk_i          : in  std_ulogic;                                        -- global clock, rising edge
    rstn_i         : in  std_ulogic;                                        -- global reset, low-active, async
    rstn_ocd_o     : out std_ulogic;                                        -- on-chip debugger reset output, low-active, sync
    rstn_wdt_o     : out std_ulogic;                                        -- watchdog reset output, low-active, sync

    -- JTAG on-chip debugger interface (available if OCD_EN = true) --
    jtag_tck_i     : in  std_ulogic := 'L';                                 -- serial clock
    jtag_tdi_i     : in  std_ulogic := 'L';                                 -- serial data input
    jtag_tdo_o     : out std_ulogic;                                        -- serial data output
    jtag_tms_i     : in  std_ulogic := 'L';                                 -- mode select

    -- External bus interface (available if XBUS_EN = true) --
    xbus_adr_o     : out std_ulogic_vector(31 downto 0);                    -- address
    xbus_dat_o     : out std_ulogic_vector(31 downto 0);                    -- write data
    xbus_tag_o     : out std_ulogic_vector(2 downto 0);                     -- access tag
    xbus_we_o      : out std_ulogic;                                        -- read/write
    xbus_sel_o     : out std_ulogic_vector(3 downto 0);                     -- byte enable
    xbus_stb_o     : out std_ulogic;                                        -- strobe
    xbus_cyc_o     : out std_ulogic;                                        -- valid cycle
    xbus_dat_i     : in  std_ulogic_vector(31 downto 0) := (others => 'L'); -- read data
    xbus_ack_i     : in  std_ulogic := 'L';                                 -- transfer acknowledge
    xbus_err_i     : in  std_ulogic := 'L';                                 -- transfer error

    -- Stream Link Interface (available if IO_SLINK_EN = true) --
    slink_rx_dat_i : in  std_ulogic_vector(31 downto 0) := (others => 'L'); -- RX input data
    slink_rx_src_i : in  std_ulogic_vector(3 downto 0)  := (others => 'L'); -- RX source routing information
    slink_rx_val_i : in  std_ulogic := 'L';                                 -- RX valid input
    slink_rx_lst_i : in  std_ulogic := 'L';                                 -- RX last element of stream
    slink_rx_rdy_o : out std_ulogic;                                        -- RX ready to receive
    slink_tx_dat_o : out std_ulogic_vector(31 downto 0);                    -- TX output data
    slink_tx_dst_o : out std_ulogic_vector(3 downto 0);                     -- TX destination routing information
    slink_tx_val_o : out std_ulogic;                                        -- TX valid output
    slink_tx_lst_o : out std_ulogic;                                        -- TX last element of stream
    slink_tx_rdy_i : in  std_ulogic := 'L';                                 -- TX ready to send

    -- GPIO (available if IO_GPIO_NUM > 0) --
    gpio_o         : out std_ulogic_vector(31 downto 0);                    -- parallel output
    gpio_i         : in  std_ulogic_vector(31 downto 0) := (others => 'L'); -- parallel input; interrupt-capable

    -- primary UART0 (available if IO_UART0_EN = true) --
    uart0_txd_o    : out std_ulogic;                                        -- UART0 send data
    uart0_rxd_i    : in  std_ulogic := 'L';                                 -- UART0 receive data
    uart0_rtsn_o   : out std_ulogic;                                        -- HW flow control: UART0.RX ready to receive ("RTR"), low-active, optional
    uart0_ctsn_i   : in  std_ulogic := 'L';                                 -- HW flow control: UART0.TX allowed to transmit, low-active, optional

    -- secondary UART1 (available if IO_UART1_EN = true) --
    uart1_txd_o    : out std_ulogic;                                        -- UART1 send data
    uart1_rxd_i    : in  std_ulogic := 'L';                                 -- UART1 receive data
    uart1_rtsn_o   : out std_ulogic;                                        -- HW flow control: UART1.RX ready to receive ("RTR"), low-active, optional
    uart1_ctsn_i   : in  std_ulogic := 'L';                                 -- HW flow control: UART1.TX allowed to transmit, low-active, optional

    -- SPI (available if IO_SPI_EN = true) --
    spi_clk_o      : out std_ulogic;                                        -- SPI serial clock
    spi_dat_o      : out std_ulogic;                                        -- controller data out, peripheral data in
    spi_dat_i      : in  std_ulogic := 'L';                                 -- controller data in, peripheral data out
    spi_csn_o      : out std_ulogic_vector(7 downto 0);                     -- chip-select, low-active

    -- SDI (available if IO_SDI_EN = true) --
    sdi_clk_i      : in  std_ulogic := 'L';                                 -- SDI serial clock
    sdi_dat_o      : out std_ulogic;                                        -- controller data out, peripheral data in
    sdi_dat_i      : in  std_ulogic := 'L';                                 -- controller data in, peripheral data out
    sdi_csn_i      : in  std_ulogic := 'H';                                 -- chip-select, low-active

    -- TWI (available if IO_TWI_EN = true) --
    twi_sda_i      : in  std_ulogic := 'H';                                 -- serial data line sense input
    twi_sda_o      : out std_ulogic;                                        -- serial data line output (pull low only)
    twi_scl_i      : in  std_ulogic := 'H';                                 -- serial clock line sense input
    twi_scl_o      : out std_ulogic;                                        -- serial clock line output (pull low only)

    -- TWD (available if IO_TWD_EN = true) --
    twd_sda_i      : in  std_ulogic := 'H';                                 -- serial data line sense input
    twd_sda_o      : out std_ulogic;                                        -- serial data line output (pull low only)
    twd_scl_i      : in  std_ulogic := 'H';                                 -- serial clock line sense input
    twd_scl_o      : out std_ulogic;                                        -- serial clock line output (pull low only)

    -- 1-Wire Interface (available if IO_ONEWIRE_EN = true) --
    onewire_i      : in  std_ulogic := 'H';                                 -- 1-wire bus sense input
    onewire_o      : out std_ulogic;                                        -- 1-wire bus output (pull low only)

    -- PWM (available if IO_PWM_NUM_CH > 0) --
    pwm_o          : out std_ulogic_vector(15 downto 0);                    -- pwm channels

    -- Custom Functions Subsystem IO (available if IO_CFS_EN = true) --
    cfs_in_i       : in  std_ulogic_vector(IO_CFS_IN_SIZE-1 downto 0) := (others => 'L'); -- custom CFS inputs conduit
    cfs_out_o      : out std_ulogic_vector(IO_CFS_OUT_SIZE-1 downto 0);     -- custom CFS outputs conduit

    -- NeoPixel-compatible smart LED interface (available if IO_NEOLED_EN = true) --
    neoled_o       : out std_ulogic;                                        -- async serial data line

    -- Machine timer system time (available if IO_CLINT_EN = true) --
    mtime_time_o   : out std_ulogic_vector(63 downto 0);                    -- current system time

    -- CPU interrupts (for chip-internal usage only) --
    mtime_irq_i    : in  std_ulogic := 'L';                                 -- machine timer interrupt, available if IO_CLINT_EN = false
    msw_irq_i      : in  std_ulogic := 'L';                                 -- machine software interrupt, available if IO_CLINT_EN = false
    mext_irq_i     : in  std_ulogic := 'L'                                  -- machine external interrupt
  );
end neorv32_top;

architecture neorv32_top_rtl of neorv32_top is

  -- ----------------------------------------------------------
  -- Boot Configuration (BOOT_MODE_SELECT)
  -- ----------------------------------------------------------
  -- 0: Internal bootloader ROM
  -- 1: Custom (use BOOT_ADDR_CUSTOM)
  -- 2: Internal IMEM initialized with application image
  -- ----------------------------------------------------------
  constant bootrom_en_c    : boolean := boolean(BOOT_MODE_SELECT = 0);
  constant imem_as_rom_c   : boolean := boolean(BOOT_MODE_SELECT = 2);
  constant cpu_boot_addr_c : std_ulogic_vector(31 downto 0) :=
    cond_sel_suv_f(boolean(BOOT_MODE_SELECT = 0), base_io_bootrom_c,
    cond_sel_suv_f(boolean(BOOT_MODE_SELECT = 1), BOOT_ADDR_CUSTOM,
    cond_sel_suv_f(boolean(BOOT_MODE_SELECT = 2), mem_imem_base_c, x"00000000")));

  -- auto-configuration --
  constant num_cores_c     : natural := cond_sel_natural_f(DUAL_CORE_EN, 2, 1);
  constant io_gpio_en_c    : boolean := boolean(IO_GPIO_NUM > 0);
  constant io_pwm_en_c     : boolean := boolean(IO_PWM_NUM_CH > 0);
  constant cpu_smpmp_c     : boolean := boolean(PMP_NUM_REGIONS > 0);
  constant io_sysinfo_en_c : boolean := not IO_DISABLE_SYSINFO;

  -- make sure physical memory sizes are a power of two --
  constant imem_size_c : natural := cond_sel_natural_f(is_power_of_two_f(MEM_INT_IMEM_SIZE), MEM_INT_IMEM_SIZE, 2**index_size_f(MEM_INT_IMEM_SIZE));
  constant dmem_size_c : natural := cond_sel_natural_f(is_power_of_two_f(MEM_INT_DMEM_SIZE), MEM_INT_DMEM_SIZE, 2**index_size_f(MEM_INT_DMEM_SIZE));

  -- reset nets --
  signal rstn_wdt, rstn_sys, rstn_ext : std_ulogic;

  -- clock system --
  signal clk_gen : std_ulogic_vector(7 downto 0); -- scaled clock-enables
  --
  type clk_gen_en_enum_t is (
    CG_CFS, CG_UART0, CG_UART1, CG_SPI, CG_TWI, CG_TWD, CG_PWM, CG_WDT, CG_NEOLED, CG_GPTMR, CG_ONEWIRE
  );
  type clk_gen_en_t is array (clk_gen_en_enum_t) of std_ulogic;
  signal clk_gen_en  : clk_gen_en_t;
  signal clk_gen_en2 : std_ulogic_vector(10 downto 0);

  -- debug module interface (DMI) --
  signal dmi_req : dmi_req_t;
  signal dmi_rsp : dmi_rsp_t;

  -- debug core interface (DCI) --
  signal dci_ndmrstn : std_ulogic;
  signal dci_haltreq : std_ulogic_vector(num_cores_c-1 downto 0);

  -- CPU ICC links --
  type core_complex_icc_t is array (0 to num_cores_c-1) of icc_t;
  signal icc_tx, icc_rx : core_complex_icc_t;

  -- bus: CPU core complex --
  type core_complex_req_t is array (0 to num_cores_c-1) of bus_req_t;
  type core_complex_rsp_t is array (0 to num_cores_c-1) of bus_rsp_t;
  signal cpu_i_req, cpu_d_req, icache_req, dcache_req, core_req : core_complex_req_t;
  signal cpu_i_rsp, cpu_d_rsp, icache_rsp, dcache_rsp, core_rsp : core_complex_rsp_t;

  -- bus: system bus (including DMA complex) --
  signal sys1_req, sys2_req, dma_req, amo_req, sys3_req : bus_req_t;
  signal sys1_rsp, sys2_rsp, dma_rsp, amo_rsp, sys3_rsp : bus_rsp_t;

  -- bus: main sections --
  signal imem_req, dmem_req, io_req, xcache_req, xbus_req : bus_req_t;
  signal imem_rsp, dmem_rsp, io_rsp, xcache_rsp, xbus_rsp : bus_rsp_t;

  -- bus: IO devices --
  type io_devices_enum_t is (
    IODEV_BOOTROM, IODEV_OCD, IODEV_SYSINFO, IODEV_NEOLED, IODEV_GPIO, IODEV_WDT, IODEV_TRNG,
    IODEV_TWI, IODEV_SPI, IODEV_SDI, IODEV_UART1, IODEV_UART0, IODEV_CLINT, IODEV_ONEWIRE,
    IODEV_GPTMR, IODEV_PWM, IODEV_CRC, IODEV_DMA, IODEV_SLINK, IODEV_CFS, IODEV_TWD
  );
  type iodev_req_t is array (io_devices_enum_t) of bus_req_t;
  type iodev_rsp_t is array (io_devices_enum_t) of bus_rsp_t;
  signal iodev_req : iodev_req_t;
  signal iodev_rsp : iodev_rsp_t;

  -- memory synchronization / ordering / coherence --
  signal mem_sync, dcache_clean : std_ulogic_vector(num_cores_c-1 downto 0);
  signal xcache_clean : std_ulogic;

  -- IRQs --
  type firq_enum_t is (
    FIRQ_TWD, FIRQ_UART0_RX, FIRQ_UART0_TX, FIRQ_UART1_RX, FIRQ_UART1_TX, FIRQ_SPI, FIRQ_SDI, FIRQ_TWI,
    FIRQ_CFS, FIRQ_NEOLED, FIRQ_GPIO, FIRQ_GPTMR, FIRQ_ONEWIRE, FIRQ_DMA, FIRQ_SLINK_RX, FIRQ_SLINK_TX
  );
  type firq_t is array (firq_enum_t) of std_ulogic;
  signal firq      : firq_t;
  signal cpu_firq  : std_ulogic_vector(15 downto 0);
  signal mtime_irq : std_ulogic_vector(num_cores_c-1 downto 0);
  signal msw_irq   : std_ulogic_vector(num_cores_c-1 downto 0);

begin

  -- **************************************************************************************************************************
  -- Sanity Checks
  -- **************************************************************************************************************************

  sanity_checks:
  if true generate

    -- say hello --
    assert false report
      "[NEORV32] The NEORV32 RISC-V Processor " &
      "(v" & print_version_f(hw_version_c) & "), " &
      "github.com/stnolting/neorv32" severity note;

    -- show SoC configuration --
    assert false report
      "[NEORV32] Processor Configuration: CPU " & -- cpu core is always enabled
      cond_sel_string_f(boolean(num_cores_c = 1),  "(single-core) ",   "") &
      cond_sel_string_f(boolean(num_cores_c = 2),  "(smp-dual-core) ", "") &
      cond_sel_string_f(MEM_INT_IMEM_EN,           cond_sel_string_f(imem_as_rom_c, "IMEM-ROM ", "IMEM "), "") &
      cond_sel_string_f(MEM_INT_DMEM_EN,           "DMEM ",       "") &
      cond_sel_string_f(bootrom_en_c,              "BOOTROM ",    "") &
      cond_sel_string_f(ICACHE_EN,                 "I-CACHE ",    "") &
      cond_sel_string_f(DCACHE_EN,                 "D-CACHE ",    "") &
      cond_sel_string_f(XBUS_EN,                   "XBUS ",       "") &
      cond_sel_string_f(XBUS_EN and XBUS_CACHE_EN, "XBUS-CACHE ", "") &
      cond_sel_string_f(IO_CLINT_EN,               "CLINT ",      "") &
      cond_sel_string_f(io_gpio_en_c,              "GPIO ",       "") &
      cond_sel_string_f(IO_UART0_EN,               "UART0 ",      "") &
      cond_sel_string_f(IO_UART1_EN,               "UART1 ",      "") &
      cond_sel_string_f(IO_SPI_EN,                 "SPI ",        "") &
      cond_sel_string_f(IO_SDI_EN,                 "SDI ",        "") &
      cond_sel_string_f(IO_TWI_EN,                 "TWI ",        "") &
      cond_sel_string_f(IO_TWD_EN,                 "TWD ",        "") &
      cond_sel_string_f(io_pwm_en_c,               "PWM ",        "") &
      cond_sel_string_f(IO_WDT_EN,                 "WDT ",        "") &
      cond_sel_string_f(IO_TRNG_EN,                "TRNG ",       "") &
      cond_sel_string_f(IO_CFS_EN,                 "CFS ",        "") &
      cond_sel_string_f(IO_NEOLED_EN,              "NEOLED ",     "") &
      cond_sel_string_f(IO_GPTMR_EN,               "GPTMR ",      "") &
      cond_sel_string_f(IO_ONEWIRE_EN,             "ONEWIRE ",    "") &
      cond_sel_string_f(IO_DMA_EN,                 "DMA ",        "") &
      cond_sel_string_f(IO_SLINK_EN,               "SLINK ",      "") &
      cond_sel_string_f(IO_CRC_EN,                 "CRC ",        "") &
      cond_sel_string_f(io_sysinfo_en_c,           "SYSINFO ",    "") &
      cond_sel_string_f(OCD_EN,                    cond_sel_string_f(OCD_AUTHENTICATION, "OCD-AUTH ", "OCD "), "") &
      ""
      severity note;

    -- IMEM size was not a power of two --
    assert not ((MEM_INT_IMEM_SIZE /= imem_size_c) and (MEM_INT_IMEM_EN = true)) report
      "[NEORV32] Auto-adjusting invalid IMEM size configuration." severity warning;

    -- DMEM size was not a power of two --
    assert not ((MEM_INT_DMEM_SIZE /= dmem_size_c) and (MEM_INT_DMEM_EN = true)) report
      "[NEORV32] Auto-adjusting invalid DMEM size configuration." severity warning;

    -- SYSINFO disabled --
    assert not (io_sysinfo_en_c = false) report
      "[NEORV32] SYSINFO module disabled - some parts of the NEORV32 software framework will no longer work!" severity warning;

    -- Clock speed not defined --
    assert not (CLOCK_FREQUENCY = 0) report
      "[NEORV32] CLOCK_FREQUENCY must be configured according to the frequency of clk_i port." severity warning;

    -- Boot configuration notifier --
    assert not (BOOT_MODE_SELECT = 0) report "[NEORV32] BOOT_MODE_SELECT = 0: booting via bootloader" severity note;
    assert not (BOOT_MODE_SELECT = 1) report "[NEORV32] BOOT_MODE_SELECT = 1: booting from custom address" severity note;
    assert not (BOOT_MODE_SELECT = 2) report "[NEORV32] BOOT_MODE_SELECT = 2: booting IMEM image" severity note;

    -- Boot configuration: boot from initialized IMEM requires the IMEM to be enabled --
    assert not ((BOOT_MODE_SELECT = 2) and (MEM_INT_IMEM_EN = false)) report
      "[NEORV32] ERROR: BOOT_MODE_SELECT = 2 (boot IMEM image) requires the internal instruction memory (IMEM) to be enabled!" severity error;

    -- The SMP dual-core configuration requires the CLINT --
    assert not ((DUAL_CORE_EN = true) and (IO_CLINT_EN = false)) report
      "[NEORV32] ERROR: The SMP dual-core configuration requires the CLINT to be enabled!" severity error;

  end generate; -- /sanity_checks


  -- **************************************************************************************************************************
  -- Clock and Reset Generators
  -- **************************************************************************************************************************

  soc_generators:
  if true generate

    -- Reset Sequencer ------------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_sys_reset_inst: entity neorv32.neorv32_sys_reset
    port map (
      clk_i       => clk_i,
      rstn_ext_i  => rstn_i,
      rstn_wdt_i  => rstn_wdt,
      rstn_dbg_i  => dci_ndmrstn,
      rstn_ext_o  => rstn_ext,
      rstn_sys_o  => rstn_sys,
      xrstn_wdt_o => rstn_wdt_o,
      xrstn_ocd_o => rstn_ocd_o
    );


    -- Clock Divider / Pulse Generator --------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_sys_clock_inst: entity neorv32.neorv32_sys_clock
    generic map (
      NUM_EN => clk_gen_en2'length
    )
    port map (
      clk_i    => clk_i,
      rstn_i   => rstn_sys,
      enable_i => clk_gen_en2,
      clk_en_o => clk_gen
    );

    -- fresh clocks anyone? --
    clk_gen_en2 <= clk_gen_en(CG_CFS)    & clk_gen_en(CG_UART0) & clk_gen_en(CG_UART1) & clk_gen_en(CG_SPI) &
                   clk_gen_en(CG_TWI)    & clk_gen_en(CG_TWD)   & clk_gen_en(CG_PWM)   & clk_gen_en(CG_WDT) &
                   clk_gen_en(CG_NEOLED) & clk_gen_en(CG_GPTMR) & clk_gen_en(CG_ONEWIRE);

  end generate; -- /soc_generators


  -- **************************************************************************************************************************
  -- Core Complex
  -- **************************************************************************************************************************

  -- fast interrupt requests (FIRQs) --
  cpu_firq(0)  <= firq(FIRQ_TWD); -- highest priority
  cpu_firq(1)  <= firq(FIRQ_CFS);
  cpu_firq(2)  <= firq(FIRQ_UART0_RX);
  cpu_firq(3)  <= firq(FIRQ_UART0_TX);
  cpu_firq(4)  <= firq(FIRQ_UART1_RX);
  cpu_firq(5)  <= firq(FIRQ_UART1_TX);
  cpu_firq(6)  <= firq(FIRQ_SPI);
  cpu_firq(7)  <= firq(FIRQ_TWI);
  cpu_firq(8)  <= firq(FIRQ_GPIO);
  cpu_firq(9)  <= firq(FIRQ_NEOLED);
  cpu_firq(10) <= firq(FIRQ_DMA);
  cpu_firq(11) <= firq(FIRQ_SDI);
  cpu_firq(12) <= firq(FIRQ_GPTMR);
  cpu_firq(13) <= firq(FIRQ_ONEWIRE);
  cpu_firq(14) <= firq(FIRQ_SLINK_RX);
  cpu_firq(15) <= firq(FIRQ_SLINK_TX); -- lowest priority

  -- CPU core(s) + optional L1 caches + bus switch --
  core_complex_gen:
  for i in 0 to num_cores_c-1 generate

    -- CPU Core -------------------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_cpu_inst: entity neorv32.neorv32_cpu
    generic map (
      -- General --
      HART_ID             => i+HART_BASE,
      BOOT_ADDR           => cpu_boot_addr_c,
      DEBUG_PARK_ADDR     => dm_park_entry_c,
      DEBUG_EXC_ADDR      => dm_exc_entry_c,
      ICC_EN              => DUAL_CORE_EN,
      -- RISC-V ISA Extensions --
      RISCV_ISA_C         => RISCV_ISA_C,
      RISCV_ISA_E         => RISCV_ISA_E,
      RISCV_ISA_M         => RISCV_ISA_M,
      RISCV_ISA_U         => RISCV_ISA_U,
      RISCV_ISA_Zaamo     => RISCV_ISA_Zaamo,
      RISCV_ISA_Zalrsc    => RISCV_ISA_Zalrsc,
      RISCV_ISA_Zba       => RISCV_ISA_Zba,
      RISCV_ISA_Zbb       => RISCV_ISA_Zbb,
      RISCV_ISA_Zbkb      => RISCV_ISA_Zbkb,
      RISCV_ISA_Zbkc      => RISCV_ISA_Zbkc,
      RISCV_ISA_Zbkx      => RISCV_ISA_Zbkx,
      RISCV_ISA_Zbs       => RISCV_ISA_Zbs,
      RISCV_ISA_Zfinx     => RISCV_ISA_Zfinx,
      RISCV_ISA_Zicntr    => RISCV_ISA_Zicntr,
      RISCV_ISA_Zicond    => RISCV_ISA_Zicond,
      RISCV_ISA_Zihpm     => RISCV_ISA_Zihpm,
      RISCV_ISA_Zknd      => RISCV_ISA_Zknd,
      RISCV_ISA_Zkne      => RISCV_ISA_Zkne,
      RISCV_ISA_Zknh      => RISCV_ISA_Zknh,
      RISCV_ISA_Zksed     => RISCV_ISA_Zksed,
      RISCV_ISA_Zksh      => RISCV_ISA_Zksh,
      RISCV_ISA_Zmmul     => RISCV_ISA_Zmmul,
      RISCV_ISA_Zxcfu     => RISCV_ISA_Zxcfu,
      RISCV_ISA_Sdext     => OCD_EN,
      RISCV_ISA_Sdtrig    => OCD_EN,
      RISCV_ISA_Smpmp     => cpu_smpmp_c,
      -- Tuning Options --
      CPU_CLOCK_GATING_EN => CPU_CLOCK_GATING_EN,
      CPU_FAST_MUL_EN     => CPU_FAST_MUL_EN,
      CPU_FAST_SHIFT_EN   => CPU_FAST_SHIFT_EN,
      CPU_RF_HW_RST_EN    => CPU_RF_HW_RST_EN,
      -- Physical Memory Protection (PMP) --
      PMP_NUM_REGIONS     => PMP_NUM_REGIONS,
      PMP_MIN_GRANULARITY => PMP_MIN_GRANULARITY,
      PMP_TOR_MODE_EN     => PMP_TOR_MODE_EN,
      PMP_NAP_MODE_EN     => PMP_NAP_MODE_EN,
      -- Hardware Performance Monitors (HPM) --
      HPM_NUM_CNTS        => HPM_NUM_CNTS,
      HPM_CNT_WIDTH       => HPM_CNT_WIDTH
    )
    port map (
      -- global control --
      clk_i      => clk_i,
      rstn_i     => rstn_sys,
      -- interrupts --
      msi_i      => msw_irq(i),
      mei_i      => mext_irq_i,
      mti_i      => mtime_irq(i),
      firq_i     => cpu_firq,
      dbi_i      => dci_haltreq(i),
      -- inter-core communication links --
      icc_tx_o   => icc_tx(i),
      icc_rx_i   => icc_rx(i),
      -- instruction bus interface --
      ibus_req_o => cpu_i_req(i),
      ibus_rsp_i => cpu_i_rsp(i),
      -- data bus interface --
      dbus_req_o => cpu_d_req(i),
      dbus_rsp_i => cpu_d_rsp(i),
      -- memory synchronization --
      mem_sync_i => mem_sync(i)
    );

    -- memory synchronization (ordering / coherence) --
    mem_sync(i) <= dcache_clean(i) and xcache_clean; -- for this hart's perspective only


    -- CPU L1 Instruction Cache ---------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_icache_enabled:
    if ICACHE_EN generate
      neorv32_icache_inst: entity neorv32.neorv32_cache
      generic map (
        NUM_BLOCKS => ICACHE_NUM_BLOCKS,
        BLOCK_SIZE => ICACHE_BLOCK_SIZE,
        UC_BEGIN   => mem_uncached_begin_c(31 downto 28),
        READ_ONLY  => true
      )
      port map (
        clk_i      => clk_i,
        rstn_i     => rstn_sys,
        clean_o    => open, -- cache is read-only so it cannot be dirty
        host_req_i => cpu_i_req(i),
        host_rsp_o => cpu_i_rsp(i),
        bus_req_o  => icache_req(i),
        bus_rsp_i  => icache_rsp(i)
      );
    end generate;

    neorv32_icache_disabled:
    if not ICACHE_EN generate
      icache_req(i) <= cpu_i_req(i);
      cpu_i_rsp(i)  <= icache_rsp(i);
    end generate;


    -- CPU L1 Data Cache ----------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_dcache_enabled:
    if DCACHE_EN generate
      neorv32_dcache_inst: entity neorv32.neorv32_cache
      generic map (
        NUM_BLOCKS => DCACHE_NUM_BLOCKS,
        BLOCK_SIZE => DCACHE_BLOCK_SIZE,
        UC_BEGIN   => mem_uncached_begin_c(31 downto 28),
        READ_ONLY  => false
      )
      port map (
        clk_i      => clk_i,
        rstn_i     => rstn_sys,
        clean_o    => dcache_clean(i),
        host_req_i => cpu_d_req(i),
        host_rsp_o => cpu_d_rsp(i),
        bus_req_o  => dcache_req(i),
        bus_rsp_i  => dcache_rsp(i)
      );
    end generate;

    neorv32_dcache_disabled:
    if not DCACHE_EN generate
      dcache_clean(i) <= '1';
      dcache_req(i)   <= cpu_d_req(i);
      cpu_d_rsp(i)    <= dcache_rsp(i);
    end generate;


    -- Core Instruction/Data Bus Switch -------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_core_bus_switch_inst: entity neorv32.neorv32_bus_switch
    generic map (
      ROUND_ROBIN_EN   => false, -- use prioritizing arbitration
      PORT_A_READ_ONLY => false,
      PORT_B_READ_ONLY => true -- instruction fetch is read-only
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_sys,
      a_req_i => dcache_req(i), -- data accesses are prioritized
      a_rsp_o => dcache_rsp(i),
      b_req_i => icache_req(i),
      b_rsp_o => icache_rsp(i),
      x_req_o => core_req(i),
      x_rsp_i => core_rsp(i)
    );

  end generate; -- /core_complex


  -- Inter-Core Communication (ICC) Links ---------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  icc_connect: process(icc_tx)
  begin
    icc_rx(icc_rx'left)  <= icc_tx(icc_tx'right);
    icc_rx(icc_rx'right) <= icc_tx(icc_tx'left);
  end process icc_connect;


  -- Core Complex Bus Arbiter ---------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  core_complex_dual:
  if num_cores_c = 2 generate
    neorv32_complex_arbiter_inst: entity neorv32.neorv32_bus_switch
    generic map (
      ROUND_ROBIN_EN   => true,
      PORT_A_READ_ONLY => false,
      PORT_B_READ_ONLY => false
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_sys,
      a_req_i => core_req(core_req'left),
      a_rsp_o => core_rsp(core_rsp'left),
      b_req_i => core_req(core_req'right),
      b_rsp_o => core_rsp(core_rsp'right),
      x_req_o => sys1_req,
      x_rsp_i => sys1_rsp
    );
  end generate;

  core_complex_single:
  if num_cores_c = 1 generate
    sys1_req    <= core_req(0);
    core_rsp(0) <= sys1_rsp;
  end generate;


  -- **************************************************************************************************************************
  -- Direct Memory Access Controller (DMA) Complex
  -- **************************************************************************************************************************

  neorv32_dma_complex_enabled:
  if IO_DMA_EN generate

    -- DMA Controller -------------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_dma_inst: entity neorv32.neorv32_dma
    port map (
      clk_i     => clk_i,
      rstn_i    => rstn_sys,
      bus_req_i => iodev_req(IODEV_DMA),
      bus_rsp_o => iodev_rsp(IODEV_DMA),
      dma_req_o => dma_req,
      dma_rsp_i => dma_rsp,
      irq_o     => firq(FIRQ_DMA)
    );


    -- DMA Bus Switch -------------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_dma_bus_switch_inst: entity neorv32.neorv32_bus_switch
    generic map (
      ROUND_ROBIN_EN   => false, -- use prioritizing arbitration
      PORT_A_READ_ONLY => false,
      PORT_B_READ_ONLY => false
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_sys,
      a_req_i => sys1_req, -- prioritized
      a_rsp_o => sys1_rsp,
      b_req_i => dma_req,
      b_rsp_o => dma_rsp,
      x_req_o => sys2_req,
      x_rsp_i => sys2_rsp
    );

  end generate; -- /neorv32_dma_complex_enabled

  neorv32_dma_complex_disabled:
  if not IO_DMA_EN generate
    iodev_rsp(IODEV_DMA) <= rsp_terminate_c;
    sys2_req             <= sys1_req;
    sys1_rsp             <= sys2_rsp;
    firq(FIRQ_DMA)       <= '0';
  end generate;


  -- **************************************************************************************************************************
  -- Atomic Memory Operations
  -- **************************************************************************************************************************

  atomics:
  if true generate

    -- Read-Modify-Write Controller -----------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_bus_amo_rmw_enabled:
    if RISCV_ISA_Zaamo generate
      neorv32_bus_amo_rmw_inst: entity neorv32.neorv32_bus_amo_rmw
      port map (
        clk_i      => clk_i,
        rstn_i     => rstn_sys,
        core_req_i => sys2_req,
        core_rsp_o => sys2_rsp,
        sys_req_o  => amo_req,
        sys_rsp_i  => amo_rsp
      );
    end generate;

    neorv32_bus_amo_rmw_disabled:
    if not RISCV_ISA_Zaamo generate
      amo_req  <= sys2_req;
      sys2_rsp <= amo_rsp;
    end generate;


    -- Reservation-Set Controller -------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_bus_amo_rvs_enabled:
    if RISCV_ISA_Zalrsc generate
      neorv32_bus_amo_rvs_inst: entity neorv32.neorv32_bus_amo_rvs
      port map (
        clk_i      => clk_i,
        rstn_i     => rstn_sys,
        core_req_i => amo_req,
        core_rsp_o => amo_rsp,
        sys_req_o  => sys3_req,
        sys_rsp_i  => sys3_rsp
      );
    end generate;

    neorv32_bus_amo_rvs_disabled:
    if not RISCV_ISA_Zalrsc generate
      sys3_req <= amo_req;
      amo_rsp  <= sys3_rsp;
    end generate;

  end generate; -- /atomics


  -- **************************************************************************************************************************
  -- Address Region Gateway
  -- **************************************************************************************************************************

  neorv32_bus_gateway_inst: entity neorv32.neorv32_bus_gateway
  generic map (
    TIMEOUT  => bus_timeout_c,
    -- port A: internal IMEM --
    A_EN   => MEM_INT_IMEM_EN,
    A_BASE => mem_imem_base_c,
    A_SIZE => imem_size_c,
    -- port B: internal DMEM --
    B_EN   => MEM_INT_DMEM_EN,
    B_BASE => mem_dmem_base_c,
    B_SIZE => dmem_size_c,
    -- port C: IO --
    C_EN   => true, -- always enabled (but will be trimmed if no IO devices are implemented)
    C_BASE => mem_io_base_c,
    C_SIZE => mem_io_size_c,
    -- port X (the void): XBUS --
    X_EN   => XBUS_EN
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_sys,
    -- host port --
    req_i   => sys3_req,
    rsp_o   => sys3_rsp,
    -- section ports --
    a_req_o => imem_req,
    a_rsp_i => imem_rsp,
    b_req_o => dmem_req,
    b_rsp_i => dmem_rsp,
    c_req_o => io_req,
    c_rsp_i => io_rsp,
    x_req_o => xbus_req,
    x_rsp_i => xbus_rsp
  );


  -- **************************************************************************************************************************
  -- Memory System
  -- **************************************************************************************************************************

  memory_system:
  if true generate

    -- Processor-Internal Instruction Memory (IMEM) -------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_int_imem_enabled:
    if MEM_INT_IMEM_EN generate
      neorv32_int_imem_inst: entity neorv32.neorv32_imem
      generic map (
        IMEM_SIZE => imem_size_c,
        IMEM_INIT => imem_as_rom_c
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => imem_req,
        bus_rsp_o => imem_rsp
      );
    end generate;

    neorv32_int_imem_disabled:
    if not MEM_INT_IMEM_EN generate
      imem_rsp <= rsp_terminate_c;
    end generate;


    -- Processor-Internal Data Memory (DMEM) --------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_int_dmem_enabled:
    if MEM_INT_DMEM_EN generate
      neorv32_int_dmem_inst: entity neorv32.neorv32_dmem
      generic map (
        DMEM_SIZE => dmem_size_c
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => dmem_req,
        bus_rsp_o => dmem_rsp
      );
    end generate;

    neorv32_int_dmem_disabled:
    if not MEM_INT_DMEM_EN generate
      dmem_rsp <= rsp_terminate_c;
    end generate;


    -- External Bus Interface (XBUS) ----------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_xbus_enabled:
    if XBUS_EN generate

      -- external bus gateway (XBUS) --
      neorv32_xbus_inst: entity neorv32.neorv32_xbus
      generic map (
        TIMEOUT_VAL => XBUS_TIMEOUT,
        REGSTAGE_EN => XBUS_REGSTAGE_EN
      )
      port map (
        clk_i      => clk_i,
        rstn_i     => rstn_sys,
        bus_req_i  => xcache_req,
        bus_rsp_o  => xcache_rsp,
        xbus_adr_o => xbus_adr_o,
        xbus_dat_i => xbus_dat_i,
        xbus_dat_o => xbus_dat_o,
        xbus_tag_o => xbus_tag_o,
        xbus_we_o  => xbus_we_o,
        xbus_sel_o => xbus_sel_o,
        xbus_stb_o => xbus_stb_o,
        xbus_cyc_o => xbus_cyc_o,
        xbus_ack_i => xbus_ack_i,
        xbus_err_i => xbus_err_i
      );

      -- external bus cache (X-CACHE) --
      neorv32_xcache_enabled:
      if XBUS_CACHE_EN generate
        neorv32_xcache_inst: entity neorv32.neorv32_cache
        generic map (
          NUM_BLOCKS => XBUS_CACHE_NUM_BLOCKS,
          BLOCK_SIZE => XBUS_CACHE_BLOCK_SIZE,
          UC_BEGIN   => mem_uncached_begin_c(31 downto 28),
          READ_ONLY  => false
        )
        port map (
          clk_i      => clk_i,
          rstn_i     => rstn_sys,
          clean_o    => xcache_clean,
          host_req_i => xbus_req,
          host_rsp_o => xbus_rsp,
          bus_req_o  => xcache_req,
          bus_rsp_i  => xcache_rsp
        );
      end generate;

      neorv32_xcache_disabled:
      if not XBUS_CACHE_EN generate
        xcache_clean <= '1';
        xcache_req   <= xbus_req;
        xbus_rsp     <= xcache_rsp;
      end generate;

    end generate; -- /neorv32_xbus_enabled

    neorv32_xbus_disabled:
    if not XBUS_EN generate
      xcache_clean <= '1';
      xcache_req   <= req_terminate_c;
      xbus_rsp     <= rsp_terminate_c;
      xbus_adr_o   <= (others => '0');
      xbus_dat_o   <= (others => '0');
      xbus_tag_o   <= (others => '0');
      xbus_we_o    <= '0';
      xbus_sel_o   <= (others => '0');
      xbus_stb_o   <= '0';
      xbus_cyc_o   <= '0';
    end generate;

  end generate; -- /memory_system


  -- **************************************************************************************************************************
  -- IO/Peripheral Modules
  -- **************************************************************************************************************************

  io_system:
  if true generate

    -- IO Switch ------------------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_bus_io_switch_inst: entity neorv32.neorv32_bus_io_switch
    generic map (
      INREG_EN  => true,
      OUTREG_EN => true,
      DEV_SIZE  => iodev_size_c,
      DEV_00_EN => bootrom_en_c,    DEV_00_BASE => base_io_bootrom_c,
      DEV_01_EN => false,           DEV_01_BASE => (others => '0'), -- reserved
      DEV_02_EN => false,           DEV_02_BASE => (others => '0'), -- reserved
      DEV_03_EN => false,           DEV_03_BASE => (others => '0'), -- reserved
      DEV_04_EN => false,           DEV_04_BASE => (others => '0'), -- reserved
      DEV_05_EN => false,           DEV_05_BASE => (others => '0'), -- reserved
      DEV_06_EN => false,           DEV_06_BASE => (others => '0'), -- reserved
      DEV_07_EN => false,           DEV_07_BASE => (others => '0'), -- reserved
      DEV_08_EN => false,           DEV_08_BASE => (others => '0'), -- reserved
      DEV_09_EN => false,           DEV_09_BASE => (others => '0'), -- reserved
      DEV_10_EN => IO_TWD_EN,       DEV_10_BASE => base_io_twd_c,
      DEV_11_EN => IO_CFS_EN,       DEV_11_BASE => base_io_cfs_c,
      DEV_12_EN => IO_SLINK_EN,     DEV_12_BASE => base_io_slink_c,
      DEV_13_EN => IO_DMA_EN,       DEV_13_BASE => base_io_dma_c,
      DEV_14_EN => IO_CRC_EN,       DEV_14_BASE => base_io_crc_c,
      DEV_15_EN => false,           DEV_15_BASE => (others => '0'), -- reserved
      DEV_16_EN => io_pwm_en_c,     DEV_16_BASE => base_io_pwm_c,
      DEV_17_EN => IO_GPTMR_EN,     DEV_17_BASE => base_io_gptmr_c,
      DEV_18_EN => IO_ONEWIRE_EN,   DEV_18_BASE => base_io_onewire_c,
      DEV_19_EN => false,           DEV_19_BASE => (others => '0'), -- reserved
      DEV_20_EN => IO_CLINT_EN,     DEV_20_BASE => base_io_clint_c,
      DEV_21_EN => IO_UART0_EN,     DEV_21_BASE => base_io_uart0_c,
      DEV_22_EN => IO_UART1_EN,     DEV_22_BASE => base_io_uart1_c,
      DEV_23_EN => IO_SDI_EN,       DEV_23_BASE => base_io_sdi_c,
      DEV_24_EN => IO_SPI_EN,       DEV_24_BASE => base_io_spi_c,
      DEV_25_EN => IO_TWI_EN,       DEV_25_BASE => base_io_twi_c,
      DEV_26_EN => IO_TRNG_EN,      DEV_26_BASE => base_io_trng_c,
      DEV_27_EN => IO_WDT_EN,       DEV_27_BASE => base_io_wdt_c,
      DEV_28_EN => io_gpio_en_c,    DEV_28_BASE => base_io_gpio_c,
      DEV_29_EN => IO_NEOLED_EN,    DEV_29_BASE => base_io_neoled_c,
      DEV_30_EN => io_sysinfo_en_c, DEV_30_BASE => base_io_sysinfo_c,
      DEV_31_EN => OCD_EN,          DEV_31_BASE => base_io_ocd_c
    )
    port map (
      clk_i        => clk_i,
      rstn_i       => rstn_sys,
      main_req_i   => io_req,
      main_rsp_o   => io_rsp,
      dev_00_req_o => iodev_req(IODEV_BOOTROM), dev_00_rsp_i => iodev_rsp(IODEV_BOOTROM),
      dev_01_req_o => open,                     dev_01_rsp_i => rsp_terminate_c, -- reserved
      dev_02_req_o => open,                     dev_02_rsp_i => rsp_terminate_c, -- reserved
      dev_03_req_o => open,                     dev_03_rsp_i => rsp_terminate_c, -- reserved
      dev_04_req_o => open,                     dev_04_rsp_i => rsp_terminate_c, -- reserved
      dev_05_req_o => open,                     dev_05_rsp_i => rsp_terminate_c, -- reserved
      dev_06_req_o => open,                     dev_06_rsp_i => rsp_terminate_c, -- reserved
      dev_07_req_o => open,                     dev_07_rsp_i => rsp_terminate_c, -- reserved
      dev_08_req_o => open,                     dev_08_rsp_i => rsp_terminate_c, -- reserved
      dev_09_req_o => open,                     dev_09_rsp_i => rsp_terminate_c, -- reserved
      dev_10_req_o => iodev_req(IODEV_TWD),     dev_10_rsp_i => iodev_rsp(IODEV_TWD),
      dev_11_req_o => iodev_req(IODEV_CFS),     dev_11_rsp_i => iodev_rsp(IODEV_CFS),
      dev_12_req_o => iodev_req(IODEV_SLINK),   dev_12_rsp_i => iodev_rsp(IODEV_SLINK),
      dev_13_req_o => iodev_req(IODEV_DMA),     dev_13_rsp_i => iodev_rsp(IODEV_DMA),
      dev_14_req_o => iodev_req(IODEV_CRC),     dev_14_rsp_i => iodev_rsp(IODEV_CRC),
      dev_15_req_o => open,                     dev_15_rsp_i => rsp_terminate_c, -- reserved
      dev_16_req_o => iodev_req(IODEV_PWM),     dev_16_rsp_i => iodev_rsp(IODEV_PWM),
      dev_17_req_o => iodev_req(IODEV_GPTMR),   dev_17_rsp_i => iodev_rsp(IODEV_GPTMR),
      dev_18_req_o => iodev_req(IODEV_ONEWIRE), dev_18_rsp_i => iodev_rsp(IODEV_ONEWIRE),
      dev_19_req_o => open,                     dev_19_rsp_i => rsp_terminate_c, -- reserved
      dev_20_req_o => iodev_req(IODEV_CLINT),   dev_20_rsp_i => iodev_rsp(IODEV_CLINT),
      dev_21_req_o => iodev_req(IODEV_UART0),   dev_21_rsp_i => iodev_rsp(IODEV_UART0),
      dev_22_req_o => iodev_req(IODEV_UART1),   dev_22_rsp_i => iodev_rsp(IODEV_UART1),
      dev_23_req_o => iodev_req(IODEV_SDI),     dev_23_rsp_i => iodev_rsp(IODEV_SDI),
      dev_24_req_o => iodev_req(IODEV_SPI),     dev_24_rsp_i => iodev_rsp(IODEV_SPI),
      dev_25_req_o => iodev_req(IODEV_TWI),     dev_25_rsp_i => iodev_rsp(IODEV_TWI),
      dev_26_req_o => iodev_req(IODEV_TRNG),    dev_26_rsp_i => iodev_rsp(IODEV_TRNG),
      dev_27_req_o => iodev_req(IODEV_WDT),     dev_27_rsp_i => iodev_rsp(IODEV_WDT),
      dev_28_req_o => iodev_req(IODEV_GPIO),    dev_28_rsp_i => iodev_rsp(IODEV_GPIO),
      dev_29_req_o => iodev_req(IODEV_NEOLED),  dev_29_rsp_i => iodev_rsp(IODEV_NEOLED),
      dev_30_req_o => iodev_req(IODEV_SYSINFO), dev_30_rsp_i => iodev_rsp(IODEV_SYSINFO),
      dev_31_req_o => iodev_req(IODEV_OCD),     dev_31_rsp_i => iodev_rsp(IODEV_OCD)
    );


    -- Processor-Internal Bootloader ROM (BOOTROM) --------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_boot_rom_enabled:
    if bootrom_en_c generate
      neorv32_boot_rom_inst: entity neorv32.neorv32_boot_rom
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_BOOTROM),
        bus_rsp_o => iodev_rsp(IODEV_BOOTROM)
      );
    end generate;

    neorv32_boot_rom_disabled:
    if not bootrom_en_c generate
      iodev_rsp(IODEV_BOOTROM) <= rsp_terminate_c;
    end generate;


    -- Custom Functions Subsystem (CFS) -------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_cfs_enabled:
    if IO_CFS_EN generate
      neorv32_cfs_inst: entity neorv32.neorv32_cfs
      generic map (
        CFS_CONFIG   => IO_CFS_CONFIG,
        CFS_IN_SIZE  => IO_CFS_IN_SIZE,
        CFS_OUT_SIZE => IO_CFS_OUT_SIZE
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_CFS),
        bus_rsp_o   => iodev_rsp(IODEV_CFS),
        clkgen_en_o => clk_gen_en(CG_CFS),
        clkgen_i    => clk_gen,
        irq_o       => firq(FIRQ_CFS),
        cfs_in_i    => cfs_in_i,
        cfs_out_o   => cfs_out_o
      );
    end generate;

    neorv32_cfs_disabled:
    if not IO_CFS_EN generate
      iodev_rsp(IODEV_CFS) <= rsp_terminate_c;
      clk_gen_en(CG_CFS)   <= '0';
      firq(FIRQ_CFS)       <= '0';
      cfs_out_o            <= (others => '0');
    end generate;


    -- Serial Data Interface (SDI) ------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_sdi_enabled:
    if IO_SDI_EN generate
      neorv32_sdi_inst: entity neorv32.neorv32_sdi
      generic map (
        RTX_FIFO => IO_SDI_FIFO
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_SDI),
        bus_rsp_o => iodev_rsp(IODEV_SDI),
        sdi_csn_i => sdi_csn_i,
        sdi_clk_i => sdi_clk_i,
        sdi_dat_i => sdi_dat_i,
        sdi_dat_o => sdi_dat_o,
        irq_o     => firq(FIRQ_SDI)
      );
    end generate;

    neorv32_sdi_disabled:
    if not IO_SDI_EN generate
      iodev_rsp(IODEV_SDI) <= rsp_terminate_c;
      sdi_dat_o            <= '0';
      firq(FIRQ_SDI)       <= '0';
    end generate;


    -- General Purpose Input/Output Port (GPIO) -----------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_gpio_enabled:
    if io_gpio_en_c generate
      neorv32_gpio_inst: entity neorv32.neorv32_gpio
      generic map (
        GPIO_NUM => IO_GPIO_NUM
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_GPIO),
        bus_rsp_o => iodev_rsp(IODEV_GPIO),
        gpio_o    => gpio_o,
        gpio_i    => gpio_i,
        cpu_irq_o => firq(FIRQ_GPIO)
      );
    end generate;

    neorv32_gpio_disabled:
    if not io_gpio_en_c generate
      iodev_rsp(IODEV_GPIO) <= rsp_terminate_c;
      gpio_o                <= (others => '0');
      firq(FIRQ_GPIO)       <= '0';
    end generate;


    -- Watch Dog Timer (WDT) ------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_wdt_enabled:
    if IO_WDT_EN generate
      neorv32_wdt_inst: entity neorv32.neorv32_wdt
      port map (
        clk_i       => clk_i,
        rstn_ext_i  => rstn_ext,
        rstn_dbg_i  => dci_ndmrstn,
        rstn_sys_i  => rstn_sys,
        bus_req_i   => iodev_req(IODEV_WDT),
        bus_rsp_o   => iodev_rsp(IODEV_WDT),
        clkgen_en_o => clk_gen_en(CG_WDT),
        clkgen_i    => clk_gen,
        rstn_o      => rstn_wdt
      );
    end generate;

    neorv32_wdt_disabled:
    if not IO_WDT_EN generate
      iodev_rsp(IODEV_WDT) <= rsp_terminate_c;
      clk_gen_en(CG_WDT)   <= '0';
      rstn_wdt             <= '1';
    end generate;


    -- Core Local Interruptor (CLINT) ---------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_clint_enabled:
    if IO_CLINT_EN generate
      neorv32_clint_inst: entity neorv32.neorv32_clint
      generic map (
        NUM_HARTS => num_cores_c
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_CLINT),
        bus_rsp_o => iodev_rsp(IODEV_CLINT),
        time_o    => mtime_time_o,
        mti_o     => mtime_irq,
        msi_o     => msw_irq
      );
    end generate;

    neorv32_clint_disabled:
    if not IO_CLINT_EN generate
      iodev_rsp(IODEV_CLINT) <= rsp_terminate_c;
      mtime_time_o           <= (others => '0');
      mtime_irq              <= (others => mtime_irq_i);
      msw_irq                <= (others => msw_irq_i);
    end generate;


    -- Primary Universal Asynchronous Receiver/Transmitter (UART0) ----------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_uart0_enabled:
    if IO_UART0_EN generate
      neorv32_uart0_inst: entity neorv32.neorv32_uart
      generic map (
        SIM_MODE_EN  => true,
        SIM_LOG_FILE => "neorv32.uart0_sim_mode.out",
        UART_RX_FIFO => IO_UART0_RX_FIFO,
        UART_TX_FIFO => IO_UART0_TX_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_UART0),
        bus_rsp_o   => iodev_rsp(IODEV_UART0),
        clkgen_en_o => clk_gen_en(CG_UART0),
        clkgen_i    => clk_gen,
        uart_txd_o  => uart0_txd_o,
        uart_rxd_i  => uart0_rxd_i,
        uart_rtsn_o => uart0_rtsn_o,
        uart_ctsn_i => uart0_ctsn_i,
        irq_rx_o    => firq(FIRQ_UART0_RX),
        irq_tx_o    => firq(FIRQ_UART0_TX)
      );
    end generate;

    neorv32_uart0_disabled:
    if not IO_UART0_EN generate
      iodev_rsp(IODEV_UART0) <= rsp_terminate_c;
      uart0_txd_o            <= '0';
      uart0_rtsn_o           <= '1';
      clk_gen_en(CG_UART0)   <= '0';
      firq(FIRQ_UART0_RX)    <= '0';
      firq(FIRQ_UART0_TX)    <= '0';
    end generate;


    -- Secondary Universal Asynchronous Receiver/Transmitter (UART1) --------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_uart1_enabled:
    if IO_UART1_EN generate
      neorv32_uart1_inst: entity neorv32.neorv32_uart
      generic map (
        SIM_MODE_EN  => true,
        SIM_LOG_FILE => "neorv32.uart1_sim_mode.out",
        UART_RX_FIFO => IO_UART1_RX_FIFO,
        UART_TX_FIFO => IO_UART1_TX_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_UART1),
        bus_rsp_o   => iodev_rsp(IODEV_UART1),
        clkgen_en_o => clk_gen_en(CG_UART1),
        clkgen_i    => clk_gen,
        uart_txd_o  => uart1_txd_o,
        uart_rxd_i  => uart1_rxd_i,
        uart_rtsn_o => uart1_rtsn_o,
        uart_ctsn_i => uart1_ctsn_i,
        irq_rx_o    => firq(FIRQ_UART1_RX),
        irq_tx_o    => firq(FIRQ_UART1_TX)
      );
    end generate;

    neorv32_uart1_disabled:
    if not IO_UART1_EN generate
      iodev_rsp(IODEV_UART1) <= rsp_terminate_c;
      uart1_txd_o            <= '0';
      uart1_rtsn_o           <= '1';
      clk_gen_en(CG_UART1)   <= '0';
      firq(FIRQ_UART1_RX)    <= '0';
      firq(FIRQ_UART1_TX)    <= '0';
    end generate;


    -- Serial Peripheral Interface (SPI) ------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_spi_enabled:
    if IO_SPI_EN generate
      neorv32_spi_inst: entity neorv32.neorv32_spi
      generic map (
        IO_SPI_FIFO => IO_SPI_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_SPI),
        bus_rsp_o   => iodev_rsp(IODEV_SPI),
        clkgen_en_o => clk_gen_en(CG_SPI),
        clkgen_i    => clk_gen,
        spi_clk_o   => spi_clk_o,
        spi_dat_o   => spi_dat_o,
        spi_dat_i   => spi_dat_i,
        spi_csn_o   => spi_csn_o,
        irq_o       => firq(FIRQ_SPI)
      );
    end generate;

    neorv32_spi_disabled:
    if not IO_SPI_EN generate
      iodev_rsp(IODEV_SPI) <= rsp_terminate_c;
      spi_clk_o            <= '0';
      spi_dat_o            <= '0';
      spi_csn_o            <= (others => '1');
      clk_gen_en(CG_SPI)   <= '0';
      firq(FIRQ_SPI)       <= '0';
    end generate;


    -- Two-Wire Interface (TWI) ---------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_twi_enabled:
    if IO_TWI_EN generate
      neorv32_twi_inst: entity neorv32.neorv32_twi
      generic map (
        IO_TWI_FIFO => IO_TWI_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_TWI),
        bus_rsp_o   => iodev_rsp(IODEV_TWI),
        clkgen_en_o => clk_gen_en(CG_TWI),
        clkgen_i    => clk_gen,
        twi_sda_i   => twi_sda_i,
        twi_sda_o   => twi_sda_o,
        twi_scl_i   => twi_scl_i,
        twi_scl_o   => twi_scl_o,
        irq_o       => firq(FIRQ_TWI)
      );
    end generate;

    neorv32_twi_disabled:
    if not IO_TWI_EN generate
      iodev_rsp(IODEV_TWI) <= rsp_terminate_c;
      twi_sda_o            <= '1';
      twi_scl_o            <= '1';
      clk_gen_en(CG_TWI)   <= '0';
      firq(FIRQ_TWI)       <= '0';
    end generate;


    -- Two-Wire Device (TWD) ------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_twd_enabled:
    if IO_TWD_EN generate
      neorv32_twd_inst: entity neorv32.neorv32_twd
      generic map (
        TWD_FIFO => IO_TWD_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_TWD),
        bus_rsp_o   => iodev_rsp(IODEV_TWD),
        clkgen_en_o => clk_gen_en(CG_TWD),
        clkgen_i    => clk_gen,
        twd_sda_i   => twd_sda_i,
        twd_sda_o   => twd_sda_o,
        twd_scl_i   => twd_scl_i,
        twd_scl_o   => twd_scl_o,
        irq_o       => firq(FIRQ_TWD)
      );
    end generate;

    neorv32_twd_disabled:
    if not IO_TWD_EN generate
      iodev_rsp(IODEV_TWD) <= rsp_terminate_c;
      twd_sda_o            <= '1';
      twd_scl_o            <= '1';
      clk_gen_en(CG_TWD)   <= '0';
      firq(FIRQ_TWD)       <= '0';
    end generate;


    -- Pulse-Width Modulation Controller (PWM) ------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_pwm_enabled:
    if io_pwm_en_c generate
      neorv32_pwm_inst: entity neorv32.neorv32_pwm
      generic map (
        NUM_CHANNELS => IO_PWM_NUM_CH
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_PWM),
        bus_rsp_o   => iodev_rsp(IODEV_PWM),
        clkgen_en_o => clk_gen_en(CG_PWM),
        clkgen_i    => clk_gen,
        pwm_o       => pwm_o
      );
    end generate;

    neorv32_pwm_disabled:
    if not io_pwm_en_c generate
      iodev_rsp(IODEV_PWM) <= rsp_terminate_c;
      clk_gen_en(CG_PWM)   <= '0';
      pwm_o                <= (others => '0');
    end generate;


    -- True Random Number Generator (TRNG) ----------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_trng_enabled:
    if IO_TRNG_EN generate
      neorv32_trng_inst: entity neorv32.neorv32_trng
      generic map (
        TRNG_FIFO => IO_TRNG_FIFO
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_TRNG),
        bus_rsp_o => iodev_rsp(IODEV_TRNG)
      );
    end generate;

    neorv32_trng_disabled:
    if not IO_TRNG_EN generate
      iodev_rsp(IODEV_TRNG) <= rsp_terminate_c;
    end generate;


    -- Smart LED (WS2811/WS2812) Interface (NEOLED) -------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_neoled_enabled:
    if IO_NEOLED_EN generate
      neorv32_neoled_inst: entity neorv32.neorv32_neoled
      generic map (
        FIFO_DEPTH => IO_NEOLED_TX_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_NEOLED),
        bus_rsp_o   => iodev_rsp(IODEV_NEOLED),
        clkgen_en_o => clk_gen_en(CG_NEOLED),
        clkgen_i    => clk_gen,
        irq_o       => firq(FIRQ_NEOLED),
        neoled_o    => neoled_o
      );
    end generate;

    neorv32_neoled_disabled:
    if not IO_NEOLED_EN generate
      iodev_rsp(IODEV_NEOLED) <= rsp_terminate_c;
      clk_gen_en(CG_NEOLED)   <= '0';
      firq(FIRQ_NEOLED)       <= '0';
      neoled_o                <= '0';
    end generate;


    -- General Purpose Timer (GPTMR) ----------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_gptmr_enabled:
    if IO_GPTMR_EN generate
      neorv32_gptmr_inst: entity neorv32.neorv32_gptmr
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_GPTMR),
        bus_rsp_o   => iodev_rsp(IODEV_GPTMR),
        clkgen_en_o => clk_gen_en(CG_GPTMR),
        clkgen_i    => clk_gen,
        irq_o       => firq(FIRQ_GPTMR)
      );
    end generate;

    neorv32_gptmr_disabled:
    if not IO_GPTMR_EN generate
      iodev_rsp(IODEV_GPTMR) <= rsp_terminate_c;
      clk_gen_en(CG_GPTMR)   <= '0';
      firq(FIRQ_GPTMR)       <= '0';
    end generate;


    -- 1-Wire Interface Controller (ONEWIRE) --------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_onewire_enabled:
    if IO_ONEWIRE_EN generate
      neorv32_onewire_inst: entity neorv32.neorv32_onewire
      generic map (
        ONEWIRE_FIFO => IO_ONEWIRE_FIFO
      )
      port map (
        clk_i       => clk_i,
        rstn_i      => rstn_sys,
        bus_req_i   => iodev_req(IODEV_ONEWIRE),
        bus_rsp_o   => iodev_rsp(IODEV_ONEWIRE),
        clkgen_en_o => clk_gen_en(CG_ONEWIRE),
        clkgen_i    => clk_gen,
        onewire_i   => onewire_i,
        onewire_o   => onewire_o,
        irq_o       => firq(FIRQ_ONEWIRE)
      );
    end generate;

    neorv32_onewire_disabled:
    if not IO_ONEWIRE_EN generate
      iodev_rsp(IODEV_ONEWIRE) <= rsp_terminate_c;
      onewire_o                <= '1';
      clk_gen_en(CG_ONEWIRE)   <= '0';
      firq(FIRQ_ONEWIRE)       <= '0';
    end generate;


    -- Stream Link Interface (SLINK) ----------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_slink_enabled:
    if IO_SLINK_EN generate
      neorv32_slink_inst: entity neorv32.neorv32_slink
      generic map (
        SLINK_RX_FIFO => IO_SLINK_RX_FIFO,
        SLINK_TX_FIFO => IO_SLINK_TX_FIFO
      )
      port map (
        clk_i            => clk_i,
        rstn_i           => rstn_sys,
        bus_req_i        => iodev_req(IODEV_SLINK),
        bus_rsp_o        => iodev_rsp(IODEV_SLINK),
        rx_irq_o         => firq(FIRQ_SLINK_RX),
        tx_irq_o         => firq(FIRQ_SLINK_TX),
        slink_rx_data_i  => slink_rx_dat_i,
        slink_rx_src_i   => slink_rx_src_i,
        slink_rx_valid_i => slink_rx_val_i,
        slink_rx_last_i  => slink_rx_lst_i,
        slink_rx_ready_o => slink_rx_rdy_o,
        slink_tx_data_o  => slink_tx_dat_o,
        slink_tx_dst_o   => slink_tx_dst_o,
        slink_tx_valid_o => slink_tx_val_o,
        slink_tx_last_o  => slink_tx_lst_o,
        slink_tx_ready_i => slink_tx_rdy_i
      );
    end generate;

    neorv32_slink_disabled:
    if not IO_SLINK_EN generate
      iodev_rsp(IODEV_SLINK) <= rsp_terminate_c;
      firq(FIRQ_SLINK_RX)    <= '0';
      firq(FIRQ_SLINK_TX)    <= '0';
      slink_rx_rdy_o         <= '0';
      slink_tx_dat_o         <= (others => '0');
      slink_tx_dst_o         <= (others => '0');
      slink_tx_val_o         <= '0';
      slink_tx_lst_o         <= '0';
    end generate;


    -- Cyclic Redundancy Check Unit (CRC) -----------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_crc_enabled:
    if IO_CRC_EN generate
      neorv32_crc_inst: entity neorv32.neorv32_crc
        port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_CRC),
        bus_rsp_o => iodev_rsp(IODEV_CRC)
      );
    end generate;

    neorv32_crc_disabled:
    if not IO_CRC_EN generate
      iodev_rsp(IODEV_CRC) <= rsp_terminate_c;
    end generate;


    -- System Configuration Information Memory (SYSINFO) --------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_sysinfo_enabled:
    if io_sysinfo_en_c generate
      neorv32_sysinfo_inst: entity neorv32.neorv32_sysinfo
      generic map (
        NUM_HARTS             => num_cores_c,
        CLOCK_FREQUENCY       => CLOCK_FREQUENCY,
        BOOT_MODE_SELECT      => BOOT_MODE_SELECT,
        INT_BOOTLOADER_EN     => bootrom_en_c,
        MEM_INT_IMEM_EN       => MEM_INT_IMEM_EN,
        MEM_INT_IMEM_ROM      => imem_as_rom_c,
        MEM_INT_IMEM_SIZE     => imem_size_c,
        MEM_INT_DMEM_EN       => MEM_INT_DMEM_EN,
        MEM_INT_DMEM_SIZE     => dmem_size_c,
        ICACHE_EN             => ICACHE_EN,
        ICACHE_NUM_BLOCKS     => ICACHE_NUM_BLOCKS,
        ICACHE_BLOCK_SIZE     => ICACHE_BLOCK_SIZE,
        DCACHE_EN             => DCACHE_EN,
        DCACHE_NUM_BLOCKS     => DCACHE_NUM_BLOCKS,
        DCACHE_BLOCK_SIZE     => DCACHE_BLOCK_SIZE,
        XBUS_EN               => XBUS_EN,
        XBUS_CACHE_EN         => XBUS_CACHE_EN,
        XBUS_CACHE_NUM_BLOCKS => XBUS_CACHE_NUM_BLOCKS,
        XBUS_CACHE_BLOCK_SIZE => XBUS_CACHE_BLOCK_SIZE,
        OCD_EN                => OCD_EN,
        OCD_AUTHENTICATION    => OCD_AUTHENTICATION,
        IO_GPIO_EN            => io_gpio_en_c,
        IO_CLINT_EN           => IO_CLINT_EN,
        IO_UART0_EN           => IO_UART0_EN,
        IO_UART1_EN           => IO_UART1_EN,
        IO_SPI_EN             => IO_SPI_EN,
        IO_SDI_EN             => IO_SDI_EN,
        IO_TWI_EN             => IO_TWI_EN,
        IO_TWD_EN             => IO_TWD_EN,
        IO_PWM_EN             => io_pwm_en_c,
        IO_WDT_EN             => IO_WDT_EN,
        IO_TRNG_EN            => IO_TRNG_EN,
        IO_CFS_EN             => IO_CFS_EN,
        IO_NEOLED_EN          => IO_NEOLED_EN,
        IO_GPTMR_EN           => IO_GPTMR_EN,
        IO_ONEWIRE_EN         => IO_ONEWIRE_EN,
        IO_DMA_EN             => IO_DMA_EN,
        IO_SLINK_EN           => IO_SLINK_EN,
        IO_CRC_EN             => IO_CRC_EN
      )
      port map (
        clk_i     => clk_i,
        rstn_i    => rstn_sys,
        bus_req_i => iodev_req(IODEV_SYSINFO),
        bus_rsp_o => iodev_rsp(IODEV_SYSINFO)
      );
    end generate;

    neorv32_sysinfo_disabled:
    if not io_sysinfo_en_c generate
      iodev_rsp(IODEV_SYSINFO) <= rsp_terminate_c;
    end generate;


  end generate; -- /io_system


  -- **************************************************************************************************************************
  -- On-Chip Debugger Complex
  -- **************************************************************************************************************************

  neorv32_ocd_enabled:
  if OCD_EN generate

    -- On-Chip Debugger - Debug Transport Module (DTM) ----------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_debug_dtm_inst: entity neorv32.neorv32_debug_dtm
    generic map (
      IDCODE_VERSION => (others => '0'), -- yet unused
      IDCODE_PARTID  => (others => '0'), -- yet unused
      IDCODE_MANID   => OCD_JEDEC_ID
    )
    port map (
      clk_i      => clk_i,
      rstn_i     => rstn_ext,
      jtag_tck_i => jtag_tck_i,
      jtag_tdi_i => jtag_tdi_i,
      jtag_tdo_o => jtag_tdo_o,
      jtag_tms_i => jtag_tms_i,
      dmi_req_o  => dmi_req,
      dmi_rsp_i  => dmi_rsp
    );

    -- On-Chip Debugger - Debug Module (DM) ---------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_debug_dm_inst: entity neorv32.neorv32_debug_dm
    generic map (
      NUM_HARTS     => num_cores_c,
      AUTHENTICATOR => OCD_AUTHENTICATION
    )
    port map (
      clk_i      => clk_i,
      rstn_i     => rstn_ext,
      dmi_req_i  => dmi_req,
      dmi_rsp_o  => dmi_rsp,
      bus_req_i  => iodev_req(IODEV_OCD),
      bus_rsp_o  => iodev_rsp(IODEV_OCD),
      ndmrstn_o  => dci_ndmrstn,
      halt_req_o => dci_haltreq
    );

  end generate; -- /neorv32_ocd_enabled

  neorv32_debug_ocd_disabled:
  if not OCD_EN generate
    iodev_rsp(IODEV_OCD) <= rsp_terminate_c;
    jtag_tdo_o           <= jtag_tdi_i; -- JTAG pass-through
    dci_ndmrstn          <= '1';
    dci_haltreq          <= (others => '0');
  end generate;


end neorv32_top_rtl;
