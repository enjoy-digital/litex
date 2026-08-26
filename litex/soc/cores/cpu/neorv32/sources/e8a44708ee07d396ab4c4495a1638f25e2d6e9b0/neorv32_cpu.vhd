-- ================================================================================ --
-- NEORV32 CPU - CPU Top Entity                                                     --
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

entity neorv32_cpu is
  generic (
    -- General --
    HART_ID             : natural range 0 to 1023;        -- hardware thread ID
    VENDOR_ID           : std_ulogic_vector(31 downto 0); -- vendor ID
    BOOT_ADDR           : std_ulogic_vector(31 downto 0); -- CPU boot address
    DEBUG_PARK_ADDR     : std_ulogic_vector(31 downto 0); -- CPU debug mode parking loop entry address
    DEBUG_EXC_ADDR      : std_ulogic_vector(31 downto 0); -- CPU debug mode exception entry address
    -- RISC-V ISA Extensions --
    RISCV_ISA_C         : boolean;                        -- compressed extension
    RISCV_ISA_E         : boolean;                        -- embedded RF extension
    RISCV_ISA_M         : boolean;                        -- mul/div extension
    RISCV_ISA_U         : boolean;                        -- user mode extension
    RISCV_ISA_Zaamo     : boolean;                        -- atomic read-modify-write operations extension
    RISCV_ISA_Zalrsc    : boolean;                        -- atomic reservation-set operations extension
    RISCV_ISA_Zba       : boolean;                        -- shifted-add bit-manipulation extension
    RISCV_ISA_Zbb       : boolean;                        -- basic bit-manipulation extension
    RISCV_ISA_Zbkb      : boolean;                        -- bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc      : boolean;                        -- carry-less multiplication instructions
    RISCV_ISA_Zbkx      : boolean;                        -- cryptography crossbar permutation extension
    RISCV_ISA_Zbs       : boolean;                        -- single-bit bit-manipulation extension
    RISCV_ISA_Zcb       : boolean;                        -- additional code size reduction instructions
    RISCV_ISA_Zfinx     : boolean;                        -- 32-bit floating-point extension
    RISCV_ISA_Zibi      : boolean;                        -- branch with immediate
    RISCV_ISA_Zicntr    : boolean;                        -- base counters
    RISCV_ISA_Zicond    : boolean;                        -- integer conditional operations
    RISCV_ISA_Zihpm     : boolean;                        -- hardware performance monitors
    RISCV_ISA_Zimop     : boolean;                        -- may-be-operations
    RISCV_ISA_Zknd      : boolean;                        -- cryptography NIST AES decryption extension
    RISCV_ISA_Zkne      : boolean;                        -- cryptography NIST AES encryption extension
    RISCV_ISA_Zknh      : boolean;                        -- cryptography NIST hash extension
    RISCV_ISA_Zksed     : boolean;                        -- ShangMi hash extension
    RISCV_ISA_Zksh      : boolean;                        -- ShangMi block cipher extension
    RISCV_ISA_Zmmul     : boolean;                        -- multiply-only M sub-extension
    RISCV_ISA_Zxcfu     : boolean;                        -- custom (instr.) functions unit
    RISCV_ISA_Sdext     : boolean;                        -- external debug mode extension
    RISCV_ISA_Sdtrig    : boolean;                        -- trigger module extension
    RISCV_ISA_Smpmp     : boolean;                        -- physical memory protection
    -- Tuning Options --
    CPU_TRACE_EN        : boolean;                        -- enable CPU execution trace generator
    CPU_CONSTT_BR_EN    : boolean;                        -- constant-time branches
    CPU_FAST_MUL_EN     : boolean;                        -- use DSPs for M extension's multiplier
    CPU_FAST_SHIFT_EN   : boolean;                        -- use barrel shifter for shift operations
    CPU_RF_ARCH_SEL     : natural range 0 to 3;           -- register file implementation style select
    -- Physical Memory Protection (PMP) --
    PMP_NUM_REGIONS     : natural range 0 to 16;          -- number of regions (0..16)
    PMP_MIN_GRANULARITY : natural;                        -- minimal region granularity in bytes, has to be a power of 2, min 4 bytes
    PMP_TOR_MODE_EN     : boolean;                        -- enable TOR mode
    PMP_NAP_MODE_EN     : boolean;                        -- enable NAPOT/NA4 modes
    -- Hardware Performance Monitors (HPM) --
    HPM_NUM_CNTS        : natural range 0 to 13;          -- number of implemented HPM counters (0..13)
    HPM_CNT_WIDTH       : natural range 0 to 64;          -- total size of HPM counters (0..64)
    -- Trigger Module (TM) --
    NUM_HW_TRIGGERS     : natural range 0 to 16           -- number of hardware triggers
  );
  port (
    -- global control --
    clk_i      : in  std_ulogic;                     -- global clock, rising edge
    rstn_i     : in  std_ulogic;                     -- global reset, low-active, async
    -- status --
    trace_o    : out trace_port_t;                   -- execution trace port (enabled when CPU_TRACE_EN = true)
    sleep_o    : out std_ulogic;                     -- CPU is in sleep mode
    -- interrupts --
    msi_i      : in  std_ulogic;                     -- RISC-V machine software interrupt
    mei_i      : in  std_ulogic;                     -- RISC-V machine external interrupt
    mti_i      : in  std_ulogic;                     -- RISC-V machine timer interrupt
    firq_i     : in  std_ulogic_vector(15 downto 0); -- custom fast interrupts
    dbi_i      : in  std_ulogic;                     -- RISC-V debug halt request interrupt
    -- instruction bus interface --
    ibus_req_o : out bus_req_t;                      -- request bus
    ibus_rsp_i : in  bus_rsp_t;                      -- response bus
    -- data bus interface --
    dbus_req_o : out bus_req_t;                      -- request bus
    dbus_rsp_i : in  bus_rsp_t                       -- response bus
  );
end neorv32_cpu;

architecture neorv32_cpu_rtl of neorv32_cpu is

  -- auto-configuration --
  constant rf_awidth_c : natural := cond_sel_natural_f(RISCV_ISA_E, 4, 5); -- register file address width
  constant riscv_a_c   : boolean := RISCV_ISA_Zaamo and RISCV_ISA_Zalrsc; -- A: atomic memory operations
  constant riscv_b_c   : boolean := RISCV_ISA_Zba and RISCV_ISA_Zbb and RISCV_ISA_Zbs; -- B: bit manipulation
  constant riscv_zcb_c : boolean := RISCV_ISA_C and RISCV_ISA_Zcb; -- Zcb: additional compressed instructions
  constant riscv_zkt_c : boolean := CPU_FAST_SHIFT_EN; -- Zkt: data-independent execution time for cryptography operations
  constant riscv_zkn_c : boolean := RISCV_ISA_Zbkb and RISCV_ISA_Zbkc and RISCV_ISA_Zbkx and
                                    RISCV_ISA_Zkne and RISCV_ISA_Zknd and RISCV_ISA_Zknh; -- Zkn: NIST suite
  constant riscv_zks_c : boolean := RISCV_ISA_Zbkb and RISCV_ISA_Zbkc and RISCV_ISA_Zbkx and
                                    RISCV_ISA_Zksh and RISCV_ISA_Zksed; -- Zks: ShangMi suite

  -- local signals --
  signal ctrl        : ctrl_bus_t;                     -- main control bus
  signal frontend    : if_bus_t;                       -- instruction-fetch interface
  signal if_pmp_addr : std_ulogic_vector(31 downto 0); -- instruction fetch access address
  signal if_pmp_priv : std_ulogic;                     -- instruction fetch access privilege level
  signal if_pmp_err  : std_ulogic;                     -- instruction fetch PMP access fault
  signal rw_pmp_err  : std_ulogic;                     -- data access PMP access fault
  signal hwtrig      : std_ulogic;                     -- hardware trigger firing
  signal rf_wdata    : std_ulogic_vector(31 downto 0); -- register file write data
  signal rs1         : std_ulogic_vector(31 downto 0); -- source register 1
  signal rs2         : std_ulogic_vector(31 downto 0); -- source register 2
  signal alu_res     : std_ulogic_vector(31 downto 0); -- ALU result
  signal alu_add     : std_ulogic_vector(31 downto 0); -- ALU address result
  signal alu_cmp     : std_ulogic_vector(1 downto 0);  -- comparator result
  signal alu_cp_done : std_ulogic;                     -- ALU co-processor operation done
  signal lsu_rdata   : std_ulogic_vector(31 downto 0); -- LSU memory read data
  signal lsu_mar     : std_ulogic_vector(31 downto 0); -- LSU memory address register
  signal lsu_err     : std_ulogic_vector(3 downto 0);  -- LSU alignment/access errors
  signal lsu_wait    : std_ulogic;                     -- wait for current data bus access
  signal dbus_req    : bus_req_t;                      -- data bus request
  signal csr_rdata   : std_ulogic_vector(31 downto 0); -- CSR read data
  signal irq_machine : std_ulogic_vector(2 downto 0);  -- RISC-V standard machine-level interrupts

  -- external CSR interface read-back --
  signal xcsr_tm, xcsr_cnt, xcsr_pmp, xcsr_alu, xcsr_res : std_ulogic_vector(31 downto 0);

begin

  -- Configuration Info and Checks ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  hello_neorv32:
  if HART_ID = 0 generate -- print only for core 0

    -- CPU ISA configuration (in alphabetical order - not in canonical order) --
    assert false report "[NEORV32] CPU ISA: rv32" &
      cond_sel_string_f(RISCV_ISA_E,      "e",         "i") &
      cond_sel_string_f(riscv_a_c,        "a",         "" ) &
      cond_sel_string_f(riscv_b_c,        "b",         "" ) &
      cond_sel_string_f(RISCV_ISA_C,      "c",         "" ) &
      cond_sel_string_f(RISCV_ISA_M,      "m",         "" ) &
      cond_sel_string_f(RISCV_ISA_U,      "u",         "" ) &
      cond_sel_string_f(true,             "x",         "" ) & -- always enabled
      cond_sel_string_f(RISCV_ISA_Zaamo,  "_zaamo",    "" ) &
      cond_sel_string_f(RISCV_ISA_Zalrsc, "_zalrsc",   "" ) &
      cond_sel_string_f(RISCV_ISA_C,      "_zca",      "" ) &
      cond_sel_string_f(riscv_zcb_c,      "_zcb",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zba,    "_zba",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zbb,    "_zbb",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zbkb,   "_zbkb",     "" ) &
      cond_sel_string_f(RISCV_ISA_Zbkc,   "_zbkc",     "" ) &
      cond_sel_string_f(RISCV_ISA_Zbkx,   "_zbkx",     "" ) &
      cond_sel_string_f(RISCV_ISA_Zbs,    "_zbs",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zfinx,  "_zfinx",    "" ) &
      cond_sel_string_f(RISCV_ISA_Zibi,   "_zibi",     "" ) &
      cond_sel_string_f(RISCV_ISA_Zicntr, "_zicntr",   "" ) &
      cond_sel_string_f(RISCV_ISA_Zicond, "_zicond",   "" ) &
      cond_sel_string_f(true,             "_zicsr",    "" ) & -- always enabled
      cond_sel_string_f(true,             "_zifencei", "" ) & -- always enabled
      cond_sel_string_f(RISCV_ISA_Zihpm,  "_zihpm",    "" ) &
      cond_sel_string_f(RISCV_ISA_Zimop,  "_zimop",    "" ) &
      cond_sel_string_f(riscv_zkn_c,      "_zkn",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zknd,   "_zknd",     "" ) &
      cond_sel_string_f(RISCV_ISA_Zkne,   "_zkne",     "" ) &
      cond_sel_string_f(RISCV_ISA_Zknh,   "_zknh",     "" ) &
      cond_sel_string_f(riscv_zks_c,      "_zks",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zksed,  "_zksed",    "" ) &
      cond_sel_string_f(RISCV_ISA_Zksh,   "_zksh",     "" ) &
      cond_sel_string_f(riscv_zkt_c,      "_zkt",      "" ) &
      cond_sel_string_f(RISCV_ISA_Zmmul,  "_zmmul",    "" ) &
      cond_sel_string_f(RISCV_ISA_Zxcfu,  "_zxcfu",    "" ) &
      cond_sel_string_f(RISCV_ISA_Sdext,  "_sdext",    "" ) &
      cond_sel_string_f(RISCV_ISA_Sdtrig, "_sdtrig",   "" ) &
      cond_sel_string_f(RISCV_ISA_Smpmp,  "_smpmp",    "" )
      severity note;

    -- CPU tuning options --
    assert false report "[NEORV32] CPU tuning options: " &
      cond_sel_string_f(CPU_TRACE_EN,                 "trace ",              "") &
      cond_sel_string_f(CPU_CONSTT_BR_EN,             "constt_br ",          "") &
      cond_sel_string_f(CPU_FAST_MUL_EN,              "fast_mul ",           "") &
      cond_sel_string_f(CPU_FAST_SHIFT_EN,            "fast_shift ",         "") &
      cond_sel_string_f(boolean(CPU_RF_ARCH_SEL = 0), "rf_arch=sram_sync ",  "") &
      cond_sel_string_f(boolean(CPU_RF_ARCH_SEL = 1), "rf_arch=sram_async ", "") &
      cond_sel_string_f(boolean(CPU_RF_ARCH_SEL = 2), "rf_arch=reg",         "") &
      cond_sel_string_f(boolean(CPU_RF_ARCH_SEL = 3), "rf_arch=latch ",      "")
      severity note;

  end generate;


  -- Front-End (Instruction Fetch) ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_frontend_inst: entity neorv32.neorv32_cpu_frontend
  generic map (
    HART_ID   => HART_ID,      -- hardware thread ID
    RISCV_C   => RISCV_ISA_C,  -- implement C ISA extension
    RISCV_ZCB => RISCV_ISA_Zcb -- implement Zcb ISA sub-extension
  )
  port map (
    -- global control --
    clk_i      => clk_i,       -- global clock, rising edge
    rstn_i     => rstn_i,      -- global reset, low-active, async
    ctrl_i     => ctrl,        -- main control bus
    -- instruction fetch interface --
    ibus_req_o => ibus_req_o,  -- request
    ibus_rsp_i => ibus_rsp_i,  -- response
    -- PMP interface --
    pmp_addr_o => if_pmp_addr, -- access address
    pmp_priv_o => if_pmp_priv, -- access privilege level
    pmp_err_i  => if_pmp_err,  -- PMP access fault
    -- back-end interface --
    frontend_o => frontend     -- fetch data and status
  );


  -- Control Unit / Back-End (Instruction Execution) ----------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_control_inst: entity neorv32.neorv32_cpu_control
  generic map (
    -- General --
    HART_ID          => HART_ID,          -- hardware thread ID
    VENDOR_ID        => VENDOR_ID,        -- vendor ID
    BOOT_ADDR        => BOOT_ADDR,        -- CPU boot address
    DEBUG_PARK_ADDR  => DEBUG_PARK_ADDR,  -- CPU debug mode parking loop entry address
    DEBUG_EXC_ADDR   => DEBUG_EXC_ADDR,   -- CPU debug mode exception entry address
    -- RISC-V ISA Extensions --
    RISCV_ISA_A      => riscv_a_c,        -- atomic memory operations extension
    RISCV_ISA_B      => riscv_b_c,        -- bit-manipulation extension
    RISCV_ISA_C      => RISCV_ISA_C,      -- compressed extension
    RISCV_ISA_E      => RISCV_ISA_E,      -- embedded RF extension
    RISCV_ISA_M      => RISCV_ISA_M,      -- mul/div extension
    RISCV_ISA_U      => RISCV_ISA_U,      -- user mode extension
    RISCV_ISA_Zaamo  => RISCV_ISA_Zaamo,  -- atomic read-modify-write operations extension
    RISCV_ISA_Zalrsc => RISCV_ISA_Zalrsc, -- atomic reservation-set operations extension
    RISCV_ISA_Zcb    => riscv_zcb_c,      -- additional code size reduction instructions
    RISCV_ISA_Zba    => RISCV_ISA_Zba,    -- shifted-add bit-manipulation extension
    RISCV_ISA_Zbb    => RISCV_ISA_Zbb,    -- basic bit-manipulation extension
    RISCV_ISA_Zbkb   => RISCV_ISA_Zbkb,   -- bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc   => RISCV_ISA_Zbkc,   -- carry-less multiplication instructions
    RISCV_ISA_Zbkx   => RISCV_ISA_Zbkx,   -- cryptography crossbar permutation extension
    RISCV_ISA_Zbs    => RISCV_ISA_Zbs,    -- single-bit bit-manipulation extension
    RISCV_ISA_Zfinx  => RISCV_ISA_Zfinx,  -- 32-bit floating-point extension
    RISCV_ISA_Zibi   => RISCV_ISA_Zibi,   -- branch with immediate
    RISCV_ISA_Zicntr => RISCV_ISA_Zicntr, -- base counters
    RISCV_ISA_Zicond => RISCV_ISA_Zicond, -- integer conditional operations
    RISCV_ISA_Zihpm  => RISCV_ISA_Zihpm,  -- hardware performance monitors
    RISCV_ISA_Zimop  => RISCV_ISA_Zimop,  -- may-be-operations
    RISCV_ISA_Zkn    => riscv_zkn_c,      -- NIST algorithm suite available
    RISCV_ISA_Zknd   => RISCV_ISA_Zknd,   -- cryptography NIST AES decryption extension
    RISCV_ISA_Zkne   => RISCV_ISA_Zkne,   -- cryptography NIST AES encryption extension
    RISCV_ISA_Zknh   => RISCV_ISA_Zknh,   -- cryptography NIST hash extension
    RISCV_ISA_Zks    => riscv_zks_c,      -- ShangMi algorithm suite available
    RISCV_ISA_Zksed  => RISCV_ISA_Zksed,  -- ShangMi block cipher extension
    RISCV_ISA_Zksh   => RISCV_ISA_Zksh,   -- ShangMi hash extension
    RISCV_ISA_Zkt    => riscv_zkt_c,      -- data-independent execution time for cryptography operations available
    RISCV_ISA_Zmmul  => RISCV_ISA_Zmmul,  -- multiply-only M sub-extension
    RISCV_ISA_Zxcfu  => RISCV_ISA_Zxcfu,  -- custom (instr.) functions unit
    RISCV_ISA_Sdext  => RISCV_ISA_Sdext,  -- external debug mode extension
    RISCV_ISA_Sdtrig => RISCV_ISA_Sdtrig, -- trigger module extension
    RISCV_ISA_Smpmp  => RISCV_ISA_Smpmp,  -- physical memory protection
    -- Tuning Options --
    CPU_CONSTT_BR_EN => CPU_CONSTT_BR_EN  -- constant-time branches
  )
  port map (
    -- global control --
    clk_i         => clk_i,       -- global clock, rising edge
    rstn_i        => rstn_i,      -- global reset, low-active, async
    ctrl_o        => ctrl,        -- main control bus
    -- misc --
    frontend_i    => frontend,    -- front-end status and data
    hwtrig_i      => hwtrig,      -- hardware trigger
    -- data path interface --
    alu_cp_done_i => alu_cp_done, -- ALU iterative operation done
    alu_cmp_i     => alu_cmp,     -- comparator status
    alu_add_i     => alu_add,     -- ALU address result
    rf_rs1_i      => rs1,         -- register file source 1
    csr_rdata_o   => csr_rdata,   -- CSR read data
    xcsr_rdata_i  => xcsr_res,    -- external CSR read data
    -- interrupts --
    irq_dbg_i     => dbi_i,       -- debug mode (halt) request
    irq_machine_i => irq_machine, -- RISC-V interrupts
    irq_fast_i    => firq_i,      -- fast interrupts
    -- load/store unit interface --
    lsu_wait_i    => lsu_wait,    -- wait for data bus
    lsu_mar_i     => lsu_mar,     -- memory address register
    lsu_err_i     => lsu_err      -- alignment/access errors
  );

  -- RISC-V machine interrupts --
  irq_machine <= mei_i & mti_i & msi_i;

  -- control-external CSR read-back --
  xcsr_res <= xcsr_tm or xcsr_cnt or xcsr_alu or xcsr_pmp;

  -- CPU is sleeping --
  sleep_o <= not ctrl.cnt_event(cnt_event_cy_c);


  -- Hardware Trigger Module (Sdtrig) -------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trigger_module_enabled:
  if (RISCV_ISA_Sdtrig = true) and (NUM_HW_TRIGGERS > 0) generate
    neorv32_cpu_hwtrig_inst: entity neorv32.neorv32_cpu_hwtrig
    generic map (
      NUM_TRIGGERS => NUM_HW_TRIGGERS, -- number of implemented hardware triggers
      RISCV_ISA_U  => RISCV_ISA_U      -- RISC-V user-mode available
    )
    port map (
    -- global control --
      clk_i  => clk_i,   -- global clock, rising edge
      rstn_i => rstn_i,  -- global reset, low-active, async
      ctrl_i => ctrl,    -- main control bus
      -- data path --
      mar_i  => lsu_mar, -- memory address register
      csr_o  => xcsr_tm, -- CSR read data
      -- trigger firing --
      hit_o  => hwtrig   -- high until debug-mode is entered
    );
  end generate;

  trigger_module_disabled:
  if (RISCV_ISA_Sdtrig = false) or (NUM_HW_TRIGGERS = 0) generate
    xcsr_tm <= (others => '0');
    hwtrig  <= '0';
  end generate;


  -- Hardware Counters ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cnts_enabled:
  if RISCV_ISA_Zicntr or RISCV_ISA_Zihpm generate
    neorv32_cpu_counters_inst: entity neorv32.neorv32_cpu_counters
    generic map (
      ZICNTR_EN => RISCV_ISA_Zicntr, -- implement base counters
      ZIHPM_EN  => RISCV_ISA_Zihpm,  -- implement hardware performance monitors (HPMs)
      HPM_NUM   => HPM_NUM_CNTS,     -- number of implemented HPM counters (0..13)
      HPM_WIDTH => HPM_CNT_WIDTH     -- total size of HPM counters (0..64)
    )
    port map (
      -- global control --
      clk_i   => clk_i,   -- global clock, rising edge
      rstn_i  => rstn_i,  -- global reset, low-active, async
      ctrl_i  => ctrl,    -- main control bus
      -- read back --
      rdata_o => xcsr_cnt -- read data
    );
  end generate;

  cnts_disabled:
  if (not RISCV_ISA_Zicntr) and (not RISCV_ISA_Zihpm) generate
    xcsr_cnt <= (others => '0');
  end generate;


  -- Register File --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_regfile_inst: entity neorv32.neorv32_cpu_regfile
  generic map (
    DWIDTH   => 32,             -- data width
    AWIDTH   => rf_awidth_c,    -- address width
    ARCH_SEL => CPU_RF_ARCH_SEL -- architecture style select
  )
  port map (
    -- global control --
    clk_i  => clk_i,    -- global clock, rising edge
    rstn_i => rstn_i,   -- global reset, low-active, async
    ctrl_i => ctrl,     -- main control bus
    -- operands --
    rd_i   => rf_wdata, -- destination operand rd
    rs1_o  => rs1,      -- source operand rs1
    rs2_o  => rs2       -- source operand rs2
  );

  -- all buses are zero unless there is an according operation --
  rf_wdata <= alu_res or lsu_rdata or csr_rdata or ctrl.pc_ret;


  -- Arithmetic/Logic Unit (ALU) and ALU Co-Processors --------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_alu_inst: entity neorv32.neorv32_cpu_alu
  generic map (
    -- RISC-V CPU Extensions --
    RISCV_ISA_M      => RISCV_ISA_M,      -- mul/div extension
    RISCV_ISA_Zba    => RISCV_ISA_Zba,    -- address-generation instruction
    RISCV_ISA_Zbb    => RISCV_ISA_Zbb,    -- basic bit-manipulation instruction
    RISCV_ISA_Zbkb   => RISCV_ISA_Zbkb,   -- bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc   => RISCV_ISA_Zbkc,   -- carry-less multiplication instructions
    RISCV_ISA_Zbkx   => RISCV_ISA_Zbkx,   -- cryptography crossbar permutation extension
    RISCV_ISA_Zbs    => RISCV_ISA_Zbs,    -- single-bit instructions
    RISCV_ISA_Zfinx  => RISCV_ISA_Zfinx,  -- 32-bit floating-point extension
    RISCV_ISA_Zibi   => RISCV_ISA_Zibi,   -- branch with immediate
    RISCV_ISA_Zicond => RISCV_ISA_Zicond, -- integer conditional operations
    RISCV_ISA_Zknd   => RISCV_ISA_Zknd,   -- cryptography NIST AES decryption extension
    RISCV_ISA_Zkne   => RISCV_ISA_Zkne,   -- cryptography NIST AES encryption extension
    RISCV_ISA_Zknh   => RISCV_ISA_Zknh,   -- cryptography NIST hash extension
    RISCV_ISA_Zksed  => RISCV_ISA_Zksed,  -- ShangMi block cipher extension
    RISCV_ISA_Zksh   => RISCV_ISA_Zksh,   -- ShangMi hash extension
    RISCV_ISA_Zmmul  => RISCV_ISA_Zmmul,  -- multiply-only M sub-extension
    RISCV_ISA_Zxcfu  => RISCV_ISA_Zxcfu,  -- custom (instr.) functions unit
    -- Tuning Options --
    FAST_MUL_EN      => CPU_FAST_MUL_EN,  -- use DSPs for M extension's multiplier
    FAST_SHIFT_EN    => CPU_FAST_SHIFT_EN -- use barrel shifter for shift operations
  )
  port map (
    -- global control --
    clk_i  => clk_i,      -- global clock, rising edge
    rstn_i => rstn_i,     -- global reset, low-active, async
    ctrl_i => ctrl,       -- main control bus
    -- data input --
    rs1_i  => rs1,        -- rf source 1
    rs2_i  => rs2,        -- rf source 2
    -- data output --
    cmp_o  => alu_cmp,    -- comparator status
    res_o  => alu_res,    -- ALU result
    add_o  => alu_add,    -- address computation result
    csr_o  => xcsr_alu,   -- CSR read data
    -- status --
    done_o => alu_cp_done -- iterative processing units done?
  );


  -- Load/Store Unit (LSU) ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_lsu_inst: entity neorv32.neorv32_cpu_lsu
  generic map (
    HART_ID => HART_ID -- hardware thread ID
  )
  port map (
    -- global control --
    clk_i       => clk_i,      -- global clock, rising edge
    rstn_i      => rstn_i,     -- global reset, low-active, async
    ctrl_i      => ctrl,       -- main control bus
    -- cpu data access interface --
    addr_i      => alu_add,    -- access address
    wdata_i     => rs2,        -- write data
    rdata_o     => lsu_rdata,  -- read data
    mar_o       => lsu_mar,    -- memory address register
    wait_o      => lsu_wait,   -- wait for access to complete
    err_o       => lsu_err,    -- alignment/access errors
    pmp_fault_i => rw_pmp_err, -- PMP read/write access fault
    -- data bus --
    dbus_req_o  => dbus_req,   -- request
    dbus_rsp_i  => dbus_rsp_i  -- response
  );

  -- memory request --
  dbus_req_o <= dbus_req;


  -- Physical Memory Protection (PMP) -------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  pmp_enabled:
  if RISCV_ISA_Smpmp generate
    neorv32_cpu_pmp_inst: entity neorv32.neorv32_cpu_pmp
    generic map (
      NUM_REGIONS => PMP_NUM_REGIONS,     -- number of regions (0..16)
      GRANULARITY => PMP_MIN_GRANULARITY, -- minimal region granularity in bytes, has to be a power of 2, min 4 bytes
      TOR_EN      => PMP_TOR_MODE_EN,     -- enable TOR mode
      NAP_EN      => PMP_NAP_MODE_EN      -- enable NAPOT/NA4 modes
    )
    port map (
      -- global control --
      clk_i    => clk_i,         -- global clock, rising edge
      rstn_i   => rstn_i,        -- global reset, low-active, async
      ctrl_i   => ctrl,          -- main control bus
      csr_o    => xcsr_pmp,      -- CSR read data
      -- instruction access check --
      i_addr_i => if_pmp_addr,   -- access address
      i_priv_i => if_pmp_priv,   -- access privilege
      i_err_o  => if_pmp_err,    -- PMP fault
      -- data access check --
      d_addr_i => alu_add,       -- access address
      d_priv_i => ctrl.lsu_priv, -- access privilege
      d_err_o  => rw_pmp_err     -- PMP fault
    );
  end generate;

  pmp_disabled:
  if not RISCV_ISA_Smpmp generate
    xcsr_pmp   <= (others => '0');
    if_pmp_err <= '0';
    rw_pmp_err <= '0';
  end generate;


  -- Trace Generator ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trace_enabled:
  if CPU_TRACE_EN generate
    neorv32_cpu_trace_inst: entity neorv32.neorv32_cpu_trace
    port map (
      -- global control --
      clk_i       => clk_i,         -- global clock, rising edge
      rstn_i      => rstn_i,        -- global reset, low-active, async
      ctrl_i      => ctrl,          -- main control bus
      -- operands --
      rs1_rdata_i => rs1,           -- rs1 read data
      rs2_rdata_i => rs2,           -- rs2 read data
      rd_wdata_i  => rf_wdata,      -- rd write data
      mem_ben_i   => dbus_req.ben,  -- memory byte-enable
      mem_addr_i  => dbus_req.addr, -- memory address
      mem_wdata_i => dbus_req.data, -- memory write data
      -- trace port --
      trace_o     => trace_o        -- execution trace port
    );
  end generate;

  trace_disabled:
  if not CPU_TRACE_EN generate
    trace_o <= trace_port_terminate_c;
  end generate;


end neorv32_cpu_rtl;
