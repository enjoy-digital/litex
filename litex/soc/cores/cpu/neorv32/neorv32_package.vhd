-- ================================================================================ --
-- NEORV32 - Main VHDL Package File                                                 --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

package neorv32_package is

-- **********************************************************************************************************
-- Architecture Configuration and Constants
-- **********************************************************************************************************

  -- Architecture Configuration -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- max response time for processor-internal bus transactions --
  -- cycles after which an unacknowledged internal bus access will timeout raising a bus fault exception
  constant bus_timeout_c : natural := 16; -- has to be a power of two

  -- instruction monitor: raise exception if multi-cycle operation times out --
  constant monitor_mc_tmo_c : natural := 9; -- = log2 of max execution cycles; default = 2^9 = 512 cycles

  -- Architecture Constants -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant hw_version_c : std_ulogic_vector(31 downto 0) := x"01110200"; -- hardware version
  constant archid_c     : natural := 19; -- official RISC-V architecture ID
  constant XLEN         : natural := 32; -- native data path width

  -- Check if we're inside the Matrix -------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant is_simulation_c : boolean := false -- seems like we're on real hardware
-- pragma translate_off
-- RTL_SYNTHESIS OFF
  or true -- this MIGHT be a simulation
-- RTL_SYNTHESIS ON
-- pragma translate_on
  ;

-- **********************************************************************************************************
-- Processor Address Space Layout
-- **********************************************************************************************************

  -- Main Address Regions (base address must be aligned to the region's size) ---
  constant mem_imem_base_c : std_ulogic_vector(31 downto 0) := x"00000000"; -- IMEM size via top generic
  constant mem_dmem_base_c : std_ulogic_vector(31 downto 0) := x"80000000"; -- DMEM size via top generic
  constant mem_io_base_c   : std_ulogic_vector(31 downto 0) := x"ffe00000";
  constant mem_io_size_c   : natural := 32*64*1024; -- 32 * iodev_size_c

  -- Start of uncached memory access (256MB page / 4 MSBs only) --
  constant mem_uncached_begin_c  : std_ulogic_vector(31 downto 0) := x"f0000000";

  -- IO Address Map (base address must be aligned to the region's size) --
  constant iodev_size_c      : natural := 64*1024; -- size of a single IO device (bytes)
  constant base_io_bootrom_c : std_ulogic_vector(31 downto 0) := x"ffe00000";
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe10000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe20000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe30000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe40000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe50000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe60000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe70000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe80000"; -- reserved
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffe90000"; -- reserved
  constant base_io_twd_c     : std_ulogic_vector(31 downto 0) := x"ffea0000";
  constant base_io_cfs_c     : std_ulogic_vector(31 downto 0) := x"ffeb0000";
  constant base_io_slink_c   : std_ulogic_vector(31 downto 0) := x"ffec0000";
  constant base_io_dma_c     : std_ulogic_vector(31 downto 0) := x"ffed0000";
  constant base_io_crc_c     : std_ulogic_vector(31 downto 0) := x"ffee0000";
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"ffef0000"; -- reserved
  constant base_io_pwm_c     : std_ulogic_vector(31 downto 0) := x"fff00000";
  constant base_io_gptmr_c   : std_ulogic_vector(31 downto 0) := x"fff10000";
  constant base_io_onewire_c : std_ulogic_vector(31 downto 0) := x"fff20000";
--constant base_io_???_c     : std_ulogic_vector(31 downto 0) := x"fff30000"; -- reserved
  constant base_io_clint_c   : std_ulogic_vector(31 downto 0) := x"fff40000";
  constant base_io_uart0_c   : std_ulogic_vector(31 downto 0) := x"fff50000";
  constant base_io_uart1_c   : std_ulogic_vector(31 downto 0) := x"fff60000";
  constant base_io_sdi_c     : std_ulogic_vector(31 downto 0) := x"fff70000";
  constant base_io_spi_c     : std_ulogic_vector(31 downto 0) := x"fff80000";
  constant base_io_twi_c     : std_ulogic_vector(31 downto 0) := x"fff90000";
  constant base_io_trng_c    : std_ulogic_vector(31 downto 0) := x"fffa0000";
  constant base_io_wdt_c     : std_ulogic_vector(31 downto 0) := x"fffb0000";
  constant base_io_gpio_c    : std_ulogic_vector(31 downto 0) := x"fffc0000";
  constant base_io_neoled_c  : std_ulogic_vector(31 downto 0) := x"fffd0000";
  constant base_io_sysinfo_c : std_ulogic_vector(31 downto 0) := x"fffe0000";
  constant base_io_ocd_c     : std_ulogic_vector(31 downto 0) := x"ffff0000";

  -- On-Chip Debugger - Debug Module Entry Points (Code ROM) --
  constant dm_exc_entry_c  : std_ulogic_vector(31 downto 0) := x"fffffe00"; -- = base_io_ocd_c + code_rom_base + 0
  constant dm_park_entry_c : std_ulogic_vector(31 downto 0) := x"fffffe10"; -- = base_io_ocd_c + code_rom_base + 16

-- **********************************************************************************************************
-- SoC Definitions
-- **********************************************************************************************************

  -- SoC Clock Select -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant clk_div2_c    : natural := 0;
  constant clk_div4_c    : natural := 1;
  constant clk_div8_c    : natural := 2;
  constant clk_div64_c   : natural := 3;
  constant clk_div128_c  : natural := 4;
  constant clk_div1024_c : natural := 5;
  constant clk_div2048_c : natural := 6;
  constant clk_div4096_c : natural := 7;

  -- Internal Memory Types ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  type mem32_t is array (natural range <>) of std_ulogic_vector(31 downto 0); -- memory with 32-bit entries
  type mem8_t  is array (natural range <>) of std_ulogic_vector(7 downto 0);  -- memory with 8-bit entries

  -- Internal Bus Interface -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- bus request --
  type bus_req_t is record
    addr  : std_ulogic_vector(31 downto 0); -- access address
    data  : std_ulogic_vector(31 downto 0); -- write data
    ben   : std_ulogic_vector(3 downto 0); -- byte enable
    stb   : std_ulogic; -- request strobe, single-shot
    rw    : std_ulogic; -- 0 = read, 1 = write
    src   : std_ulogic; -- 0 = data access, 1 = instruction fetch
    priv  : std_ulogic; -- set if privileged (machine-mode) access
    debug : std_ulogic; -- set if debug mode access
    amo   : std_ulogic; -- set if atomic memory operation
    amoop : std_ulogic_vector(3 downto 0); -- type of atomic memory operation
    -- out-of-band signals --
    fence : std_ulogic; -- set if fence(.i) operation, single-shot
  end record;

  -- bus response --
  type bus_rsp_t is record
    data : std_ulogic_vector(31 downto 0); -- read data, valid if ack = 1
    ack  : std_ulogic; -- set if access acknowledge, single-shot
    err  : std_ulogic; -- set if access error, single-shot, has priority over ack
  end record;

  -- source (request) termination --
  constant req_terminate_c : bus_req_t := (
    addr  => (others => '0'),
    data  => (others => '0'),
    ben   => (others => '0'),
    stb   => '0',
    rw    => '0',
    src   => '0',
    priv  => '0',
    debug => '0',
    amo   => '0',
    amoop => (others => '0'),
    fence => '0'
  );

  -- endpoint (response) termination --
  constant rsp_terminate_c : bus_rsp_t := (
    data => (others => '0'),
    ack  => '0',
    err  => '0'
  );

  -- Debug Module Interface -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- request --
  type dmi_req_t is record
    addr : std_ulogic_vector(6 downto 0);
    op   : std_ulogic_vector(1 downto 0);
    data : std_ulogic_vector(31 downto 0);
  end record;

  -- request operation --
  constant dmi_req_nop_c : std_ulogic_vector(1 downto 0) := "00"; -- no operation
  constant dmi_req_rd_c  : std_ulogic_vector(1 downto 0) := "01"; -- read access
  constant dmi_req_wr_c  : std_ulogic_vector(1 downto 0) := "10"; -- write access

  -- response --
  type dmi_rsp_t is record
    data : std_ulogic_vector(31 downto 0);
    ack  : std_ulogic;
  end record;

  -- External Bus Interface (XBUS / Wishbone) -----------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- xbus request --
  type xbus_req_t is record
    addr : std_ulogic_vector(31 downto 0); -- access address
    data : std_ulogic_vector(31 downto 0); -- write data
    tag  : std_ulogic_vector(2 downto 0); -- access tag
    we   : std_ulogic; -- read/write
    sel  : std_ulogic_vector(3 downto 0); -- byte enable
    stb  : std_ulogic; -- strobe
    cyc  : std_ulogic; -- valid cycle
  end record;

  -- source (request) termination --
  constant xbus_req_terminate_c : xbus_req_t := (
    addr => (others => '0'),
    data => (others => '0'),
    tag  => (others => '0'),
    we   => '0',
    sel  => (others => '0'),
    stb  => '0',
    cyc  => '0'
  );

  -- xbus response --
  type xbus_rsp_t is record
    data : std_ulogic_vector(31 downto 0); -- read data, valid if ack=1
    ack  : std_ulogic; -- access acknowledge
    err  : std_ulogic; -- access error
  end record;

  -- endpoint (response) termination --
  constant xbus_rsp_terminate_c : xbus_rsp_t := (
    data => (others => '0'),
    ack  => '0',
    err  => '0'
  );

  -- Inter-Core Communication (ICC) Link ----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  type icc_t is record
    rdy : std_ulogic; -- data available
    ack : std_ulogic; -- read-enable
    dat : std_ulogic_vector(31 downto 0); -- data word
  end record;

  -- endpoint termination --
  constant icc_terminate_c : icc_t := (
    rdy => '0',
    ack => '0',
    dat => (others => '0')
  );

-- **********************************************************************************************************
-- RISC-V ISA Definitions
-- **********************************************************************************************************

  -- RISC-V 32-Bit Instruction Word Layout --------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant instr_opcode_lsb_c  : natural :=  0; -- opcode bit 0
  constant instr_opcode_msb_c  : natural :=  6; -- opcode bit 6
  constant instr_rd_lsb_c      : natural :=  7; -- destination register address bit 0
  constant instr_rd_msb_c      : natural := 11; -- destination register address bit 4
  constant instr_funct3_lsb_c  : natural := 12; -- funct3 bit 0
  constant instr_funct3_msb_c  : natural := 14; -- funct3 bit 2
  constant instr_rs1_lsb_c     : natural := 15; -- source register 1 address bit 0
  constant instr_rs1_msb_c     : natural := 19; -- source register 1 address bit 4
  constant instr_rs2_lsb_c     : natural := 20; -- source register 2 address bit 0
  constant instr_rs2_msb_c     : natural := 24; -- source register 2 address bit 4
  constant instr_funct7_lsb_c  : natural := 25; -- funct7 bit 0
  constant instr_funct7_msb_c  : natural := 31; -- funct7 bit 6
  constant instr_funct12_lsb_c : natural := 20; -- funct12 bit 0
  constant instr_funct12_msb_c : natural := 31; -- funct12 bit 11
  constant instr_imm12_lsb_c   : natural := 20; -- immediate12 bit 0
  constant instr_imm12_msb_c   : natural := 31; -- immediate12 bit 11
  constant instr_imm20_lsb_c   : natural := 12; -- immediate20 bit 0
  constant instr_imm20_msb_c   : natural := 31; -- immediate20 bit 21
  constant instr_funct5_lsb_c  : natural := 27; -- funct5 select bit 0
  constant instr_funct5_msb_c  : natural := 31; -- funct5 select bit 4

  -- RISC-V Opcodes -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- alu --
  constant opcode_alui_c   : std_ulogic_vector(6 downto 0) := "0010011"; -- ALU operation with immediate
  constant opcode_alu_c    : std_ulogic_vector(6 downto 0) := "0110011"; -- ALU operation
  constant opcode_lui_c    : std_ulogic_vector(6 downto 0) := "0110111"; -- load upper immediate
  constant opcode_auipc_c  : std_ulogic_vector(6 downto 0) := "0010111"; -- add upper immediate to PC
  -- control flow --
  constant opcode_jal_c    : std_ulogic_vector(6 downto 0) := "1101111"; -- jump and link
  constant opcode_jalr_c   : std_ulogic_vector(6 downto 0) := "1100111"; -- jump and link with register
  constant opcode_branch_c : std_ulogic_vector(6 downto 0) := "1100011"; -- branch
  -- memory access --
  constant opcode_load_c   : std_ulogic_vector(6 downto 0) := "0000011"; -- load
  constant opcode_store_c  : std_ulogic_vector(6 downto 0) := "0100011"; -- store
  constant opcode_amo_c    : std_ulogic_vector(6 downto 0) := "0101111"; -- atomic memory access
  constant opcode_fence_c  : std_ulogic_vector(6 downto 0) := "0001111"; -- fence / fence.i
  -- system/csr --
  constant opcode_system_c : std_ulogic_vector(6 downto 0) := "1110011"; -- system/csr access
  -- floating point operations --
  constant opcode_fop_c    : std_ulogic_vector(6 downto 0) := "1010011"; -- dual/single operand instruction
  -- official custom RISC-V opcodes - free for custom instructions --
  constant opcode_cust0_c  : std_ulogic_vector(6 downto 0) := "0001011"; -- custom-0 (NEORV32 CFU)
  constant opcode_cust1_c  : std_ulogic_vector(6 downto 0) := "0101011"; -- custom-1 (NEORV32 CFU)
  constant opcode_cust2_c  : std_ulogic_vector(6 downto 0) := "1011011"; -- custom-2 (reserved)
  constant opcode_cust3_c  : std_ulogic_vector(6 downto 0) := "1111011"; -- custom-3 (reserved)

  -- RISC-V Funct3 --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- control flow --
  constant funct3_beq_c    : std_ulogic_vector(2 downto 0) := "000"; -- branch if equal
  constant funct3_bne_c    : std_ulogic_vector(2 downto 0) := "001"; -- branch if not equal
  constant funct3_blt_c    : std_ulogic_vector(2 downto 0) := "100"; -- branch if less than
  constant funct3_bge_c    : std_ulogic_vector(2 downto 0) := "101"; -- branch if greater than or equal
  constant funct3_bltu_c   : std_ulogic_vector(2 downto 0) := "110"; -- branch if less than (unsigned)
  constant funct3_bgeu_c   : std_ulogic_vector(2 downto 0) := "111"; -- branch if greater than or equal (unsigned)
  -- memory access --
  constant funct3_lb_c     : std_ulogic_vector(2 downto 0) := "000"; -- load byte (signed)
  constant funct3_lh_c     : std_ulogic_vector(2 downto 0) := "001"; -- load half word (signed)
  constant funct3_lw_c     : std_ulogic_vector(2 downto 0) := "010"; -- load word (signed)
  constant funct3_lbu_c    : std_ulogic_vector(2 downto 0) := "100"; -- load byte (unsigned)
  constant funct3_lhu_c    : std_ulogic_vector(2 downto 0) := "101"; -- load half word (unsigned)
  constant funct3_lwu_c    : std_ulogic_vector(2 downto 0) := "110"; -- load word (unsigned)
  constant funct3_sb_c     : std_ulogic_vector(2 downto 0) := "000"; -- store byte
  constant funct3_sh_c     : std_ulogic_vector(2 downto 0) := "001"; -- store half word
  constant funct3_sw_c     : std_ulogic_vector(2 downto 0) := "010"; -- store word
  -- alu --
  constant funct3_sadd_c   : std_ulogic_vector(2 downto 0) := "000"; -- sub/add
  constant funct3_sll_c    : std_ulogic_vector(2 downto 0) := "001"; -- shift logical left
  constant funct3_slt_c    : std_ulogic_vector(2 downto 0) := "010"; -- set on less
  constant funct3_sltu_c   : std_ulogic_vector(2 downto 0) := "011"; -- set on less unsigned
  constant funct3_xor_c    : std_ulogic_vector(2 downto 0) := "100"; -- logical exclusive-or
  constant funct3_sr_c     : std_ulogic_vector(2 downto 0) := "101"; -- shift right
  constant funct3_or_c     : std_ulogic_vector(2 downto 0) := "110"; -- logical or
  constant funct3_and_c    : std_ulogic_vector(2 downto 0) := "111"; -- logical and
  -- system/csr --
  constant funct3_env_c    : std_ulogic_vector(2 downto 0) := "000"; -- ecall, ebreak, mret, wfi, ...
  constant funct3_csrrw_c  : std_ulogic_vector(2 downto 0) := "001"; -- csr r/w
  constant funct3_csrrs_c  : std_ulogic_vector(2 downto 0) := "010"; -- csr read & set
  constant funct3_csrrc_c  : std_ulogic_vector(2 downto 0) := "011"; -- csr read & clear
  constant funct3_csril_c  : std_ulogic_vector(2 downto 0) := "100"; -- undefined/illegal csr command
  constant funct3_csrrwi_c : std_ulogic_vector(2 downto 0) := "101"; -- csr r/w immediate
  constant funct3_csrrsi_c : std_ulogic_vector(2 downto 0) := "110"; -- csr read & set immediate
  constant funct3_csrrci_c : std_ulogic_vector(2 downto 0) := "111"; -- csr read & clear immediate
  -- fence --
  constant funct3_fence_c  : std_ulogic_vector(2 downto 0) := "000"; -- fence - order IO/memory access
  constant funct3_fencei_c : std_ulogic_vector(2 downto 0) := "001"; -- fence.i - instruction stream sync

  -- RISC-V Funct12 - SYSTEM ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant funct12_ecall_c  : std_ulogic_vector(11 downto 0) := x"000";
  constant funct12_ebreak_c : std_ulogic_vector(11 downto 0) := x"001";
  constant funct12_wfi_c    : std_ulogic_vector(11 downto 0) := x"105";
  constant funct12_mret_c   : std_ulogic_vector(11 downto 0) := x"302";
  constant funct12_dret_c   : std_ulogic_vector(11 downto 0) := x"7b2";

  -- RISC-V Floating-Point Stuff ------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- number class flags --
  constant fp_class_neg_inf_c    : natural := 0; -- negative infinity
  constant fp_class_neg_norm_c   : natural := 1; -- negative normal number
  constant fp_class_neg_denorm_c : natural := 2; -- negative subnormal number
  constant fp_class_neg_zero_c   : natural := 3; -- negative zero
  constant fp_class_pos_zero_c   : natural := 4; -- positive zero
  constant fp_class_pos_denorm_c : natural := 5; -- positive subnormal number
  constant fp_class_pos_norm_c   : natural := 6; -- positive normal number
  constant fp_class_pos_inf_c    : natural := 7; -- positive infinity
  constant fp_class_snan_c       : natural := 8; -- signaling NaN (sNaN)
  constant fp_class_qnan_c       : natural := 9; -- quiet NaN (qNaN)

  -- exception flags --
  constant fp_exc_nx_c : natural := 0; -- inexact
  constant fp_exc_uf_c : natural := 1; -- underflow
  constant fp_exc_of_c : natural := 2; -- overflow
  constant fp_exc_dz_c : natural := 3; -- division by zero
  constant fp_exc_nv_c : natural := 4; -- invalid operation

  -- special values (single-precision) --
  constant fp_single_qnan_c     : std_ulogic_vector(31 downto 0) := x"7fc00000"; -- quiet NaN
  constant fp_single_snan_c     : std_ulogic_vector(31 downto 0) := x"7fa00000"; -- signaling NaN
  constant fp_single_pos_max_c  : std_ulogic_vector(31 downto 0) := x"7f7FFFFF"; -- positive max
  constant fp_single_neg_max_c  : std_ulogic_vector(31 downto 0) := x"Ff7FFFFF"; -- negative max
  constant fp_single_pos_inf_c  : std_ulogic_vector(31 downto 0) := x"7f800000"; -- positive infinity
  constant fp_single_neg_inf_c  : std_ulogic_vector(31 downto 0) := x"ff800000"; -- negative infinity
  constant fp_single_pos_zero_c : std_ulogic_vector(31 downto 0) := x"00000000"; -- positive zero
  constant fp_single_neg_zero_c : std_ulogic_vector(31 downto 0) := x"80000000"; -- negative zero

  -- RISC-V CSRs ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- user floating-point CSRs --
  constant csr_fflags_c         : std_ulogic_vector(11 downto 0) := x"001";
  constant csr_frm_c            : std_ulogic_vector(11 downto 0) := x"002";
  constant csr_fcsr_c           : std_ulogic_vector(11 downto 0) := x"003";
  -- machine trap setup --
  constant csr_mstatus_c        : std_ulogic_vector(11 downto 0) := x"300";
  constant csr_misa_c           : std_ulogic_vector(11 downto 0) := x"301";
  constant csr_mie_c            : std_ulogic_vector(11 downto 0) := x"304";
  constant csr_mtvec_c          : std_ulogic_vector(11 downto 0) := x"305";
  constant csr_mcounteren_c     : std_ulogic_vector(11 downto 0) := x"306";
  constant csr_mstatush_c       : std_ulogic_vector(11 downto 0) := x"310";
  -- machine configuration --
  constant csr_menvcfg_c        : std_ulogic_vector(11 downto 0) := x"30a";
  constant csr_menvcfgh_c       : std_ulogic_vector(11 downto 0) := x"31a";
  -- machine counter setup --
  constant csr_mcountinhibit_c  : std_ulogic_vector(11 downto 0) := x"320";
  constant csr_mhpmevent3_c     : std_ulogic_vector(11 downto 0) := x"323";
  constant csr_mhpmevent4_c     : std_ulogic_vector(11 downto 0) := x"324";
  constant csr_mhpmevent5_c     : std_ulogic_vector(11 downto 0) := x"325";
  constant csr_mhpmevent6_c     : std_ulogic_vector(11 downto 0) := x"326";
  constant csr_mhpmevent7_c     : std_ulogic_vector(11 downto 0) := x"327";
  constant csr_mhpmevent8_c     : std_ulogic_vector(11 downto 0) := x"328";
  constant csr_mhpmevent9_c     : std_ulogic_vector(11 downto 0) := x"329";
  constant csr_mhpmevent10_c    : std_ulogic_vector(11 downto 0) := x"32a";
  constant csr_mhpmevent11_c    : std_ulogic_vector(11 downto 0) := x"32b";
  constant csr_mhpmevent12_c    : std_ulogic_vector(11 downto 0) := x"32c";
  constant csr_mhpmevent13_c    : std_ulogic_vector(11 downto 0) := x"32d";
  constant csr_mhpmevent14_c    : std_ulogic_vector(11 downto 0) := x"32e";
  constant csr_mhpmevent15_c    : std_ulogic_vector(11 downto 0) := x"32f";
  -- machine trap handling --
  constant csr_mscratch_c       : std_ulogic_vector(11 downto 0) := x"340";
  constant csr_mepc_c           : std_ulogic_vector(11 downto 0) := x"341";
  constant csr_mcause_c         : std_ulogic_vector(11 downto 0) := x"342";
  constant csr_mtval_c          : std_ulogic_vector(11 downto 0) := x"343";
  constant csr_mip_c            : std_ulogic_vector(11 downto 0) := x"344";
  constant csr_mtinst_c         : std_ulogic_vector(11 downto 0) := x"34a";
  -- physical memory protection - configuration --
  constant csr_pmpcfg0_c        : std_ulogic_vector(11 downto 0) := x"3a0";
  constant csr_pmpcfg1_c        : std_ulogic_vector(11 downto 0) := x"3a1";
  constant csr_pmpcfg2_c        : std_ulogic_vector(11 downto 0) := x"3a2";
  constant csr_pmpcfg3_c        : std_ulogic_vector(11 downto 0) := x"3a3";
  -- physical memory protection - address --
  constant csr_pmpaddr0_c       : std_ulogic_vector(11 downto 0) := x"3b0";
  constant csr_pmpaddr1_c       : std_ulogic_vector(11 downto 0) := x"3b1";
  constant csr_pmpaddr2_c       : std_ulogic_vector(11 downto 0) := x"3b2";
  constant csr_pmpaddr3_c       : std_ulogic_vector(11 downto 0) := x"3b3";
  constant csr_pmpaddr4_c       : std_ulogic_vector(11 downto 0) := x"3b4";
  constant csr_pmpaddr5_c       : std_ulogic_vector(11 downto 0) := x"3b5";
  constant csr_pmpaddr6_c       : std_ulogic_vector(11 downto 0) := x"3b6";
  constant csr_pmpaddr7_c       : std_ulogic_vector(11 downto 0) := x"3b7";
  constant csr_pmpaddr8_c       : std_ulogic_vector(11 downto 0) := x"3b8";
  constant csr_pmpaddr9_c       : std_ulogic_vector(11 downto 0) := x"3b9";
  constant csr_pmpaddr10_c      : std_ulogic_vector(11 downto 0) := x"3ba";
  constant csr_pmpaddr11_c      : std_ulogic_vector(11 downto 0) := x"3bb";
  constant csr_pmpaddr12_c      : std_ulogic_vector(11 downto 0) := x"3bc";
  constant csr_pmpaddr13_c      : std_ulogic_vector(11 downto 0) := x"3bd";
  constant csr_pmpaddr14_c      : std_ulogic_vector(11 downto 0) := x"3be";
  constant csr_pmpaddr15_c      : std_ulogic_vector(11 downto 0) := x"3bf";
  -- trigger module registers --
  constant csr_tselect_c        : std_ulogic_vector(11 downto 0) := x"7a0";
  constant csr_tdata1_c         : std_ulogic_vector(11 downto 0) := x"7a1";
  constant csr_tdata2_c         : std_ulogic_vector(11 downto 0) := x"7a2";
  constant csr_tinfo_c          : std_ulogic_vector(11 downto 0) := x"7a4";
  -- debug registers --
  constant csr_dcsr_c           : std_ulogic_vector(11 downto 0) := x"7b0";
  constant csr_dpc_c            : std_ulogic_vector(11 downto 0) := x"7b1";
  constant csr_dscratch0_c      : std_ulogic_vector(11 downto 0) := x"7b2";
  -- NEORV32-specific read/write user registers --
  constant csr_cfureg0_c        : std_ulogic_vector(11 downto 0) := x"800";
  constant csr_cfureg1_c        : std_ulogic_vector(11 downto 0) := x"801";
  constant csr_cfureg2_c        : std_ulogic_vector(11 downto 0) := x"802";
  constant csr_cfureg3_c        : std_ulogic_vector(11 downto 0) := x"803";
  -- machine counters/timers --
  constant csr_mcycle_c         : std_ulogic_vector(11 downto 0) := x"b00";
  constant csr_mtime_c          : std_ulogic_vector(11 downto 0) := x"b01";
  constant csr_minstret_c       : std_ulogic_vector(11 downto 0) := x"b02";
  constant csr_mhpmcounter3_c   : std_ulogic_vector(11 downto 0) := x"b03";
  constant csr_mhpmcounter4_c   : std_ulogic_vector(11 downto 0) := x"b04";
  constant csr_mhpmcounter5_c   : std_ulogic_vector(11 downto 0) := x"b05";
  constant csr_mhpmcounter6_c   : std_ulogic_vector(11 downto 0) := x"b06";
  constant csr_mhpmcounter7_c   : std_ulogic_vector(11 downto 0) := x"b07";
  constant csr_mhpmcounter8_c   : std_ulogic_vector(11 downto 0) := x"b08";
  constant csr_mhpmcounter9_c   : std_ulogic_vector(11 downto 0) := x"b09";
  constant csr_mhpmcounter10_c  : std_ulogic_vector(11 downto 0) := x"b0a";
  constant csr_mhpmcounter11_c  : std_ulogic_vector(11 downto 0) := x"b0b";
  constant csr_mhpmcounter12_c  : std_ulogic_vector(11 downto 0) := x"b0c";
  constant csr_mhpmcounter13_c  : std_ulogic_vector(11 downto 0) := x"b0d";
  constant csr_mhpmcounter14_c  : std_ulogic_vector(11 downto 0) := x"b0e";
  constant csr_mhpmcounter15_c  : std_ulogic_vector(11 downto 0) := x"b0f";
  constant csr_mcycleh_c        : std_ulogic_vector(11 downto 0) := x"b80";
  constant csr_mtimeh_c         : std_ulogic_vector(11 downto 0) := x"b81";
  constant csr_minstreth_c      : std_ulogic_vector(11 downto 0) := x"b82";
  constant csr_mhpmcounter3h_c  : std_ulogic_vector(11 downto 0) := x"b83";
  constant csr_mhpmcounter4h_c  : std_ulogic_vector(11 downto 0) := x"b84";
  constant csr_mhpmcounter5h_c  : std_ulogic_vector(11 downto 0) := x"b85";
  constant csr_mhpmcounter6h_c  : std_ulogic_vector(11 downto 0) := x"b86";
  constant csr_mhpmcounter7h_c  : std_ulogic_vector(11 downto 0) := x"b87";
  constant csr_mhpmcounter8h_c  : std_ulogic_vector(11 downto 0) := x"b88";
  constant csr_mhpmcounter9h_c  : std_ulogic_vector(11 downto 0) := x"b89";
  constant csr_mhpmcounter10h_c : std_ulogic_vector(11 downto 0) := x"b8a";
  constant csr_mhpmcounter11h_c : std_ulogic_vector(11 downto 0) := x"b8b";
  constant csr_mhpmcounter12h_c : std_ulogic_vector(11 downto 0) := x"b8c";
  constant csr_mhpmcounter13h_c : std_ulogic_vector(11 downto 0) := x"b8d";
  constant csr_mhpmcounter14h_c : std_ulogic_vector(11 downto 0) := x"b8e";
  constant csr_mhpmcounter15h_c : std_ulogic_vector(11 downto 0) := x"b8f";
  -- NEORV32-specific read/write machine registers --
  constant csr_mxiccsreg_c      : std_ulogic_vector(11 downto 0) := x"bc0";
  constant csr_mxiccdata_c      : std_ulogic_vector(11 downto 0) := x"bc1";
  -- user counters/timers --
  constant csr_cycle_c          : std_ulogic_vector(11 downto 0) := x"c00";
  constant csr_time_c           : std_ulogic_vector(11 downto 0) := x"c01";
  constant csr_instret_c        : std_ulogic_vector(11 downto 0) := x"c02";
  constant csr_hpmcounter3_c    : std_ulogic_vector(11 downto 0) := x"c03";
  constant csr_hpmcounter4_c    : std_ulogic_vector(11 downto 0) := x"c04";
  constant csr_hpmcounter5_c    : std_ulogic_vector(11 downto 0) := x"c05";
  constant csr_hpmcounter6_c    : std_ulogic_vector(11 downto 0) := x"c06";
  constant csr_hpmcounter7_c    : std_ulogic_vector(11 downto 0) := x"c07";
  constant csr_hpmcounter8_c    : std_ulogic_vector(11 downto 0) := x"c08";
  constant csr_hpmcounter9_c    : std_ulogic_vector(11 downto 0) := x"c09";
  constant csr_hpmcounter10_c   : std_ulogic_vector(11 downto 0) := x"c0a";
  constant csr_hpmcounter11_c   : std_ulogic_vector(11 downto 0) := x"c0b";
  constant csr_hpmcounter12_c   : std_ulogic_vector(11 downto 0) := x"c0c";
  constant csr_hpmcounter13_c   : std_ulogic_vector(11 downto 0) := x"c0d";
  constant csr_hpmcounter14_c   : std_ulogic_vector(11 downto 0) := x"c0e";
  constant csr_hpmcounter15_c   : std_ulogic_vector(11 downto 0) := x"c0f";
  constant csr_cycleh_c         : std_ulogic_vector(11 downto 0) := x"c80";
  constant csr_timeh_c          : std_ulogic_vector(11 downto 0) := x"c81";
  constant csr_instreth_c       : std_ulogic_vector(11 downto 0) := x"c82";
  constant csr_hpmcounter3h_c   : std_ulogic_vector(11 downto 0) := x"c83";
  constant csr_hpmcounter4h_c   : std_ulogic_vector(11 downto 0) := x"c84";
  constant csr_hpmcounter5h_c   : std_ulogic_vector(11 downto 0) := x"c85";
  constant csr_hpmcounter6h_c   : std_ulogic_vector(11 downto 0) := x"c86";
  constant csr_hpmcounter7h_c   : std_ulogic_vector(11 downto 0) := x"c87";
  constant csr_hpmcounter8h_c   : std_ulogic_vector(11 downto 0) := x"c88";
  constant csr_hpmcounter9h_c   : std_ulogic_vector(11 downto 0) := x"c89";
  constant csr_hpmcounter10h_c  : std_ulogic_vector(11 downto 0) := x"c8a";
  constant csr_hpmcounter11h_c  : std_ulogic_vector(11 downto 0) := x"c8b";
  constant csr_hpmcounter12h_c  : std_ulogic_vector(11 downto 0) := x"c8c";
  constant csr_hpmcounter13h_c  : std_ulogic_vector(11 downto 0) := x"c8d";
  constant csr_hpmcounter14h_c  : std_ulogic_vector(11 downto 0) := x"c8e";
  constant csr_hpmcounter15h_c  : std_ulogic_vector(11 downto 0) := x"c8f";
  -- machine information registers --
  constant csr_mvendorid_c      : std_ulogic_vector(11 downto 0) := x"f11";
  constant csr_marchid_c        : std_ulogic_vector(11 downto 0) := x"f12";
  constant csr_mimpid_c         : std_ulogic_vector(11 downto 0) := x"f13";
  constant csr_mhartid_c        : std_ulogic_vector(11 downto 0) := x"f14";
  constant csr_mconfigptr_c     : std_ulogic_vector(11 downto 0) := x"f15";
  -- NEORV32-specific read-only machine registers --
  constant csr_mxisa_c          : std_ulogic_vector(11 downto 0) := x"fc0";
--constant csr_mxisah_c         : std_ulogic_vector(11 downto 0) := x"fc1"; -- to be implemented...

-- **********************************************************************************************************
-- CPU Control
-- **********************************************************************************************************

  -- Main CPU Control Bus -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  type ctrl_bus_t is record
    -- instruction fetch --
    if_fence     : std_ulogic;                     -- fence.i operation
    if_reset     : std_ulogic;                     -- restart instruction fetch
    if_ack       : std_ulogic;                     -- consume data from instruction fetch
    -- program counter --
    pc_cur       : std_ulogic_vector(31 downto 0); -- address of current instruction
    pc_nxt       : std_ulogic_vector(31 downto 0); -- address of next instruction
    pc_ret       : std_ulogic_vector(31 downto 0); -- return address
    -- register file --
    rf_wb_en     : std_ulogic; -- write back enable
    rf_rs1       : std_ulogic_vector(4 downto 0);  -- source register 1 address
    rf_rs2       : std_ulogic_vector(4 downto 0);  -- source register 2 address
    rf_rd        : std_ulogic_vector(4 downto 0);  -- destination register address
    rf_zero_we   : std_ulogic;                     -- allow/force write access to x0
    -- alu --
    alu_op       : std_ulogic_vector(2 downto 0);  -- operation select
    alu_sub      : std_ulogic;                     -- addition/subtraction control
    alu_opa_mux  : std_ulogic;                     -- operand A select (0=rs1, 1=PC)
    alu_opb_mux  : std_ulogic;                     -- operand B select (0=rs2, 1=IMM)
    alu_unsigned : std_ulogic;                     -- is unsigned ALU operation
    alu_imm      : std_ulogic_vector(31 downto 0); -- immediate
    alu_cp_alu   : std_ulogic;                     -- ALU.base co-processor trigger (one-shot)
    alu_cp_cfu   : std_ulogic;                     -- CFU co-processor trigger (one-shot)
    alu_cp_fpu   : std_ulogic;                     -- FPU co-processor trigger (one-shot)
    -- load/store unit --
    lsu_req      : std_ulogic;                     -- trigger memory access request
    lsu_rw       : std_ulogic;                     -- 0: read access, 1: write access
    lsu_amo      : std_ulogic;                     -- set if atomic memory operation
    lsu_mo_we    : std_ulogic;                     -- memory address and data output register write enable
    lsu_fence    : std_ulogic;                     -- fence operation
    lsu_priv     : std_ulogic;                     -- effective privilege mode for load/store
    -- control and status registers --
    csr_we       : std_ulogic;                     -- global write-enable
    csr_re       : std_ulogic;                     -- global read-enable
    csr_addr     : std_ulogic_vector(11 downto 0); -- address
    csr_wdata    : std_ulogic_vector(31 downto 0); -- write data
    cnt_halt     : std_ulogic_vector(15 downto 0); -- counter inhibit
    cnt_event    : std_ulogic_vector(11 downto 0); -- counter increment events
    -- instruction word --
    ir_funct3    : std_ulogic_vector(2 downto 0);  -- funct3 bit field
    ir_funct12   : std_ulogic_vector(11 downto 0); -- funct12 bit field
    ir_opcode    : std_ulogic_vector(6 downto 0);  -- opcode bit field
    -- cpu status --
    cpu_priv     : std_ulogic;                     -- effective privilege mode
    cpu_sleep    : std_ulogic;                     -- set when CPU is in sleep mode
    cpu_trap     : std_ulogic;                     -- set when CPU is entering trap exec
    cpu_debug    : std_ulogic;                     -- set when CPU is in debug mode
  end record;

  -- control bus reset initializer --
  constant ctrl_bus_zero_c : ctrl_bus_t := (
    if_fence     => '0',
    if_reset     => '0',
    if_ack       => '0',
    pc_cur       => (others => '0'),
    pc_nxt       => (others => '0'),
    pc_ret       => (others => '0'),
    rf_wb_en     => '0',
    rf_rs1       => (others => '0'),
    rf_rs2       => (others => '0'),
    rf_rd        => (others => '0'),
    rf_zero_we   => '0',
    alu_op       => (others => '0'),
    alu_sub      => '0',
    alu_opa_mux  => '0',
    alu_opb_mux  => '0',
    alu_unsigned => '0',
    alu_imm      => (others => '0'),
    alu_cp_alu   => '0',
    alu_cp_cfu   => '0',
    alu_cp_fpu   => '0',
    lsu_req      => '0',
    lsu_rw       => '0',
    lsu_amo      => '0',
    lsu_mo_we    => '0',
    lsu_fence    => '0',
    lsu_priv     => '0',
    csr_we       => '0',
    csr_re       => '0',
    csr_addr     => (others => '0'),
    csr_wdata    => (others => '0'),
    cnt_halt     => (others => '0'),
    cnt_event    => (others => '0'),
    ir_funct3    => (others => '0'),
    ir_funct12   => (others => '0'),
    ir_opcode    => (others => '0'),
    cpu_priv     => '0',
    cpu_sleep    => '0',
    cpu_trap     => '0',
    cpu_debug    => '0'
  );

  -- Instruction Fetch Interface ------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  type if_bus_t is record
    valid  : std_ulogic;                     -- bus signals are valid
    instr  : std_ulogic_vector(31 downto 0); -- instruction word
    compr  : std_ulogic;                     -- instruction is decompressed
    error  : std_ulogic;                     -- instruction-fetch error
    halted : std_ulogic;                     -- instruction fetch has halted
  end record;

  -- Comparator Bus -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant cmp_equal_c : natural := 0;
  constant cmp_less_c  : natural := 1; -- for signed and unsigned comparisons

  -- ALU Function Codes ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant alu_op_zero_c : std_ulogic_vector(2 downto 0) := "000"; -- result <= 0
  constant alu_op_add_c  : std_ulogic_vector(2 downto 0) := "001"; -- result <= A + (-)B
  constant alu_op_cp_c   : std_ulogic_vector(2 downto 0) := "010"; -- result <= ALU co-processor
  constant alu_op_slt_c  : std_ulogic_vector(2 downto 0) := "011"; -- result <= A < B
  constant alu_op_movb_c : std_ulogic_vector(2 downto 0) := "100"; -- result <= B
  constant alu_op_xor_c  : std_ulogic_vector(2 downto 0) := "101"; -- result <= A xor B
  constant alu_op_or_c   : std_ulogic_vector(2 downto 0) := "110"; -- result <= A or B
  constant alu_op_and_c  : std_ulogic_vector(2 downto 0) := "111"; -- result <= A and B

  -- Register File Input Select -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant rf_mux_alu_c : std_ulogic_vector(1 downto 0) := "00"; -- register file <= alu result
  constant rf_mux_mem_c : std_ulogic_vector(1 downto 0) := "01"; -- register file <= memory read data
  constant rf_mux_csr_c : std_ulogic_vector(1 downto 0) := "10"; -- register file <= CSR read data
  constant rf_mux_ret_c : std_ulogic_vector(1 downto 0) := "11"; -- register file <= link-PC (return address)

  -- Trap ID Codes --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- MSB:   1 = interrupt, 0 = sync. exception
  -- MSB-1: 1 = entry to debug mode, 0 = normal trapping
  -- RISC-V compliant synchronous exceptions --
  constant trap_ima_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00000"; -- 0: instruction misaligned
  constant trap_iaf_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00001"; -- 1: instruction access fault
  constant trap_iil_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00010"; -- 2: illegal instruction
  constant trap_brk_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00011"; -- 3: environment breakpoint
  constant trap_lma_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00100"; -- 4: load address misaligned
  constant trap_laf_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00101"; -- 5: load access fault
  constant trap_sma_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00110"; -- 6: store address misaligned
  constant trap_saf_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "00111"; -- 7: store access fault
  constant trap_env_c      : std_ulogic_vector(6 downto 0) := "0" & "0" & "01000"; -- 8..11: environment call
  -- RISC-V compliant asynchronous exceptions (interrupts) --
  constant trap_msi_c      : std_ulogic_vector(6 downto 0) := "1" & "0" & "00011"; -- 3:  machine software interrupt
  constant trap_mti_c      : std_ulogic_vector(6 downto 0) := "1" & "0" & "00111"; -- 7:  machine timer interrupt
  constant trap_mei_c      : std_ulogic_vector(6 downto 0) := "1" & "0" & "01011"; -- 11: machine external interrupt
  -- NEORV32-specific (RISC-V custom) asynchronous exceptions (interrupts) --
  constant trap_firq0_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10000"; -- 16: fast interrupt 0
  constant trap_firq1_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10001"; -- 17: fast interrupt 1
  constant trap_firq2_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10010"; -- 18: fast interrupt 2
  constant trap_firq3_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10011"; -- 19: fast interrupt 3
  constant trap_firq4_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10100"; -- 20: fast interrupt 4
  constant trap_firq5_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10101"; -- 21: fast interrupt 5
  constant trap_firq6_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10110"; -- 22: fast interrupt 6
  constant trap_firq7_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "10111"; -- 23: fast interrupt 7
  constant trap_firq8_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "11000"; -- 24: fast interrupt 8
  constant trap_firq9_c    : std_ulogic_vector(6 downto 0) := "1" & "0" & "11001"; -- 25: fast interrupt 9
  constant trap_firq10_c   : std_ulogic_vector(6 downto 0) := "1" & "0" & "11010"; -- 26: fast interrupt 10
  constant trap_firq11_c   : std_ulogic_vector(6 downto 0) := "1" & "0" & "11011"; -- 27: fast interrupt 11
  constant trap_firq12_c   : std_ulogic_vector(6 downto 0) := "1" & "0" & "11100"; -- 28: fast interrupt 12
  constant trap_firq13_c   : std_ulogic_vector(6 downto 0) := "1" & "0" & "11101"; -- 29: fast interrupt 13
  constant trap_firq14_c   : std_ulogic_vector(6 downto 0) := "1" & "0" & "11110"; -- 30: fast interrupt 14
  constant trap_firq15_c   : std_ulogic_vector(6 downto 0) := "1" & "0" & "11111"; -- 31: fast interrupt 15
  -- entering debug mode (sync./async. exceptions) --
  constant trap_db_break_c : std_ulogic_vector(6 downto 0) := "0" & "1" & "00001"; -- 1: break instruction (sync)
  constant trap_db_trig_c  : std_ulogic_vector(6 downto 0) := "0" & "1" & "00010"; -- 2: hardware trigger (sync)
  constant trap_db_halt_c  : std_ulogic_vector(6 downto 0) := "1" & "1" & "00011"; -- 3: external halt request (async)
  constant trap_db_step_c  : std_ulogic_vector(6 downto 0) := "1" & "1" & "00100"; -- 4: single-stepping (async)

  -- Trap System ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- exception source list --
  constant exc_iaccess_c  : natural :=  0; -- instruction access fault
  constant exc_illegal_c  : natural :=  1; -- illegal instruction
  constant exc_ialign_c   : natural :=  2; -- instruction address misaligned
  constant exc_ecall_c    : natural :=  3; -- environment call
  constant exc_ebreak_c   : natural :=  4; -- breakpoint
  constant exc_salign_c   : natural :=  5; -- store address misaligned
  constant exc_lalign_c   : natural :=  6; -- load address misaligned
  constant exc_saccess_c  : natural :=  7; -- store access fault
  constant exc_laccess_c  : natural :=  8; -- load access fault
  constant exc_db_break_c : natural :=  9; -- enter debug mode via ebreak instruction
  constant exc_db_hw_c    : natural := 10; -- enter debug mode via hw trigger
  constant exc_width_c    : natural := 11; -- length of this list in bits
  -- interrupt source list --
  constant irq_msi_irq_c  : natural :=  0; -- machine software interrupt
  constant irq_mti_irq_c  : natural :=  1; -- machine timer interrupt
  constant irq_mei_irq_c  : natural :=  2; -- machine external interrupt
  constant irq_firq_0_c   : natural :=  3; -- fast interrupt channel 0
  constant irq_firq_1_c   : natural :=  4; -- fast interrupt channel 1
  constant irq_firq_2_c   : natural :=  5; -- fast interrupt channel 2
  constant irq_firq_3_c   : natural :=  6; -- fast interrupt channel 3
  constant irq_firq_4_c   : natural :=  7; -- fast interrupt channel 4
  constant irq_firq_5_c   : natural :=  8; -- fast interrupt channel 5
  constant irq_firq_6_c   : natural :=  9; -- fast interrupt channel 6
  constant irq_firq_7_c   : natural := 10; -- fast interrupt channel 7
  constant irq_firq_8_c   : natural := 11; -- fast interrupt channel 8
  constant irq_firq_9_c   : natural := 12; -- fast interrupt channel 9
  constant irq_firq_10_c  : natural := 13; -- fast interrupt channel 10
  constant irq_firq_11_c  : natural := 14; -- fast interrupt channel 11
  constant irq_firq_12_c  : natural := 15; -- fast interrupt channel 12
  constant irq_firq_13_c  : natural := 16; -- fast interrupt channel 13
  constant irq_firq_14_c  : natural := 17; -- fast interrupt channel 14
  constant irq_firq_15_c  : natural := 18; -- fast interrupt channel 15
  constant irq_db_halt_c  : natural := 19; -- enter debug mode via external halt request
  constant irq_db_step_c  : natural := 20; -- enter debug mode via single-stepping
  constant irq_width_c    : natural := 21; -- length of this list in bits

  -- Privilege Modes ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  constant priv_mode_m_c : std_ulogic := '1'; -- machine mode
  constant priv_mode_u_c : std_ulogic := '0'; -- user mode

  -- Counter Events -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- RISC-V-compliant base counter events --
  constant cnt_event_cy_c       : natural := 0;  -- active cycle
  constant cnt_event_tm_c       : natural := 1;  -- time (unused/reserved)
  constant cnt_event_ir_c       : natural := 2;  -- retired instruction
  -- NEORV32-specific HPM counter events --
  constant cnt_event_compr_c    : natural := 3;  -- executed compressed instruction
  constant cnt_event_wait_dis_c : natural := 4;  -- instruction dispatch wait cycle
  constant cnt_event_wait_alu_c : natural := 5;  -- multi-cycle ALU co-processor wait cycle
  constant cnt_event_branch_c   : natural := 6;  -- executed branch instruction
  constant cnt_event_branched_c : natural := 7;  -- control flow transfer
  constant cnt_event_load_c     : natural := 8;  -- load operation
  constant cnt_event_store_c    : natural := 9;  -- store operation
  constant cnt_event_wait_lsu_c : natural := 10; -- load-store unit memory wait cycle
  constant cnt_event_trap_c     : natural := 11; -- entered trap

-- **********************************************************************************************************
-- Helper Functions
-- **********************************************************************************************************

  function index_size_f(input : natural) return natural;
  function cond_sel_natural_f(cond : boolean; val_t : natural; val_f : natural) return natural;
  function cond_sel_suv_f(cond : boolean; val_t : std_ulogic_vector; val_f : std_ulogic_vector) return std_ulogic_vector;
  function cond_sel_string_f(cond : boolean; val_t : string; val_f : string) return string;
  function max_natural_f(a : natural; b : natural) return natural;
  function min_natural_f(a : natural; b : natural) return natural;
  function bool_to_ulogic_f(cond : boolean) return std_ulogic;
  function or_reduce_f(input : std_ulogic_vector) return std_ulogic;
  function and_reduce_f(input : std_ulogic_vector) return std_ulogic;
  function xor_reduce_f(input : std_ulogic_vector) return std_ulogic;
  function to_hexchar_f(input : std_ulogic_vector(3 downto 0)) return character;
  function bit_rev_f(input : std_ulogic_vector) return std_ulogic_vector;
  function is_power_of_two_f(input : natural) return boolean;
  function bswap_f(input : std_ulogic_vector) return std_ulogic_vector;
  function popcount_f(input : std_ulogic_vector) return natural;
  function leading_zeros_f(input : std_ulogic_vector) return natural;
  function replicate_f(input : std_ulogic; num : natural) return std_ulogic_vector;
  impure function mem32_init_f(init : mem32_t; depth : natural) return mem32_t;
  function print_version_f(version : std_ulogic_vector(31 downto 0)) return string;
  function match_f(input : std_ulogic_vector; pattern : std_ulogic_vector) return boolean;

-- **********************************************************************************************************
-- NEORV32 Processor Top Entity (component prototype)
-- **********************************************************************************************************

  component neorv32_top
    generic (
      -- Processor Clocking --
      CLOCK_FREQUENCY       : natural                        := 0;
      HART_BASE             : natural                        := 0;
      -- Dual-Core Configuration --
      DUAL_CORE_EN          : boolean                        := false;
      -- Boot Configuration --
      BOOT_MODE_SELECT      : natural range 0 to 2           := 0;
      BOOT_ADDR_CUSTOM      : std_ulogic_vector(31 downto 0) := x"00000000";
      -- On-Chip Debugger (OCD) --
      OCD_EN                : boolean                        := false;
      OCD_AUTHENTICATION    : boolean                        := false;
      OCD_JEDEC_ID          : std_ulogic_vector(10 downto 0) := "00000000000";
      -- RISC-V CPU Extensions --
      RISCV_ISA_C           : boolean                        := false;
      RISCV_ISA_E           : boolean                        := false;
      RISCV_ISA_M           : boolean                        := false;
      RISCV_ISA_U           : boolean                        := false;
      RISCV_ISA_Zaamo       : boolean                        := false;
      RISCV_ISA_Zalrsc      : boolean                        := false;
      RISCV_ISA_Zba         : boolean                        := false;
      RISCV_ISA_Zbb         : boolean                        := false;
      RISCV_ISA_Zbkb        : boolean                        := false;
      RISCV_ISA_Zbkc        : boolean                        := false;
      RISCV_ISA_Zbkx        : boolean                        := false;
      RISCV_ISA_Zbs         : boolean                        := false;
      RISCV_ISA_Zfinx       : boolean                        := false;
      RISCV_ISA_Zicntr      : boolean                        := false;
      RISCV_ISA_Zicond      : boolean                        := false;
      RISCV_ISA_Zihpm       : boolean                        := false;
      RISCV_ISA_Zmmul       : boolean                        := false;
      RISCV_ISA_Zknd        : boolean                        := false;
      RISCV_ISA_Zkne        : boolean                        := false;
      RISCV_ISA_Zknh        : boolean                        := false;
      RISCV_ISA_Zksed       : boolean                        := false;
      RISCV_ISA_Zksh        : boolean                        := false;
      RISCV_ISA_Zxcfu       : boolean                        := false;
      -- Tuning Options --
      CPU_CLOCK_GATING_EN   : boolean                        := false;
      CPU_FAST_MUL_EN       : boolean                        := false;
      CPU_FAST_SHIFT_EN     : boolean                        := false;
      CPU_RF_HW_RST_EN      : boolean                        := false;
      -- Physical Memory Protection (PMP) --
      PMP_NUM_REGIONS       : natural range 0 to 16          := 0;
      PMP_MIN_GRANULARITY   : natural                        := 4;
      PMP_TOR_MODE_EN       : boolean                        := false;
      PMP_NAP_MODE_EN       : boolean                        := false;
      -- Hardware Performance Monitors (HPM) --
      HPM_NUM_CNTS          : natural range 0 to 13          := 0;
      HPM_CNT_WIDTH         : natural range 0 to 64          := 40;
      -- Internal Instruction memory (IMEM) --
      MEM_INT_IMEM_EN       : boolean                        := false;
      MEM_INT_IMEM_SIZE     : natural                        := 16*1024;
      -- Internal Data memory (DMEM) --
      MEM_INT_DMEM_EN       : boolean                        := false;
      MEM_INT_DMEM_SIZE     : natural                        := 8*1024;
      -- Internal Instruction Cache (iCACHE) --
      ICACHE_EN             : boolean                        := false;
      ICACHE_NUM_BLOCKS     : natural range 1 to 256         := 4;
      ICACHE_BLOCK_SIZE     : natural range 4 to 2**16       := 64;
      -- Internal Data Cache (dCACHE) --
      DCACHE_EN             : boolean                        := false;
      DCACHE_NUM_BLOCKS     : natural range 1 to 256         := 4;
      DCACHE_BLOCK_SIZE     : natural range 4 to 2**16       := 64;
      -- External bus interface (XBUS) --
      XBUS_EN               : boolean                        := false;
      XBUS_TIMEOUT          : natural                        := 255;
      XBUS_REGSTAGE_EN      : boolean                        := false;
      XBUS_CACHE_EN         : boolean                        := false;
      XBUS_CACHE_NUM_BLOCKS : natural range 1 to 256         := 64;
      XBUS_CACHE_BLOCK_SIZE : natural range 1 to 2**16       := 32;
      -- Processor peripherals --
      IO_DISABLE_SYSINFO    : boolean                        := false;
      IO_GPIO_NUM           : natural range 0 to 64          := 0;
      IO_CLINT_EN           : boolean                        := false;
      IO_UART0_EN           : boolean                        := false;
      IO_UART0_RX_FIFO      : natural range 1 to 2**15       := 1;
      IO_UART0_TX_FIFO      : natural range 1 to 2**15       := 1;
      IO_UART1_EN           : boolean                        := false;
      IO_UART1_RX_FIFO      : natural range 1 to 2**15       := 1;
      IO_UART1_TX_FIFO      : natural range 1 to 2**15       := 1;
      IO_SPI_EN             : boolean                        := false;
      IO_SPI_FIFO           : natural range 1 to 2**15       := 1;
      IO_SDI_EN             : boolean                        := false;
      IO_SDI_FIFO           : natural range 1 to 2**15       := 1;
      IO_TWI_EN             : boolean                        := false;
      IO_TWI_FIFO           : natural range 1 to 2**15       := 1;
      IO_TWD_EN             : boolean                        := false;
      IO_TWD_FIFO           : natural range 1 to 2**15       := 1;
      IO_PWM_NUM_CH         : natural range 0 to 16          := 0;
      IO_WDT_EN             : boolean                        := false;
      IO_TRNG_EN            : boolean                        := false;
      IO_TRNG_FIFO          : natural range 1 to 2**15       := 1;
      IO_CFS_EN             : boolean                        := false;
      IO_CFS_CONFIG         : std_ulogic_vector(31 downto 0) := x"00000000";
      IO_CFS_IN_SIZE        : natural                        := 32;
      IO_CFS_OUT_SIZE       : natural                        := 32;
      IO_NEOLED_EN          : boolean                        := false;
      IO_NEOLED_TX_FIFO     : natural range 1 to 2**15       := 1;
      IO_GPTMR_EN           : boolean                        := false;
      IO_ONEWIRE_EN         : boolean                        := false;
      IO_ONEWIRE_FIFO       : natural range 1 to 2**15       := 1;
      IO_DMA_EN             : boolean                        := false;
      IO_SLINK_EN           : boolean                        := false;
      IO_SLINK_RX_FIFO      : natural range 1 to 2**15       := 1;
      IO_SLINK_TX_FIFO      : natural range 1 to 2**15       := 1;
      IO_CRC_EN             : boolean                        := false
    );
    port (
      -- Global control --
      clk_i          : in  std_ulogic;
      rstn_i         : in  std_ulogic;
      rstn_ocd_o     : out std_ulogic;
      rstn_wdt_o     : out std_ulogic;
      -- JTAG on-chip debugger interface (available if OCD_EN = true) --
      jtag_tck_i     : in  std_ulogic := 'L';
      jtag_tdi_i     : in  std_ulogic := 'L';
      jtag_tdo_o     : out std_ulogic;
      jtag_tms_i     : in  std_ulogic := 'L';
      -- External bus interface (available if XBUS_EN = true) --
      xbus_adr_o     : out std_ulogic_vector(31 downto 0);
      xbus_dat_o     : out std_ulogic_vector(31 downto 0);
      xbus_tag_o     : out std_ulogic_vector(2 downto 0);
      xbus_we_o      : out std_ulogic;
      xbus_sel_o     : out std_ulogic_vector(3 downto 0);
      xbus_stb_o     : out std_ulogic;
      xbus_cyc_o     : out std_ulogic;
      xbus_dat_i     : in  std_ulogic_vector(31 downto 0) := (others => 'L');
      xbus_ack_i     : in  std_ulogic := 'L';
      xbus_err_i     : in  std_ulogic := 'L';
      -- Stream Link Interface (available if IO_SLINK_EN = true) --
      slink_rx_dat_i : in  std_ulogic_vector(31 downto 0) := (others => 'L');
      slink_rx_src_i : in  std_ulogic_vector(3 downto 0) := (others => 'L');
      slink_rx_val_i : in  std_ulogic := 'L';
      slink_rx_lst_i : in  std_ulogic := 'L';
      slink_rx_rdy_o : out std_ulogic;
      slink_tx_dat_o : out std_ulogic_vector(31 downto 0);
      slink_tx_dst_o : out std_ulogic_vector(3 downto 0);
      slink_tx_val_o : out std_ulogic;
      slink_tx_lst_o : out std_ulogic;
      slink_tx_rdy_i : in  std_ulogic := 'L';
      -- GPIO (available if IO_GPIO_NUM > 0) --
      gpio_o         : out std_ulogic_vector(31 downto 0);
      gpio_i         : in  std_ulogic_vector(31 downto 0) := (others => 'L');
      -- primary UART0 (available if IO_UART0_EN = true) --
      uart0_txd_o    : out std_ulogic;
      uart0_rxd_i    : in  std_ulogic := 'L';
      uart0_rtsn_o   : out std_ulogic;
      uart0_ctsn_i   : in  std_ulogic := 'L';
      -- secondary UART1 (available if IO_UART1_EN = true) --
      uart1_txd_o    : out std_ulogic;
      uart1_rxd_i    : in  std_ulogic := 'L'; -- UART1 receive data
      uart1_rtsn_o   : out std_ulogic;
      uart1_ctsn_i   : in  std_ulogic := 'L';
      -- SPI (available if IO_SPI_EN = true) --
      spi_clk_o      : out std_ulogic;
      spi_dat_o      : out std_ulogic;
      spi_dat_i      : in  std_ulogic := 'L';
      spi_csn_o      : out std_ulogic_vector(7 downto 0); -- SPI CS
      -- SDI (available if IO_SDI_EN = true) --
      sdi_clk_i      : in  std_ulogic := 'L';
      sdi_dat_o      : out std_ulogic;
      sdi_dat_i      : in  std_ulogic := 'L';
      sdi_csn_i      : in  std_ulogic := 'H';
      -- TWI (available if IO_TWI_EN = true) --
      twi_sda_i      : in  std_ulogic := 'H';
      twi_sda_o      : out std_ulogic;
      twi_scl_i      : in  std_ulogic := 'H';
      twi_scl_o      : out std_ulogic;
      -- TWD (available if IO_TWD_EN = true) --
      twd_sda_i      : in  std_ulogic := 'H';
      twd_sda_o      : out std_ulogic;
      twd_scl_i      : in  std_ulogic := 'H';
      twd_scl_o      : out std_ulogic;
      -- 1-Wire Interface (available if IO_ONEWIRE_EN = true) --
      onewire_i      : in  std_ulogic := 'H';
      onewire_o      : out std_ulogic;
      -- PWM (available if IO_PWM_NUM_CH > 0) --
      pwm_o          : out std_ulogic_vector(15 downto 0); -- pwm channels
      -- Custom Functions Subsystem IO --
      cfs_in_i       : in  std_ulogic_vector(IO_CFS_IN_SIZE-1 downto 0) := (others => 'L');
      cfs_out_o      : out std_ulogic_vector(IO_CFS_OUT_SIZE-1 downto 0);
      -- NeoPixel-compatible smart LED interface (available if IO_NEOLED_EN = true) --
      neoled_o       : out std_ulogic;
      -- Machine timer system time (available if IO_CLINT_EN = true) --
      mtime_time_o   : out std_ulogic_vector(63 downto 0);
      -- CPU Interrupts --
      mtime_irq_i    : in  std_ulogic := 'L';
      msw_irq_i      : in  std_ulogic := 'L';
      mext_irq_i     : in  std_ulogic := 'L'
    );
  end component;

end neorv32_package;

package body neorv32_package is

-- **********************************************************************************************************
-- Helper Functions
-- **********************************************************************************************************

  -- Minimal required number of bits to represent <input> numbers ---------------------------
  -- -------------------------------------------------------------------------------------------
  function index_size_f(input : natural) return natural is
  begin
    for i in 0 to natural'high loop
      if (2**i >= input) then
        return i;
      end if;
    end loop;
    return 0;
  end function index_size_f;

  -- Conditional select natural -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function cond_sel_natural_f(cond : boolean; val_t : natural; val_f : natural) return natural is
  begin
    if cond then
      return val_t;
    else
      return val_f;
    end if;
  end function cond_sel_natural_f;

  -- Conditional select std_ulogic_vector ---------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function cond_sel_suv_f(cond : boolean; val_t : std_ulogic_vector; val_f : std_ulogic_vector) return std_ulogic_vector is
  begin
    if cond then
      return val_t;
    else
      return val_f;
    end if;
  end function cond_sel_suv_f;

  -- Conditional select string --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function cond_sel_string_f(cond : boolean; val_t : string; val_f : string) return string is
  begin
    if cond then
      return val_t;
    else
      return val_f;
    end if;
  end function cond_sel_string_f;

  -- Select minimal natural value -----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function max_natural_f(a : natural; b : natural) return natural is
  begin
    if a < b then
      return b;
    else
      return a;
    end if;
  end function max_natural_f;

  -- Select maximal natural value -----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function min_natural_f(a : natural; b : natural) return natural is
  begin
    if a < b then
      return a;
    else
      return b;
    end if;
  end function min_natural_f;

  -- Convert boolean to std_ulogic ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function bool_to_ulogic_f(cond : boolean) return std_ulogic is
  begin
    if cond then
      return '1';
    else
      return '0';
    end if;
  end function bool_to_ulogic_f;

  -- OR all bits ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function or_reduce_f(input : std_ulogic_vector) return std_ulogic is
    variable tmp_v : std_ulogic;
  begin
    tmp_v := '0';
    for i in input'range loop
      tmp_v := tmp_v or input(i);
    end loop;
    return tmp_v;
  end function or_reduce_f;

  -- AND all bits ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function and_reduce_f(input : std_ulogic_vector) return std_ulogic is
    variable tmp_v : std_ulogic;
  begin
    tmp_v := '1';
    for i in input'range loop
      tmp_v := tmp_v and input(i);
    end loop;
    return tmp_v;
  end function and_reduce_f;

  -- XOR all bits ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function xor_reduce_f(input : std_ulogic_vector) return std_ulogic is
    variable tmp_v : std_ulogic;
  begin
    tmp_v := '0';
    for i in input'range loop
      tmp_v := tmp_v xor input(i);
    end loop;
    return tmp_v;
  end function xor_reduce_f;

  -- Convert 4-bit std_ulogic_vector to lowercase hex char ----------------------------------
  -- -------------------------------------------------------------------------------------------
  function to_hexchar_f(input : std_ulogic_vector(3 downto 0)) return character is
    variable hex_v : string(1 to 16);
  begin
    hex_v := "0123456789abcdef";
    if ((input(0) /= '0') and (input(0) /= '1')) or
       ((input(1) /= '0') and (input(1) /= '1')) or
       ((input(2) /= '0') and (input(2) /= '1')) or
       ((input(3) /= '0') and (input(3) /= '1')) then
      return '?';
    else
      return hex_v(to_integer(unsigned(input)) + 1);
    end if;
  end function to_hexchar_f;

  -- Bit reversal ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function bit_rev_f(input : std_ulogic_vector) return std_ulogic_vector is
    variable tmp_v, output_v : std_ulogic_vector(input'length-1 downto 0);
  begin
    tmp_v := input;
    for i in 0 to input'length-1 loop
      output_v((input'length-1)-i) := tmp_v(i);
    end loop;
    return output_v;
  end function bit_rev_f;

  -- Test if input number is a power of two -------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function is_power_of_two_f(input : natural) return boolean is
    variable tmp_v : unsigned(31 downto 0);
  begin
    tmp_v := to_unsigned(input, 32);
    if (input = 0) then
      return false;
    elsif (input = 1) then
      return true;
    else
      if ((tmp_v and (tmp_v - 1)) = 0) then
        return true;
      else
        return false;
      end if;
    end if;
  end function is_power_of_two_f;

  -- Swap all bytes of a N*8-bit word (endianness conversion) -------------------------------
  -- -------------------------------------------------------------------------------------------
  function bswap_f(input : std_ulogic_vector) return std_ulogic_vector is
    variable output_v : std_ulogic_vector(input'range);
    variable j        : natural range 0 to input'length/8;
  begin
    for i in 0 to (input'length/8)-1 loop
      j := ((input'length/8) - 1) - i;
      output_v(i*8+7 downto i*8+0) := input(j*8+7 downto j*8+0);
    end loop;
    return output_v;
  end function bswap_f;

  -- Population count (number of set bits) --------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function popcount_f(input : std_ulogic_vector) return natural is
    variable cnt_v : natural range 0 to input'length;
  begin
    cnt_v := 0;
    for i in 0 to input'length-1 loop
      if (input(i) = '1') then
        cnt_v := cnt_v + 1;
      end if;
    end loop;
    return cnt_v;
  end function popcount_f;

  -- Count leading zeros --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function leading_zeros_f(input : std_ulogic_vector) return natural is
    variable cnt_v : natural range 0 to input'length;
  begin
    cnt_v := 0;
    for i in input'length-1 downto 0 loop
      if (input(i) = '0') then
        cnt_v := cnt_v + 1;
      else
        exit;
      end if;
    end loop;
    return cnt_v;
  end function leading_zeros_f;

  -- Replicate input bit num times ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  function replicate_f(input : std_ulogic; num : natural) return std_ulogic_vector is
    variable tmp_v : std_ulogic_vector(num-1 downto 0);
  begin
    tmp_v := (others => input);
    return tmp_v;
  end function replicate_f;

  -- Initialize mem32_t array from another mem32_t array ------------------------------------
  -- -------------------------------------------------------------------------------------------
  impure function mem32_init_f(init : mem32_t; depth : natural) return mem32_t is
    variable mem_v : mem32_t(0 to depth-1);
  begin
    mem_v := (others => (others => '0'));
    if (init'length > depth) then
      report "[NEORV32] mem32_init_f: initialization image is overflowing memory range!" severity warning;
    else
      mem_v(0 to init'length-1) := init(0 to init'length-1);
    end if;
    return mem_v;
  end function mem32_init_f;

  -- Print hardware version in human-readable format (xx.xx.xx.xx) --------------------------
  -- -------------------------------------------------------------------------------------------
  function print_version_f(version : std_ulogic_vector(31 downto 0)) return string is
    variable res_v : string(1 to 11);
    variable idx_v : natural;
  begin
    idx_v := 1;
    for i in 4 downto 1 loop
      if (version((i*8)-1 downto (i*8)-4) /= x"0") then -- print only if not trailing zero
        res_v(idx_v) := to_hexchar_f(version((i*8)-1 downto (i*8)-4)); -- high nibble
        idx_v := idx_v + 1;
      end if;
      res_v(idx_v) := to_hexchar_f(version((i*8)-5 downto (i*8)-8)); -- low nibble
      idx_v := idx_v + 1;
      if (i /= 1) then -- separator
        res_v(idx_v) := '.';
        idx_v := idx_v + 1;
      end if;
    end loop;
    return res_v;
  end function print_version_f;

  -- Check if signal matches binary pattern (skip elements compared with '-') ---------------
  -- -------------------------------------------------------------------------------------------
  function match_f(input : std_ulogic_vector; pattern : std_ulogic_vector) return boolean is
    variable match_v : boolean;
  begin
    if (input'length /= pattern'length) then
      report "[NEORV32] match_f: input and pattern have different sizes!" severity error;
      return false;
    else
      match_v := true;
      for i in input'length-1 downto 0 loop
        if (pattern(i) = '1') or (pattern(i) = '0') then -- valid pattern value, skip everything else
          match_v := match_v and boolean(pattern(i) = input(i));
        end if;
      end loop;
      return match_v;
    end if;
  end function match_f;

end neorv32_package;
