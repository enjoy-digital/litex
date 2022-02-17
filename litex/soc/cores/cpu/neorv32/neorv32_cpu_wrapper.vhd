library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_wrapper is
  generic (
    -- General --
    HW_THREAD_ID                 : natural                        := 0;           -- hardware thread id (32-bit)
    CPU_BOOT_ADDR                : std_ulogic_vector(31 downto 0) := x"00000000"; -- cpu boot address
    CPU_DEBUG_ADDR               : std_ulogic_vector(31 downto 0) := x"00000000"; -- cpu debug mode start address
    -- RISC-V CPU Extensions --
    CPU_EXTENSION_RISCV_A        : boolean := false; -- implement atomic extension?
    CPU_EXTENSION_RISCV_B        : boolean := false; -- implement bit-manipulation extension?
    CPU_EXTENSION_RISCV_C        : boolean := false; -- implement compressed extension?
    CPU_EXTENSION_RISCV_E        : boolean := false; -- implement embedded RF extension?
    CPU_EXTENSION_RISCV_M        : boolean := true;  -- implement muld/div extension?
    CPU_EXTENSION_RISCV_U        : boolean := true;  -- implement user mode extension?
    CPU_EXTENSION_RISCV_Zfinx    : boolean := false; -- implement 32-bit floating-point extension (using INT reg!)
    CPU_EXTENSION_RISCV_Zicsr    : boolean := true;  -- implement CSR system?
    CPU_EXTENSION_RISCV_Zicntr   : boolean := true;  -- implement base counters?
    CPU_EXTENSION_RISCV_Zihpm    : boolean := false; -- implement hardware performance monitors?
    CPU_EXTENSION_RISCV_Zifencei : boolean := false; -- implement instruction stream sync.?
    CPU_EXTENSION_RISCV_Zmmul    : boolean := false; -- implement multiply-only M sub-extension?
    CPU_EXTENSION_RISCV_Zxcfu    : boolean := false; -- implement custom (instr.) functions unit?
    CPU_EXTENSION_RISCV_DEBUG    : boolean := false; -- implement CPU debug mode?
    -- Extension Options --
    FAST_MUL_EN                  : boolean := true; -- use DSPs for M extension's multiplier
    FAST_SHIFT_EN                : boolean := true; -- use barrel shifter for shift operations
    CPU_CNT_WIDTH                : natural := 32;   -- total width of CPU cycle and instret counters (0..64)
    CPU_IPB_ENTRIES              : natural :=  4;   -- entries is instruction prefetch buffer, has to be a power of 2
    -- Physical Memory Protection (PMP) --
    PMP_NUM_REGIONS              : natural := 4; -- number of regions (0..64)
    PMP_MIN_GRANULARITY          : natural := 8; -- minimal region granularity in bytes, has to be a power of 2, min 8 bytes
    -- Hardware Performance Monitors (HPM) --
    HPM_NUM_CNTS                 : natural := 0; -- number of implemented HPM counters (0..29)
    HPM_CNT_WIDTH                : natural := 32 -- total size of HPM counters (0..64)
  );
  port (
    -- global control --
    clk_i         : in  std_ulogic; -- global clock, rising edge
    rstn_i        : in  std_ulogic; -- global reset, low-active, async
    sleep_o       : out std_ulogic; -- cpu is in sleep mode when set
    debug_o       : out std_ulogic; -- cpu is in debug mode when set
    -- instruction bus interface --
    i_bus_addr_o  : out std_ulogic_vector(data_width_c-1 downto 0); -- bus access address
    i_bus_rdata_i : in  std_ulogic_vector(data_width_c-1 downto 0); -- bus read data
    i_bus_wdata_o : out std_ulogic_vector(data_width_c-1 downto 0); -- bus write data
    i_bus_ben_o   : out std_ulogic_vector(03 downto 0); -- byte enable
    i_bus_we_o    : out std_ulogic; -- write enable
    i_bus_re_o    : out std_ulogic; -- read enable
    i_bus_lock_o  : out std_ulogic; -- exclusive access request
    i_bus_ack_i   : in  std_ulogic; -- bus transfer acknowledge
    i_bus_err_i   : in  std_ulogic; -- bus transfer error
    i_bus_fence_o : out std_ulogic; -- executed FENCEI operation
    i_bus_priv_o  : out std_ulogic_vector(1 downto 0); -- privilege level
    -- data bus interface --
    d_bus_addr_o  : out std_ulogic_vector(data_width_c-1 downto 0); -- bus access address
    d_bus_rdata_i : in  std_ulogic_vector(data_width_c-1 downto 0); -- bus read data
    d_bus_wdata_o : out std_ulogic_vector(data_width_c-1 downto 0); -- bus write data
    d_bus_ben_o   : out std_ulogic_vector(03 downto 0); -- byte enable
    d_bus_we_o    : out std_ulogic; -- write enable
    d_bus_re_o    : out std_ulogic; -- read enable
    d_bus_lock_o  : out std_ulogic; -- exclusive access request
    d_bus_ack_i   : in  std_ulogic; -- bus transfer acknowledge
    d_bus_err_i   : in  std_ulogic; -- bus transfer error
    d_bus_fence_o : out std_ulogic; -- executed FENCE operation
    d_bus_priv_o  : out std_ulogic_vector(1 downto 0); -- privilege level
    -- system time input from MTIME --
    time_i        : in  std_ulogic_vector(63 downto 0); -- current system time
    -- interrupts (risc-v compliant) --
    msw_irq_i     : in  std_ulogic;-- machine software interrupt
    mext_irq_i    : in  std_ulogic;-- machine external interrupt
    mtime_irq_i   : in  std_ulogic;-- machine timer interrupt
    -- fast interrupts (custom) --
    firq_i        : in  std_ulogic_vector(15 downto 0);
    -- debug mode (halt) request --
    db_halt_req_i : in  std_ulogic
  );
end neorv32_cpu_wrapper;

architecture neorv32_cpu_wrapper_rtl of neorv32_cpu_wrapper is

begin

  neorv32_cpu_inst: neorv32_cpu
    generic map (
      HW_THREAD_ID                 => HW_THREAD_ID                ,
      CPU_BOOT_ADDR                => CPU_BOOT_ADDR               ,
      CPU_DEBUG_ADDR               => CPU_DEBUG_ADDR              ,
      CPU_EXTENSION_RISCV_A        => CPU_EXTENSION_RISCV_A       ,
      CPU_EXTENSION_RISCV_B        => CPU_EXTENSION_RISCV_B       ,
      CPU_EXTENSION_RISCV_C        => CPU_EXTENSION_RISCV_C       ,
      CPU_EXTENSION_RISCV_E        => CPU_EXTENSION_RISCV_E       ,
      CPU_EXTENSION_RISCV_M        => CPU_EXTENSION_RISCV_M       ,
      CPU_EXTENSION_RISCV_U        => CPU_EXTENSION_RISCV_U       ,
      CPU_EXTENSION_RISCV_Zfinx    => CPU_EXTENSION_RISCV_Zfinx   ,
      CPU_EXTENSION_RISCV_Zicsr    => CPU_EXTENSION_RISCV_Zicsr   ,
      CPU_EXTENSION_RISCV_Zicntr   => CPU_EXTENSION_RISCV_Zicntr  ,
      CPU_EXTENSION_RISCV_Zihpm    => CPU_EXTENSION_RISCV_Zihpm   ,
      CPU_EXTENSION_RISCV_Zifencei => CPU_EXTENSION_RISCV_Zifencei,
      CPU_EXTENSION_RISCV_Zmmul    => CPU_EXTENSION_RISCV_Zmmul   ,
      CPU_EXTENSION_RISCV_Zxcfu    => CPU_EXTENSION_RISCV_Zxcfu   ,
      CPU_EXTENSION_RISCV_DEBUG    => CPU_EXTENSION_RISCV_DEBUG   ,
      FAST_MUL_EN                  => FAST_MUL_EN                 ,
      FAST_SHIFT_EN                => FAST_SHIFT_EN               ,
      CPU_CNT_WIDTH                => CPU_CNT_WIDTH               ,
      CPU_IPB_ENTRIES              => CPU_IPB_ENTRIES             ,
      PMP_NUM_REGIONS              => PMP_NUM_REGIONS             ,
      PMP_MIN_GRANULARITY          => PMP_MIN_GRANULARITY         ,
      HPM_NUM_CNTS                 => HPM_NUM_CNTS                ,
      HPM_CNT_WIDTH                => HPM_CNT_WIDTH
  )
  port map (
    clk_i         => clk_i        ,
    rstn_i        => rstn_i       ,
    sleep_o       => sleep_o      ,
    debug_o       => debug_o      ,
    i_bus_addr_o  => i_bus_addr_o ,
    i_bus_rdata_i => i_bus_rdata_i,
    i_bus_wdata_o => i_bus_wdata_o,
    i_bus_ben_o   => i_bus_ben_o  ,
    i_bus_we_o    => i_bus_we_o   ,
    i_bus_re_o    => i_bus_re_o   ,
    i_bus_lock_o  => i_bus_lock_o ,
    i_bus_ack_i   => i_bus_ack_i  ,
    i_bus_err_i   => i_bus_err_i  ,
    i_bus_fence_o => i_bus_fence_o,
    i_bus_priv_o  => i_bus_priv_o ,
    d_bus_addr_o  => d_bus_addr_o ,
    d_bus_rdata_i => d_bus_rdata_i,
    d_bus_wdata_o => d_bus_wdata_o,
    d_bus_ben_o   => d_bus_ben_o  ,
    d_bus_we_o    => d_bus_we_o   ,
    d_bus_re_o    => d_bus_re_o   ,
    d_bus_lock_o  => d_bus_lock_o ,
    d_bus_ack_i   => d_bus_ack_i  ,
    d_bus_err_i   => d_bus_err_i  ,
    d_bus_fence_o => d_bus_fence_o,
    d_bus_priv_o  => d_bus_priv_o ,
    time_i        => time_i       ,
    msw_irq_i     => msw_irq_i    ,
    mext_irq_i    => mext_irq_i   ,
    mtime_irq_i   => mtime_irq_i  ,
    firq_i        => firq_i       ,
    db_halt_req_i => db_halt_req_i
  );

end neorv32_cpu_wrapper_rtl;
