-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: Single-Precision FPU (RISC-V "Zfinx" Extension)      --
-- -------------------------------------------------------------------------------- --
-- The Zfinx floating-point extension uses the integer register file (x) for all FP --
-- operations.                                                                      --
--                                                                                  --
-- Design Notes:                                                                    --
-- * This FPU is based on a multi-cycle architecture and is NOT suited for          --
--   pipelined operations.                                                          --
-- * The hardware design goal was SIZE (performance comes second). All shift        --
--   operations are done using an iterative approach (no barrel shifters!).         --
-- * Multiplication (FMUL instruction) will infer DSP blocks (if available).        --
-- * Subnormal numbers are not supported yet - they are "flushed to zero" before    --
--   entering the actual FPU core.                                                  --
-- * Division and square root operations (FDIV, FSQRT) and fused multiply-          --
--   accumulate operations (F[N]MADD) are not supported yet - they will raise an    --
--   illegal instruction exception.                                                 --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2024 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_cp_fpu is
  generic (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT : boolean := false -- Implemented sub-normal support, default false
  );
  port (
    -- global control --
    clk_i       : in  std_ulogic; -- global clock, rising edge
    rstn_i      : in  std_ulogic; -- global reset, low-active, async
    ctrl_i      : in  ctrl_bus_t; -- main control bus
    -- CSR interface --
    csr_we_i    : in  std_ulogic; -- write enable
    csr_addr_i  : in  std_ulogic_vector(1 downto 0); -- address
    csr_wdata_i : in  std_ulogic_vector(XLEN-1 downto 0); -- write data
    csr_rdata_o : out std_ulogic_vector(XLEN-1 downto 0); -- read data
    -- data input --
    cmp_i       : in  std_ulogic_vector(1 downto 0); -- comparator status
    rs1_i       : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 1
    rs2_i       : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 2
    rs3_i       : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 3
    -- result and status --
    res_o       : out std_ulogic_vector(XLEN-1 downto 0); -- operation result
    valid_o     : out std_ulogic -- data output valid
  );
end neorv32_cpu_cp_fpu;

architecture neorv32_cpu_cp_fpu_rtl of neorv32_cpu_cp_fpu is

  -- FPU core functions --
  constant op_class_c  : std_ulogic_vector(2 downto 0) := "000";
  constant op_comp_c   : std_ulogic_vector(2 downto 0) := "001";
  constant op_i2f_c    : std_ulogic_vector(2 downto 0) := "010";
  constant op_f2i_c    : std_ulogic_vector(2 downto 0) := "011";
  constant op_sgnj_c   : std_ulogic_vector(2 downto 0) := "100";
  constant op_minmax_c : std_ulogic_vector(2 downto 0) := "101";
  constant op_addsub_c : std_ulogic_vector(2 downto 0) := "110";
  constant op_mul_c    : std_ulogic_vector(2 downto 0) := "111";

  -- FPU CSRs --
  signal csr_frm    : std_ulogic_vector(2 downto 0); -- FPU rounding mode
  signal csr_fflags : std_ulogic_vector(4 downto 0); -- FPU exception flags
  signal fflags     : std_ulogic_vector(4 downto 0); -- exception flags

  -- float-to-integer unit --
  component neorv32_cpu_cp_fpu_f2i
  generic (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT : boolean := false -- Implemented sub-normal support, default false
  );
  port (
    -- control --
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    start_i    : in  std_ulogic; -- trigger operation
    abort_i    : in  std_ulogic; -- abort current operation
    rmode_i    : in  std_ulogic_vector(2 downto 0); -- rounding mode
    funct_i    : in  std_ulogic; -- 0=signed, 1=unsigned
    -- input --
    sign_i     : in  std_ulogic; -- sign
    exponent_i : in  std_ulogic_vector(7 downto 0); -- exponent
    mantissa_i : in  std_ulogic_vector(22 downto 0); -- mantissa
    class_i    : in  std_ulogic_vector(9 downto 0); -- operand class
    -- output --
    result_o   : out std_ulogic_vector(31 downto 0); -- integer result
    flags_o    : out std_ulogic_vector(4 downto 0); -- exception flags
    done_o     : out std_ulogic -- operation done
  );
  end component;

  -- normalizer + rounding unit --
  component neorv32_cpu_cp_fpu_normalizer
  generic (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT : boolean := false -- Implemented sub-normal support, default false
  );
  port (
    -- control --
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    start_i    : in  std_ulogic; -- trigger operation
    abort_i    : in  std_ulogic; -- abort current operation
    rmode_i    : in  std_ulogic_vector(2 downto 0); -- rounding mode
    funct_i    : in  std_ulogic; -- operating mode (0=norm&round, 1=int-to-float)
    -- input --
    sign_i     : in  std_ulogic; -- sign
    exponent_i : in  std_ulogic_vector(8 downto 0); -- extended exponent
    mantissa_i : in  std_ulogic_vector(47 downto 0); -- extended mantissa
    integer_i  : in  std_ulogic_vector(31 downto 0); -- integer input
    class_i    : in  std_ulogic_vector(9 downto 0); -- input number class
    flags_i    : in  std_ulogic_vector(4 downto 0); -- exception flags input
    -- output --
    result_o   : out std_ulogic_vector(31 downto 0); -- result (float or int)
    flags_o    : out std_ulogic_vector(4 downto 0); -- exception flags
    done_o     : out std_ulogic -- operation done
  );
  end component;

  -- commands (one-hot) --
  type cmd_t is record
    instr_class  : std_ulogic;
    instr_sgnj   : std_ulogic;
    instr_comp   : std_ulogic;
    instr_i2f    : std_ulogic;
    instr_f2i    : std_ulogic;
    instr_minmax : std_ulogic;
    instr_addsub : std_ulogic;
    instr_mul    : std_ulogic;
    funct        : std_ulogic_vector(2 downto 0);
    valid        : std_ulogic;
  end record;
  signal cmd : cmd_t;
  signal funct_ff : std_ulogic_vector(2 downto 0);

  -- co-processor control engine --
  type ctrl_state_t is (S_IDLE, S_BUSY);
  type ctrl_engine_t is record
    state : ctrl_state_t;
    start : std_ulogic;
    valid : std_ulogic;
  end record;
  signal ctrl_engine : ctrl_engine_t;

  -- floating-point operands --
  type op_data_t  is array (0 to 1) of std_ulogic_vector(31 downto 0);
  type op_class_t is array (0 to 1) of std_ulogic_vector(9 downto 0);
  type fpu_operands_t is record
    rs1       : std_ulogic_vector(31 downto 0); -- operand 1
    rs1_class : std_ulogic_vector(9 downto 0);  -- operand 1 number class
    rs2       : std_ulogic_vector(31 downto 0); -- operand 2
    rs2_class : std_ulogic_vector(9 downto 0);  -- operand 2 number class
    frm       : std_ulogic_vector(2 downto 0);  -- rounding mode
  end record;
  signal op_data      : op_data_t;
  signal op_class     : op_class_t;
  signal fpu_operands : fpu_operands_t;

  -- floating-point comparator --
  signal cmp_ff        : std_ulogic_vector(1 downto 0);
  signal comp_equal_ff : std_ulogic;
  signal comp_less_ff  : std_ulogic;

  -- functional units interface --
  type fu_interface_t is record
    result : std_ulogic_vector(31 downto 0);
    flags  : std_ulogic_vector(4 downto 0);
    start  : std_ulogic;
    done   : std_ulogic;
  end record;
  signal fu_classify    : fu_interface_t;
  signal fu_compare     : fu_interface_t;
  signal fu_sign_inject : fu_interface_t;
  signal fu_min_max     : fu_interface_t;
  signal fu_conv_f2i    : fu_interface_t;
  signal fu_addsub      : fu_interface_t;
  signal fu_mul         : fu_interface_t;
  signal fu_core_done   : std_ulogic; -- FU operation completed

  -- integer-to-float --
  type fu_i2f_interface_t is record
    result : std_ulogic_vector(31 downto 0);
    sign   : std_ulogic;
    start  : std_ulogic;
    done   : std_ulogic;
  end record;
  signal fu_conv_i2f : fu_i2f_interface_t; -- float result

  -- multiplier unit --
  type multiplier_t is record
    opa       : unsigned(23 downto 0); -- mantissa A plus hidden one
    opb       : unsigned(23 downto 0); -- mantissa B plus hidden one
    buf_ff    : unsigned(47 downto 0); -- product buffer
    sign      : std_ulogic; -- resulting sign
    product   : std_ulogic_vector(47 downto 0); -- product
    exp_sum   : std_ulogic_vector(8 downto 0);  -- incl 1x overflow/underflow bit
    exp_res   : std_ulogic_vector(9 downto 0);  -- resulting exponent incl 2x overflow/underflow bit
    --
    res_class : std_ulogic_vector(9 downto 0);
    flags     : std_ulogic_vector(4 downto 0);  -- exception flags
    --
    start     : std_ulogic;
    latency   : std_ulogic_vector(2 downto 0);  -- unit latency
    done      : std_ulogic;
  end record;
  signal multiplier : multiplier_t;

  -- adder/subtractor unit --
  type addsub_t is record
    -- input comparison --
    exp_comp  : std_ulogic_vector(1 downto 0);  -- equal & less
    small_exp : std_ulogic_vector(7 downto 0);
    small_man : std_ulogic_vector(23 downto 0); -- mantissa + hidden one
    large_exp : std_ulogic_vector(7 downto 0);
    large_man : std_ulogic_vector(23 downto 0); -- mantissa + hidden one
    -- smaller mantissa alignment --
    man_sreg  : std_ulogic_vector(23 downto 0); -- mantissa + hidden one
    man_g_ext : std_ulogic;
    man_r_ext : std_ulogic;
    man_s_ext : std_ulogic;
    exp_cnt   : std_ulogic_vector(8 downto 0);
    -- adder/subtractor stage --
    man_comp  : std_ulogic;
    man_s     : std_ulogic_vector(26 downto 0); -- mantissa + hidden one + GRS
    man_l     : std_ulogic_vector(26 downto 0); -- mantissa + hidden one + GRS
    add_stage : std_ulogic_vector(27 downto 0); -- adder result incl. overflow
    -- result --
    res_sign  : std_ulogic;
    res_sum   : std_ulogic_vector(27 downto 0); -- mantissa sum (+1 bit) + GRS bits (for rounding)
    res_class : std_ulogic_vector(9 downto 0);
    flags     : std_ulogic_vector(4 downto 0);  -- exception flags
    -- arbitration --
    start     : std_ulogic;
    latency   : std_ulogic_vector(4 downto 0);  -- unit latency
    done      : std_ulogic;
  end record;
  signal addsub : addsub_t;

  -- normalizer interface (normalization & rounding and int-to-float) --
  type normalizer_t is record
    start     : std_ulogic;
    mode      : std_ulogic;
    sign      : std_ulogic;
    xexp      : std_ulogic_vector(8 downto 0);
    xmantissa : std_ulogic_vector(47 downto 0);
    result    : std_ulogic_vector(31 downto 0);
    class     : std_ulogic_vector(9 downto 0);
    flags_in  : std_ulogic_vector(4 downto 0);
    flags_out : std_ulogic_vector(4 downto 0);
    done      : std_ulogic;
  end record;
  signal normalizer : normalizer_t;

begin

-- ****************************************************************************************************************************
-- Control
-- ****************************************************************************************************************************

  -- CSR Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- write access --
  csr_write: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr_frm    <= (others => '0');
      csr_fflags <= (others => '0');
    elsif rising_edge(clk_i) then
      if (csr_we_i = '1') then
        -- exception flags --
        if (csr_addr_i = csr_fflags_c(1 downto 0)) then
          csr_fflags <= csr_wdata_i(4 downto 0);
        end if;
        -- rounding mode --
        if (csr_addr_i = csr_frm_c(1 downto 0)) then
          csr_frm <= csr_wdata_i(2 downto 0);
        end if;
        -- control/status (frm & fflags) --
        if (csr_addr_i = csr_fcsr_c(1 downto 0)) then
          csr_frm    <= csr_wdata_i(7 downto 5);
          csr_fflags <= csr_wdata_i(4 downto 0);
        end if;
      else -- auto-update ("accumulate" flags)
        csr_fflags <= csr_fflags or fflags;
      end if;
    end if;
  end process csr_write;

  -- read access --
  csr_read: process(csr_addr_i, csr_fflags, csr_frm)
  begin
    csr_rdata_o <= (others => '0'); -- default
    case csr_addr_i is
      when "01"   => csr_rdata_o(4 downto 0) <= csr_fflags; -- fflags: exception flags
      when "10"   => csr_rdata_o(2 downto 0) <= csr_frm; -- frm: rounding mode
      when "11"   => csr_rdata_o(7 downto 0) <= csr_frm & csr_fflags; -- fcsr: control/status (frm & fflags)
      when others => NULL;
    end case;
  end process csr_read;


  -- Instruction Decoding -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- one-hot re-encoding --
  cmd.instr_class  <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "11100") and (ctrl_i.ir_funct3 = "001")               else '0'; -- FCLASS
  cmd.instr_comp   <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "10100") and (ctrl_i.ir_funct3(2) = '0')              else '0'; -- FEQ/FLT/FLE
  cmd.instr_i2f    <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "11010") and (ctrl_i.ir_funct12(4 downto 1) = "0000") else '0'; -- FCVT
  cmd.instr_f2i    <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "11000") and (ctrl_i.ir_funct12(4 downto 1) = "0000") else '0'; -- FCVT
  cmd.instr_sgnj   <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "00100") and (ctrl_i.ir_funct3(2) = '0')              else '0'; -- FSGNJ
  cmd.instr_minmax <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "00101") and (ctrl_i.ir_funct3(2 downto 1) = "00")    else '0'; -- FMIN/FMAX
  cmd.instr_addsub <= '1' when (ctrl_i.ir_funct12(11 downto 8) = "0000")                                               else '0'; -- FADD/FSUB
  cmd.instr_mul    <= '1' when (ctrl_i.ir_funct12(11 downto 7) = "00010")                                              else '0'; -- FMUL

  -- valid FPU operation? --
  cmd.valid <= '1' when (ctrl_i.ir_funct12(6 downto 5) = "00") and -- single-precision format only
                        ((cmd.instr_class  = '1') or (cmd.instr_comp   = '1') or
                         (cmd.instr_i2f    = '1') or (cmd.instr_f2i    = '1') or
                         (cmd.instr_sgnj   = '1') or (cmd.instr_minmax = '1') or
                         (cmd.instr_addsub = '1') or (cmd.instr_mul    = '1')) else '0';

  -- binary re-encoding --
  cmd.funct <= op_mul_c    when (cmd.instr_mul    = '1') else
               op_addsub_c when (cmd.instr_addsub = '1') else
               op_minmax_c when (cmd.instr_minmax = '1') else
               op_sgnj_c   when (cmd.instr_sgnj   = '1') else
               op_f2i_c    when (cmd.instr_f2i    = '1') else
               op_i2f_c    when (cmd.instr_i2f    = '1') else
               op_comp_c   when (cmd.instr_comp   = '1') else
               op_class_c;


  -- Input Operands: Check for subnormal numbers (flush to zero) ----------------------------
  -- -------------------------------------------------------------------------------------------
  -- [WARNING] Subnormal numbers are not supported yet and are "flushed to zero"!
  -- rs1 --
  op_data(0)(31)           <= rs1_i(31);
  op_data(0)(30 downto 23) <= rs1_i(30 downto 23);
  op_data(0)(22 downto 0)  <= (others => '0') when (rs1_i(30 downto 23) = "00000000") else rs1_i(22 downto 0); -- flush mantissa to zero if subnormal
  -- rs2 --
  op_data(1)(31)           <= rs2_i(31);
  op_data(1)(30 downto 23) <= rs2_i(30 downto 23);
  op_data(1)(22 downto 0)  <= (others => '0') when (rs2_i(30 downto 23) = "00000000") else rs2_i(22 downto 0); -- flush mantissa to zero if subnormal


  -- Number Classifier ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  number_classifier: process(op_data, rs1_i, rs2_i)
    variable op_m_all_zero_v, op_e_all_zero_v, op_e_all_one_v       : std_ulogic;
    variable op_is_zero_v, op_is_inf_v, op_is_denorm_v, op_is_nan_v : std_ulogic;
  begin
    for i in 0 to 1 loop -- for rs1 and rs2 inputs
      -- check for all-zero/all-one --
      op_m_all_zero_v := not or_reduce_f(op_data(i)(22 downto 0));
      op_e_all_zero_v := not or_reduce_f(op_data(i)(30 downto 23));
      op_e_all_one_v  :=    and_reduce_f(op_data(i)(30 downto 23));

      -- check special cases --
      op_is_zero_v := op_e_all_zero_v and op_m_all_zero_v;  -- zero
      op_is_inf_v  := op_e_all_one_v  and op_m_all_zero_v;  -- infinity
      -- As we are flushing subnormals before classification they will show up as 0.0
      -- So we check calculate the denorm value is the non-flushed mantissa gated by the op_e_all_zero
      if (i = 0) then
        op_is_denorm_v := or_reduce_f(rs1_i(22 downto 0)) and op_e_all_zero_v; -- set the number to subnormal
      end if;
      if (i = 1) then
        op_is_denorm_v := or_reduce_f(rs2_i(22 downto 0)) and op_e_all_zero_v; -- set the number to subnormal
      end if;
      -- Placeholder for rs3_i support, as i cannot be 3.
      --if (i = 2) then
      --  op_is_denorm_v := or_reduce_f(rs3_i(22 downto 0)) and op_e_all_zero_v; -- set the number to subnormal
      --end if;
      op_is_nan_v := op_e_all_one_v and (not op_m_all_zero_v); -- NaN

      -- actual attributes --
      op_class(i)(fp_class_neg_inf_c)    <= op_data(i)(31) and op_is_inf_v; -- negative infinity
      op_class(i)(fp_class_neg_norm_c)   <= op_data(i)(31) and (not op_is_denorm_v) and (not op_is_nan_v) and (not op_is_inf_v) and (not op_is_zero_v); -- negative normal number
      op_class(i)(fp_class_neg_denorm_c) <= op_data(i)(31) and op_is_denorm_v; -- negative subnormal number
      op_class(i)(fp_class_neg_zero_c)   <= op_data(i)(31) and op_is_zero_v and (not op_is_denorm_v); -- negative zero
      op_class(i)(fp_class_pos_zero_c)   <= (not op_data(i)(31)) and op_is_zero_v and (not op_is_denorm_v); -- positive zero
      op_class(i)(fp_class_pos_denorm_c) <= (not op_data(i)(31)) and op_is_denorm_v; -- positive subnormal number
      op_class(i)(fp_class_pos_norm_c)   <= (not op_data(i)(31)) and (not op_is_denorm_v) and (not op_is_nan_v) and (not op_is_inf_v) and (not op_is_zero_v); -- positive normal number
      op_class(i)(fp_class_pos_inf_c)    <= (not op_data(i)(31)) and op_is_inf_v; -- positive infinity
      op_class(i)(fp_class_snan_c)       <= op_is_nan_v and (not op_data(i)(22)); -- signaling NaN
      op_class(i)(fp_class_qnan_c)       <= op_is_nan_v and (    op_data(i)(22)); -- quiet NaN
    end loop; -- i
  end process number_classifier;


  -- Co-Processor Control Engine ------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  control_engine_fsm: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl_engine.state      <= S_IDLE;
      ctrl_engine.valid      <= '0';
      ctrl_engine.start      <= '0';
      fpu_operands.frm       <= (others => '0');
      fpu_operands.rs1       <= (others => '0');
      fpu_operands.rs1_class <= (others => '0');
      fpu_operands.rs2       <= (others => '0');
      fpu_operands.rs2_class <= (others => '0');
      funct_ff               <= (others => '0');
      cmp_ff                 <= (others => '0');
    elsif rising_edge(clk_i) then
      -- arbiter defaults --
      ctrl_engine.valid <= '0';
      ctrl_engine.start <= '0';

      -- state machine --
      case ctrl_engine.state is

        when S_IDLE => -- waiting for operation trigger
        -- ------------------------------------------------------------
          funct_ff <= cmd.funct; -- actual operation to execute
          cmp_ff   <= cmp_i; -- main ALU comparator
          -- rounding mode --
          -- "round to nearest, ties to max magnitude" (0b100) is now supported
          if (ctrl_i.ir_funct3 = "111") then
            fpu_operands.frm <= csr_frm(2 downto 0);
          else
            fpu_operands.frm <= ctrl_i.ir_funct3(2 downto 0);
          end if;
          --
          if (ctrl_i.alu_cp_fpu = '1') and (cmd.valid = '1') then
            -- operand data --
            fpu_operands.rs1       <= op_data(0);
            fpu_operands.rs1_class <= op_class(0);
            fpu_operands.rs2       <= op_data(1);
            fpu_operands.rs2_class <= op_class(1);
            -- execute! --
            ctrl_engine.start <= '1';
            ctrl_engine.state <= S_BUSY;
          end if;

        when S_BUSY => -- operation in progress (multi-cycle)
        -- -----------------------------------------------------------
          if (fu_core_done = '1') or (ctrl_i.cpu_trap = '1') then -- processing done? abort if trap
            ctrl_engine.valid <= '1';
            ctrl_engine.state <= S_IDLE;
          end if;

        when others => -- undefined
        -- ------------------------------------------------------------
          ctrl_engine.state <= S_IDLE;

      end case;
    end if;
  end process control_engine_fsm;

  -- operation done / valid output --
  valid_o <= ctrl_engine.valid;


  -- Functional Unit Interface (operation-start trigger) ------------------------------------
  -- -------------------------------------------------------------------------------------------
  fu_classify.start    <= ctrl_engine.start and cmd.instr_class;
  fu_compare.start     <= ctrl_engine.start and cmd.instr_comp;
  fu_sign_inject.start <= ctrl_engine.start and cmd.instr_sgnj;
  fu_min_max.start     <= ctrl_engine.start and cmd.instr_minmax;
  fu_conv_i2f.start    <= ctrl_engine.start and cmd.instr_i2f;
  fu_conv_f2i.start    <= ctrl_engine.start and cmd.instr_f2i;
  fu_addsub.start      <= ctrl_engine.start and cmd.instr_addsub;
  fu_mul.start         <= ctrl_engine.start and cmd.instr_mul;


-- ****************************************************************************************************************************
-- FPU Core - Functional Units
-- ****************************************************************************************************************************

  -- Number Classifier (FCLASS) -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  fu_classify.flags <= (others => '0'); -- does not generate flags at all
  fu_classify.result(31 downto 10) <= (others => '0');
  fu_classify.result(9 downto 0) <= fpu_operands.rs1_class;
  fu_classify.done <= fu_classify.start;


  -- Floating-Point Comparator --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  float_comparator: process(rstn_i, clk_i)
    variable cond_v : std_ulogic_vector(1 downto 0);
  begin
    if (rstn_i = '0') then
      comp_equal_ff   <= '0';
      comp_less_ff    <= '0';
      fu_compare.done <= '0';
      fu_min_max.done <= '0';
    elsif rising_edge(clk_i) then
      -- equal --
      -- If we do not support subnormals we need to expand the compare with +/- denorm as if it was a +/- zero.
      if (not FPU_SUBNORMAL_SUPPORT) then
        if ((fpu_operands.rs1_class(fp_class_pos_inf_c)     = '1') and (fpu_operands.rs2_class(fp_class_pos_inf_c)   = '1')) or -- +inf == +inf
           ((fpu_operands.rs1_class(fp_class_neg_inf_c)     = '1') and (fpu_operands.rs2_class(fp_class_neg_inf_c)   = '1')) or -- -inf == -inf
           (((fpu_operands.rs1_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs1_class(fp_class_neg_zero_c)   = '1'))  and
            ((fpu_operands.rs2_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs2_class(fp_class_neg_zero_c)   = '1')))  or  -- +/-zero == +/-zero
           (((fpu_operands.rs1_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs1_class(fp_class_neg_denorm_c) = '1'))  and
            ((fpu_operands.rs2_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs2_class(fp_class_neg_zero_c)   = '1'))) or  -- +/-denorm == +/-zero
           (((fpu_operands.rs1_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs1_class(fp_class_neg_denorm_c) = '1'))  and
            ((fpu_operands.rs2_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs2_class(fp_class_neg_denorm_c) = '1'))) or  -- +/-denorm == +/-denorm
           (((fpu_operands.rs1_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs1_class(fp_class_neg_zero_c)   = '1'))  and
            ((fpu_operands.rs2_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs2_class(fp_class_neg_denorm_c) = '1'))) or  -- +/-zero == +/-denorm
           (cmp_ff(cmp_equal_c) = '1') then -- identical in every way (comparator result from main ALU)
          comp_equal_ff <= '1';
        else
          comp_equal_ff <= '0';
        end if;
      else
        if ((fpu_operands.rs1_class(fp_class_pos_inf_c)   = '1') and (fpu_operands.rs2_class(fp_class_pos_inf_c) = '1')) or -- +inf == +inf
           ((fpu_operands.rs1_class(fp_class_neg_inf_c)   = '1') and (fpu_operands.rs2_class(fp_class_neg_inf_c) = '1')) or -- -inf == -inf
           (((fpu_operands.rs1_class(fp_class_pos_zero_c) = '1') or (fpu_operands.rs1_class(fp_class_neg_zero_c) = '1')) and
            ((fpu_operands.rs2_class(fp_class_pos_zero_c) = '1') or (fpu_operands.rs2_class(fp_class_neg_zero_c) = '1'))) or  -- +/-zero == +/-zero
           (cmp_ff(cmp_equal_c) = '1') then -- identical in every way (comparator result from main ALU)
          comp_equal_ff <= '1';
        else
          comp_equal_ff <= '0';
        end if;
      end if;

      -- less than --
      -- If we do not support subnormals we need to expand the compare with +/- denorm as if it was a +/- zero.
      if (not FPU_SUBNORMAL_SUPPORT) then
        if ((fpu_operands.rs1_class(fp_class_pos_inf_c)     = '1') and (fpu_operands.rs2_class(fp_class_pos_inf_c)   = '1'))  or -- +inf !< +inf
           ((fpu_operands.rs1_class(fp_class_neg_inf_c)     = '1') and (fpu_operands.rs2_class(fp_class_neg_inf_c)   = '1'))  or -- -inf !< -inf
           (((fpu_operands.rs1_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs1_class(fp_class_neg_zero_c)   = '1'))  and -- +/- zero !< +/- zero
            ((fpu_operands.rs2_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs2_class(fp_class_neg_zero_c)   = '1'))) or
           (((fpu_operands.rs1_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs1_class(fp_class_neg_denorm_c) = '1'))  and -- +/- denorm !< +/- zero
            ((fpu_operands.rs2_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs2_class(fp_class_neg_zero_c)   = '1'))) or
           (((fpu_operands.rs1_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs1_class(fp_class_neg_denorm_c) = '1'))  and -- +/- zero !< +/- denorm
            ((fpu_operands.rs2_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs2_class(fp_class_neg_denorm_c) = '1'))) or
           (((fpu_operands.rs1_class(fp_class_pos_zero_c)   = '1') or (fpu_operands.rs1_class(fp_class_neg_zero_c)   = '1'))  and -- +/- zero !< +/- denorm
            ((fpu_operands.rs2_class(fp_class_pos_denorm_c) = '1') or (fpu_operands.rs2_class(fp_class_neg_denorm_c) = '1'))) then
          comp_less_ff <= '0';
        else
          cond_v := fpu_operands.rs1(31) & fpu_operands.rs2(31);
          case cond_v is
            when "10"   => comp_less_ff <= '1'; -- rs1 negative, rs2 positive
            when "01"   => comp_less_ff <= '0'; -- rs1 positive, rs2 negative
            when "00"   => comp_less_ff <= cmp_ff(cmp_less_c); -- both positive (comparator result from main ALU)
            -- As we are just inverting cmp_less this statement would also flag true if the two numbers are equal
            -- Added a "and not equal" to prevent this corner case.
            when "11"   => comp_less_ff <= (not cmp_ff(cmp_less_c)) and (not cmp_ff(cmp_equal_c)); -- both negative (comparator result from main ALU)
            when others => comp_less_ff <= '0'; -- undefined
          end case;
        end if;
      else
        if ((fpu_operands.rs1_class(fp_class_pos_inf_c)  = '1') and (fpu_operands.rs2_class(fp_class_pos_inf_c) = '1')) or -- +inf !< +inf
           ((fpu_operands.rs1_class(fp_class_neg_inf_c)  = '1') and (fpu_operands.rs2_class(fp_class_neg_inf_c) = '1')) or -- -inf !< -inf
           (((fpu_operands.rs1_class(fp_class_pos_zero_c) = '1') or (fpu_operands.rs1_class(fp_class_neg_zero_c) = '1')) and
            ((fpu_operands.rs2_class(fp_class_pos_zero_c) = '1') or (fpu_operands.rs2_class(fp_class_neg_zero_c) = '1'))) then  -- +/-zero !< +/-zero
          comp_less_ff <= '0';
        else
          cond_v := fpu_operands.rs1(31) & fpu_operands.rs2(31);
          case cond_v is
            when "10"   => comp_less_ff <= '1'; -- rs1 negative, rs2 positive
            when "01"   => comp_less_ff <= '0'; -- rs1 positive, rs2 negative
            when "00"   => comp_less_ff <= cmp_ff(cmp_less_c); -- both positive (comparator result from main ALU)
            -- As we are just inverting cmp_less this statement would also flag true if the two numbers are equal
            -- Added a "and not equal" to prevent this corner case.
            when "11"   => comp_less_ff <= not cmp_ff(cmp_less_c) and (not cmp_ff(cmp_equal_c)); -- both negative (comparator result from main ALU)
            when others => comp_less_ff <= '0'; -- undefined
          end case;
        end if;
      end if;

      -- comparator latency --
      fu_compare.done <= fu_compare.start; -- for actual comparison operation
      fu_min_max.done <= fu_min_max.start; -- for min/max operations
    end if;
  end process float_comparator;


  -- Comparison (FEQ/FLT/FLE) ---------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  float_comparison: process(fpu_operands, ctrl_i, comp_equal_ff, comp_less_ff)
    variable snan_v : std_ulogic; -- at least one input is sNaN
    variable qnan_v : std_ulogic; -- at least one input is qNaN
  begin
    -- check for NaN --
    snan_v := fpu_operands.rs1_class(fp_class_snan_c) or fpu_operands.rs2_class(fp_class_snan_c);
    qnan_v := fpu_operands.rs1_class(fp_class_qnan_c) or fpu_operands.rs2_class(fp_class_qnan_c);

    -- condition evaluation --
    -- assume no exceptions by default
    fu_compare.flags <= (others => '0');
    -- condition evaluation --
    fu_compare.result <= (others => '0');
    case ctrl_i.ir_funct3(1 downto 0) is
      when "00" => -- FLE: less than or equal
        fu_compare.result(0) <= (comp_less_ff or comp_equal_ff) and (not (snan_v or qnan_v)); -- result is zero if either input is NaN
        -- if one of the operands is unordered (q/sNAN) the compare operation must signal NV per 754.
        if ((snan_v or qnan_v) = '1') then
          fu_compare.flags(fp_exc_nv_c) <= '1';
        end if;
      when "01" => -- FLT: less than
        fu_compare.result(0) <= comp_less_ff and (not (snan_v or qnan_v)); -- result is zero if either input is NaN
        -- if one of the operands is unordered (q/sNAN) the compare operation must signal NV per 754.
        if ((snan_v or qnan_v) = '1') then
          fu_compare.flags(fp_exc_nv_c) <= '1';
        end if;
      when "10" => -- FEQ: equal
        fu_compare.result(0) <= comp_equal_ff and (not (snan_v or qnan_v)); -- result is zero if either input is NaN
        -- if one of the operands in the compare operation is a sNAN we must signal NV per 754.
        -- for equal compares we do not need to consider unordred NAN
        if ((snan_v) = '1') then
          fu_compare.flags(fp_exc_nv_c) <= '1';
        end if;
      when others => -- undefined
        fu_compare.result(0) <= '0';
    end case;
  end process float_comparison;

  -- latency --
  -- -> done in "float_comparator"

  -- exceptions --

  -- Min/Max Select (FMIN/FMAX) -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  min_max_select: process(fpu_operands, comp_less_ff, ctrl_i)
    variable cond_v : std_ulogic_vector(2 downto 0);
  begin
    -- comparison result - check for special cases: -0 is less than +0
    -- If we do not support subnormals we need to expand the compare with +/- denorm as if it was a +/- zero.
    if (not FPU_SUBNORMAL_SUPPORT) then
      if (((fpu_operands.rs1_class(fp_class_neg_zero_c)   = '1') and (fpu_operands.rs2_class(fp_class_pos_denorm_c) = '1')) or
          ((fpu_operands.rs1_class(fp_class_neg_denorm_c) = '1') and (fpu_operands.rs2_class(fp_class_pos_zero_c)   = '1')) or
          ((fpu_operands.rs1_class(fp_class_neg_denorm_c) = '1') and (fpu_operands.rs2_class(fp_class_pos_denorm_c) = '1')) or
          ((fpu_operands.rs1_class(fp_class_neg_zero_c)   = '1') and (fpu_operands.rs2_class(fp_class_pos_zero_c)   = '1'))) then
        cond_v(0) := ctrl_i.ir_funct3(0);
      elsif (((fpu_operands.rs1_class(fp_class_pos_zero_c)   = '1') and (fpu_operands.rs2_class(fp_class_neg_denorm_c) = '1')) or
             ((fpu_operands.rs1_class(fp_class_pos_denorm_c) = '1') and (fpu_operands.rs2_class(fp_class_neg_zero_c)   = '1')) or
             ((fpu_operands.rs1_class(fp_class_pos_denorm_c) = '1') and (fpu_operands.rs2_class(fp_class_neg_denorm_c) = '1')) or
             ((fpu_operands.rs1_class(fp_class_pos_zero_c)   = '1') and (fpu_operands.rs2_class(fp_class_neg_zero_c)   = '1'))) then
        cond_v(0) := not ctrl_i.ir_funct3(0);
      else
        cond_v(0) := not (comp_less_ff xor ctrl_i.ir_funct3(0)); -- min/max select
      end if;
    else
      if ((fpu_operands.rs1_class(fp_class_neg_zero_c) = '1') and (fpu_operands.rs2_class(fp_class_pos_zero_c) = '1')) then
        cond_v(0) := ctrl_i.ir_funct3(0);
      elsif ((fpu_operands.rs1_class(fp_class_pos_zero_c) = '1') and (fpu_operands.rs2_class(fp_class_neg_zero_c) = '1')) then
        cond_v(0) := not ctrl_i.ir_funct3(0);
      else -- "normal= comparison
        cond_v(0) := not (comp_less_ff xor ctrl_i.ir_funct3(0)); -- min/max select
      end if;
    end if;

    -- number NaN check --
    cond_v(2) := fpu_operands.rs1_class(fp_class_snan_c) or fpu_operands.rs1_class(fp_class_qnan_c);
    cond_v(1) := fpu_operands.rs2_class(fp_class_snan_c) or fpu_operands.rs2_class(fp_class_qnan_c);

    -- exceptions --
    -- Assume no exceptions
    fu_min_max.flags <= (others => '0');
    -- if one of the operands is sNAN) the compare operation must signal NV per 754 2019 chapter 9.6
    if ((fpu_operands.rs1_class(fp_class_snan_c) or fpu_operands.rs2_class(fp_class_snan_c)) = '1') then
      fu_min_max.flags(fp_exc_nv_c) <= '1';
    end if;

    -- data output --
    case cond_v is
      when "000"         => fu_min_max.result <= fpu_operands.rs1;
      when "001"         => fu_min_max.result <= fpu_operands.rs2;
      when "010" | "011" => fu_min_max.result <= fpu_operands.rs1; -- if one input is NaN output the non-NaN one
      when "100" | "101" => fu_min_max.result <= fpu_operands.rs2; -- if one input is NaN output the non-NaN one
      when others        => fu_min_max.result <= fp_single_qnan_c; -- output quiet NaN if both inputs are NaN
    end case;
  end process min_max_select;

  -- latency --
  -- -> done in "float_comparator"

  -- Convert: Float to [unsigned] Integer (FCVT.S.W) ----------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_fpu_f2i_inst: neorv32_cpu_cp_fpu_f2i
  generic map (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT => FPU_SUBNORMAL_SUPPORT -- Implemented sub-normal support, default false
  )
  port map (
    -- control --
    clk_i      => clk_i,                          -- global clock, rising edge
    rstn_i     => rstn_i,                         -- global reset, low-active, async
    start_i    => fu_conv_f2i.start,              -- trigger operation
    abort_i    => ctrl_i.cpu_trap,                -- abort current operation
    rmode_i    => fpu_operands.frm,               -- rounding mode
    funct_i    => ctrl_i.ir_funct12(0),           -- 0=signed, 1=unsigned
    -- input --
    sign_i     => fpu_operands.rs1(31),           -- sign
    exponent_i => fpu_operands.rs1(30 downto 23), -- exponent
    mantissa_i => fpu_operands.rs1(22 downto 0),  -- mantissa
    class_i    => fpu_operands.rs1_class,         -- operand class
    -- output --
    result_o   => fu_conv_f2i.result,             -- integer result
    flags_o    => fu_conv_f2i.flags,              -- exception flags
    done_o     => fu_conv_f2i.done                -- operation done
  );


  -- Sign-Injection (FSGNJ) -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sign_injector: process(ctrl_i, fpu_operands, rs1_i)
  begin
    case ctrl_i.ir_funct3(1 downto 0) is
      when "00"   => fu_sign_inject.result(31) <= fpu_operands.rs2(31); -- FSGNJ
      when "01"   => fu_sign_inject.result(31) <= not fpu_operands.rs2(31); -- FSGNJN
      when "10"   => fu_sign_inject.result(31) <= fpu_operands.rs1(31) xor fpu_operands.rs2(31); -- FSGNJX
      when others => fu_sign_inject.result(31) <= fpu_operands.rs2(31); -- undefined
    end case;
    -- if we do not have subnormal support we need to use the input operand and not the
    -- converted operand
    if (not FPU_SUBNORMAL_SUPPORT) then
      fu_sign_inject.result(30 downto 0) <= rs1_i(30 downto 0);
    else
      fu_sign_inject.result(30 downto 0) <= fpu_operands.rs1(30 downto 0);
    end if;
    fu_sign_inject.flags <= (others => '0'); -- does not generate flags
  end process sign_injector;

  -- latency --
  fu_sign_inject.done <= fu_sign_inject.start;


  -- Convert: [unsigned] Integer to Float (FCVT.W.S) ----------------------------------------
  -- -------------------------------------------------------------------------------------------
  convert_i2f: process(rstn_i, clk_i)
  begin
    -- this process only computes the absolute input value
    -- the actual conversion is done by the normalizer
    if (rstn_i = '0') then
      fu_conv_i2f.result <= (others => '0');
      fu_conv_i2f.sign   <= '0';
      fu_conv_i2f.done   <= '0';
    elsif rising_edge(clk_i) then
      if (ctrl_i.ir_funct12(0) = '0') and (rs1_i(31) = '1') then -- convert signed integer
        fu_conv_i2f.result <= std_ulogic_vector(0 - unsigned(rs1_i));
        fu_conv_i2f.sign   <= rs1_i(31); -- original sign
      else -- convert unsigned integer
        fu_conv_i2f.result <= rs1_i;
        fu_conv_i2f.sign   <= '0';
      end if;
      fu_conv_i2f.done <= fu_conv_i2f.start; -- actual conversion is done by the normalizer unit
    end if;
  end process convert_i2f;


  -- Multiplier Core (FMUL) -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  multiplier_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      multiplier.opa     <= (others => '0');
      multiplier.opb     <= (others => '0');
      multiplier.buf_ff  <= (others => '0');
      multiplier.product <= (others => '0');
      multiplier.sign    <= '0';
      multiplier.exp_res <= (others => '0');
      multiplier.flags   <= (others => '0');
      multiplier.latency <= (others => '0');
    elsif rising_edge(clk_i) then
      -- multiplier core --
      -- if the inputs to the multiplier is +/- zero or +/- denorm the result will always be +/- zero
      if ((fpu_operands.rs1_class(fp_class_pos_zero_c)   or fpu_operands.rs1_class(fp_class_neg_zero_c)   or
           fpu_operands.rs2_class(fp_class_pos_zero_c)   or fpu_operands.rs2_class(fp_class_neg_zero_c)   or
           fpu_operands.rs1_class(fp_class_pos_denorm_c) or fpu_operands.rs1_class(fp_class_neg_denorm_c) or
           fpu_operands.rs2_class(fp_class_pos_denorm_c) or fpu_operands.rs2_class(fp_class_neg_denorm_c)) = '1') then
        if (multiplier.start = '1') then
          -- the result will be 0 so force it to be 0
          multiplier.product <= (others => '0');
          multiplier.exp_res <= (others => '0');
        end if;
      else
        if (multiplier.start = '1') then -- remove buffer?
          multiplier.opa <= unsigned('1' & fpu_operands.rs1(22 downto 0)); -- append hidden one
          multiplier.opb <= unsigned('1' & fpu_operands.rs2(22 downto 0)); -- append hidden one
        end if;
        multiplier.buf_ff  <= multiplier.opa * multiplier.opb;
        multiplier.product <= std_ulogic_vector(multiplier.buf_ff(47 downto 0)); -- let the register balancing do the magic here
        multiplier.exp_res <= std_ulogic_vector(unsigned('0' & multiplier.exp_sum) - 127);
      end if;
      multiplier.sign <= fpu_operands.rs1(31) xor fpu_operands.rs2(31); -- resulting sign

      -- exponent computation --
      -- assume we are exact and the operation hasn't over/under flown
      multiplier.flags(fp_exc_of_c) <= '0';
      multiplier.flags(fp_exc_uf_c) <= '0';
      multiplier.flags(fp_exc_nx_c) <= '0';

      -- Multiplier exception handling
      -- Check that one operand is not inf or NAN before potentially setting OF, UF, and NX flags
      if ((fpu_operands.rs1_class(fp_class_pos_inf_c) or fpu_operands.rs2_class(fp_class_pos_inf_c) or
           fpu_operands.rs1_class(fp_class_neg_inf_c) or fpu_operands.rs2_class(fp_class_neg_inf_c) or
           fpu_operands.rs1_class(fp_class_snan_c)    or fpu_operands.rs2_class(fp_class_snan_c)    or
           fpu_operands.rs1_class(fp_class_qnan_c)    or fpu_operands.rs2_class(fp_class_qnan_c)) = '0') then
        if (multiplier.exp_res(multiplier.exp_res'left) = '1') then -- underflow (exp_res is "negative")
          multiplier.flags(fp_exc_of_c) <= '0';
          multiplier.flags(fp_exc_uf_c) <= '1';
          -- when over or underflow is set the result is also inexact
          multiplier.flags(fp_exc_nx_c) <= '1';
        elsif (multiplier.exp_res(multiplier.exp_res'left-1) = '1') then -- overflow
          multiplier.flags(fp_exc_of_c) <= '1';
          multiplier.flags(fp_exc_uf_c) <= '0';
          -- when over or underflow is set the result is also inexact
          multiplier.flags(fp_exc_nx_c) <= '1';
        end if;
      end if;

      -- invalid operation --
      -- Any multiplication between +/- inf and +/- zero is a not valid operation
      -- Any multiplication with sNAN is not a valid operation
      -- If subnormals are flushed to zero we need to treat them as zero for exception handling
      if (not FPU_SUBNORMAL_SUPPORT) then
        multiplier.flags(fp_exc_nv_c) <=
          ((fpu_operands.rs1_class(fp_class_snan_c)       or fpu_operands.rs2_class(fp_class_snan_c))) or -- mul(sNAN, X) or mul(X, sNAN)
          ((fpu_operands.rs1_class(fp_class_pos_denorm_c) or fpu_operands.rs1_class(fp_class_neg_denorm_c)) and
           (fpu_operands.rs2_class(fp_class_pos_inf_c)    or fpu_operands.rs2_class(fp_class_neg_inf_c))) or -- mul(+/-denorm, +/-inf)
          ((fpu_operands.rs1_class(fp_class_pos_inf_c)    or fpu_operands.rs1_class(fp_class_neg_inf_c)) and
           (fpu_operands.rs2_class(fp_class_pos_denorm_c) or fpu_operands.rs2_class(fp_class_neg_denorm_c))) or -- mul(+/-inf, +/-denorm)
          ((fpu_operands.rs1_class(fp_class_pos_zero_c)   or fpu_operands.rs1_class(fp_class_neg_zero_c)) and
           (fpu_operands.rs2_class(fp_class_pos_inf_c)    or fpu_operands.rs2_class(fp_class_neg_inf_c))) or -- mul(+/-zero, +/-inf)
          ((fpu_operands.rs1_class(fp_class_pos_inf_c)    or fpu_operands.rs1_class(fp_class_neg_inf_c)) and
           (fpu_operands.rs2_class(fp_class_pos_zero_c)   or fpu_operands.rs2_class(fp_class_neg_zero_c))); -- mul(+/-inf, +/-zero)
      else
        multiplier.flags(fp_exc_nv_c) <=
          ((fpu_operands.rs1_class(fp_class_pos_zero_c) or fpu_operands.rs1_class(fp_class_neg_zero_c)) and
           (fpu_operands.rs2_class(fp_class_pos_inf_c)  or fpu_operands.rs2_class(fp_class_neg_inf_c))) or -- mul(+/-zero, +/-inf)
          ((fpu_operands.rs1_class(fp_class_pos_inf_c)  or fpu_operands.rs1_class(fp_class_neg_inf_c)) and
           (fpu_operands.rs2_class(fp_class_pos_zero_c) or fpu_operands.rs2_class(fp_class_neg_zero_c))); -- mul(+/-inf, +/-zero)
      end if;

      -- unused exception flags --
      multiplier.flags(fp_exc_dz_c) <= '0'; -- division by zero: not possible here

      -- latency shift register --
      multiplier.latency <= multiplier.latency(multiplier.latency'left-1 downto 0) & multiplier.start;
    end if;
  end process multiplier_core;

  -- exponent sum --
  multiplier.exp_sum <= std_ulogic_vector(unsigned('0' & fpu_operands.rs1(30 downto 23)) + unsigned('0' & fpu_operands.rs2(30 downto 23)));

  -- latency --
  multiplier.start <= fu_mul.start;
  multiplier.done  <= multiplier.latency(multiplier.latency'left);
  fu_mul.done      <= multiplier.done;


  -- result class --
  multiplier_class_core: process(rstn_i, clk_i)
    variable a_pos_norm_v, a_neg_norm_v, b_pos_norm_v, b_neg_norm_v : std_ulogic;
    variable a_pos_subn_v, a_neg_subn_v, b_pos_subn_v, b_neg_subn_v : std_ulogic;
    variable a_pos_zero_v, a_neg_zero_v, b_pos_zero_v, b_neg_zero_v : std_ulogic;
    variable a_pos_inf_v,  a_neg_inf_v,  b_pos_inf_v,  b_neg_inf_v  : std_ulogic;
    variable a_snan_v,     a_qnan_v,     b_snan_v,     b_qnan_v     : std_ulogic;
  begin
    if (rstn_i = '0') then
      multiplier.res_class <= (others => '0');
    elsif rising_edge(clk_i) then
      -- minions --
      a_pos_norm_v := fpu_operands.rs1_class(fp_class_pos_norm_c);   b_pos_norm_v := fpu_operands.rs2_class(fp_class_pos_norm_c);
      a_neg_norm_v := fpu_operands.rs1_class(fp_class_neg_norm_c);   b_neg_norm_v := fpu_operands.rs2_class(fp_class_neg_norm_c);
      a_pos_subn_v := fpu_operands.rs1_class(fp_class_pos_denorm_c); b_pos_subn_v := fpu_operands.rs2_class(fp_class_pos_denorm_c);
      a_neg_subn_v := fpu_operands.rs1_class(fp_class_neg_denorm_c); b_neg_subn_v := fpu_operands.rs2_class(fp_class_neg_denorm_c);
      a_pos_zero_v := fpu_operands.rs1_class(fp_class_pos_zero_c);   b_pos_zero_v := fpu_operands.rs2_class(fp_class_pos_zero_c);
      a_neg_zero_v := fpu_operands.rs1_class(fp_class_neg_zero_c);   b_neg_zero_v := fpu_operands.rs2_class(fp_class_neg_zero_c);
      a_pos_inf_v  := fpu_operands.rs1_class(fp_class_pos_inf_c);    b_pos_inf_v  := fpu_operands.rs2_class(fp_class_pos_inf_c);
      a_neg_inf_v  := fpu_operands.rs1_class(fp_class_neg_inf_c);    b_neg_inf_v  := fpu_operands.rs2_class(fp_class_neg_inf_c);
      a_snan_v     := fpu_operands.rs1_class(fp_class_snan_c);       b_snan_v     := fpu_operands.rs2_class(fp_class_snan_c);
      a_qnan_v     := fpu_operands.rs1_class(fp_class_qnan_c);       b_qnan_v     := fpu_operands.rs2_class(fp_class_qnan_c);

      -- +normal --
      multiplier.res_class(fp_class_pos_norm_c) <=
        (a_pos_norm_v and b_pos_norm_v) or -- +norm * +norm
        (a_neg_norm_v and b_neg_norm_v);   -- -norm * -norm
      -- -normal --
      multiplier.res_class(fp_class_neg_norm_c) <=
        (a_pos_norm_v and b_neg_norm_v) or -- +norm * -norm
        (a_neg_norm_v and b_pos_norm_v);   -- -norm * +norm

      -- +infinity --
      -- If we flush denorms to zero then we meed tp remove denorms from the list
      if (not FPU_SUBNORMAL_SUPPORT) then
        multiplier.res_class(fp_class_pos_inf_c) <=
          (a_pos_inf_v  and b_pos_inf_v)  or -- +inf    * +inf
          (a_neg_inf_v  and b_neg_inf_v)  or -- -inf    * -inf
          (a_pos_norm_v and b_pos_inf_v)  or -- +norm   * +inf
          (a_pos_inf_v  and b_pos_norm_v) or -- +inf    * +norm
          (a_neg_norm_v and b_neg_inf_v)  or -- -norm   * -inf
          (a_neg_inf_v  and b_neg_norm_v);   -- -inf    * -norm
      else
        multiplier.res_class(fp_class_pos_inf_c) <=
          (a_pos_inf_v  and b_pos_inf_v)  or -- +inf    * +inf
          (a_neg_inf_v  and b_neg_inf_v)  or -- -inf    * -inf
          (a_pos_norm_v and b_pos_inf_v)  or -- +norm   * +inf
          (a_pos_inf_v  and b_pos_norm_v) or -- +inf    * +norm
          (a_neg_norm_v and b_neg_inf_v)  or -- -norm   * -inf
          (a_neg_inf_v  and b_neg_norm_v) or -- -inf    * -norm
          (a_neg_subn_v and b_neg_inf_v)  or -- -denorm * -inf
          (a_neg_inf_v  and b_neg_subn_v);   -- -inf    * -denorm
      end if;
      -- -infinity --
      -- If we flush denorms to zero then we meed tp remove denorms from the list
      if (not FPU_SUBNORMAL_SUPPORT) then
        multiplier.res_class(fp_class_neg_inf_c) <=
          (a_pos_inf_v  and b_neg_inf_v)  or -- +inf    * -inf
          (a_neg_inf_v  and b_pos_inf_v)  or -- -inf    * +inf
          (a_pos_norm_v and b_neg_inf_v)  or -- +norm   * -inf
          (a_neg_inf_v  and b_pos_norm_v) or -- -inf    * +norm
          (a_neg_norm_v and b_pos_inf_v)  or -- -norm   * +inf
          (a_pos_inf_v  and b_neg_norm_v);   -- +inf    * -norm
      else
        multiplier.res_class(fp_class_neg_inf_c) <=
          (a_pos_inf_v  and b_neg_inf_v)  or -- +inf    * -inf
          (a_neg_inf_v  and b_pos_inf_v)  or -- -inf    * +inf
          (a_pos_norm_v and b_neg_inf_v)  or -- +norm   * -inf
          (a_neg_inf_v  and b_pos_norm_v) or -- -inf    * +norm
          (a_neg_norm_v and b_pos_inf_v)  or -- -norm   * +inf
          (a_pos_inf_v  and b_neg_norm_v) or -- +inf    * -norm
          (a_pos_subn_v and b_neg_inf_v)  or -- +denorm * -inf
          (a_neg_inf_v  and b_pos_subn_v) or -- -inf    * +de-norm
          (a_neg_subn_v and b_pos_inf_v)  or -- -denorm * +inf
          (a_pos_inf_v  and b_neg_subn_v);   -- +inf    * -de-norm
      end if;

      -- +zero --
      -- If we flush denorms to zero then
      if (not FPU_SUBNORMAL_SUPPORT) then
        multiplier.res_class(fp_class_pos_zero_c) <=
          (a_pos_zero_v and b_pos_zero_v) or -- +zero   * +zero
          (a_pos_zero_v and b_pos_norm_v) or -- +zero   * +norm
          (a_pos_subn_v and b_pos_norm_v) or -- +denorm * +norm
          (a_pos_zero_v and b_pos_subn_v) or -- +zero   * +denorm
          (a_neg_zero_v and b_neg_zero_v) or -- -zero   * -zero
          (a_neg_zero_v and b_neg_norm_v) or -- -zero   * -norm
          (a_neg_subn_v and b_neg_norm_v) or -- -denrom * -norm
          (a_neg_zero_v and b_neg_subn_v) or -- -zero   * -denorm
          (a_pos_norm_v and b_pos_zero_v) or -- +norm   * +zero
          (a_pos_norm_v and b_pos_subn_v) or -- +norm   * +denorm
          (a_pos_subn_v and b_pos_zero_v) or -- +denorm * +zero
          (a_neg_norm_v and b_neg_zero_v) or -- -norm   * -zero
          (a_neg_norm_v and b_neg_subn_v) or -- -norm   * -denorm
          (a_neg_subn_v and b_neg_zero_v);   -- -denorm * -zero
      else
        multiplier.res_class(fp_class_pos_zero_c) <=
          (a_pos_zero_v and b_pos_zero_v) or -- +zero   * +zero
          (a_pos_zero_v and b_pos_norm_v) or -- +zero   * +norm
          (a_pos_zero_v and b_pos_subn_v) or -- +zero   * +denorm
          (a_neg_zero_v and b_neg_zero_v) or -- -zero   * -zero
          (a_neg_zero_v and b_neg_norm_v) or -- -zero   * -norm
          (a_neg_zero_v and b_neg_subn_v) or -- -zero   * -denorm
          (a_pos_norm_v and b_pos_zero_v) or -- +norm   * +zero
          (a_pos_subn_v and b_pos_zero_v) or -- +denorm * +zero
          (a_neg_norm_v and b_neg_zero_v) or -- -norm   * -zero
          (a_neg_subn_v and b_neg_zero_v);   -- -denorm * -zero
      end if;

      -- -zero --
      -- If we flush denorms to zero then
      if (not FPU_SUBNORMAL_SUPPORT) then
        multiplier.res_class(fp_class_neg_zero_c) <=
          (a_pos_zero_v and b_neg_zero_v) or -- +zero   * -zero
          (a_pos_zero_v and b_neg_norm_v) or -- +zero   * -norm
          (a_pos_subn_v and b_neg_norm_v) or -- +denom  * -norm
          (a_pos_zero_v and b_neg_subn_v) or -- +zero   * -denorm
          (a_neg_zero_v and b_pos_zero_v) or -- -zero   * +zero
          (a_neg_zero_v and b_pos_norm_v) or -- -zero   * +norm
          (a_neg_subn_v and b_pos_norm_v) or -- -denorm * +norm
          (a_neg_zero_v and b_pos_subn_v) or -- -zero   * +denorm
          (a_neg_norm_v and b_pos_zero_v) or -- -norm   * +zero
          (a_neg_norm_v and b_pos_subn_v) or -- -norm   * +denorm
          (a_neg_subn_v and b_pos_zero_v) or -- -denorm * +zero
          (a_pos_norm_v and b_neg_zero_v) or -- +norm   * -zero
          (a_pos_norm_v and b_neg_subn_v) or -- +norm   * -denorm
          (a_pos_subn_v and b_neg_zero_v);   -- +denorm * -zero
      else
        multiplier.res_class(fp_class_neg_zero_c) <=
          (a_pos_zero_v and b_neg_zero_v) or -- +zero   * -zero
          (a_pos_zero_v and b_neg_norm_v) or -- +zero   * -norm
          (a_pos_zero_v and b_neg_subn_v) or -- +zero   * -denorm
          (a_neg_zero_v and b_pos_zero_v) or -- -zero   * +zero
          (a_neg_zero_v and b_pos_norm_v) or -- -zero   * +norm
          (a_neg_zero_v and b_pos_subn_v) or -- -zero   * +denorm
          (a_neg_norm_v and b_pos_zero_v) or -- -norm   * +zero
          (a_neg_subn_v and b_pos_zero_v) or -- -denorm * +zero
          (a_pos_norm_v and b_neg_zero_v) or -- +norm   * -zero
          (a_pos_subn_v and b_neg_zero_v);   -- +denorm * -zero
      end if;

      -- sNaN --
      multiplier.res_class(fp_class_snan_c) <= (a_snan_v or b_snan_v); -- any input is sNaN
      -- qNaN --
      -- If we flush denorms to zero then
      if (not FPU_SUBNORMAL_SUPPORT) then
        multiplier.res_class(fp_class_qnan_c) <=
          (a_snan_v or b_snan_v) or -- any input is sNaN
          (a_qnan_v or b_qnan_v) or -- any input is qNaN
          ((a_pos_inf_v  or a_neg_inf_v)  and (b_pos_zero_v or b_neg_zero_v)) or -- +/-inf * +/-zero
          ((a_pos_zero_v or a_neg_zero_v) and (b_pos_inf_v  or b_neg_inf_v))  or -- +/-zero * +/-inf
          ((a_pos_inf_v  or a_neg_inf_v)  and (b_pos_subn_v or b_neg_subn_v)) or -- +/-inf * +/-denorm
          ((a_pos_subn_v or a_neg_subn_v) and (b_pos_inf_v  or b_neg_inf_v));    -- +/-denorm * +/-inf
      else
        multiplier.res_class(fp_class_qnan_c) <=
          (a_snan_v or b_snan_v) or -- any input is sNaN
          (a_qnan_v or b_qnan_v) or -- any input is qNaN
          ((a_pos_inf_v  or a_neg_inf_v)  and (b_pos_zero_v or b_neg_zero_v)) or -- +/-inf * +/-zero
          ((a_pos_zero_v or a_neg_zero_v) and (b_pos_inf_v  or b_neg_inf_v));    -- +/-zero * +/-inf
      end if;

      -- subnormal result --
      multiplier.res_class(fp_class_pos_denorm_c) <= '0'; -- is evaluated by the normalizer
      multiplier.res_class(fp_class_neg_denorm_c) <= '0'; -- is evaluated by the normalizer
    end if;
  end process multiplier_class_core;

  -- unused --
  fu_mul.result <= (others => '0');
  fu_mul.flags  <= (others => '0');


  -- Adder/Subtractor Core (FADD, FSUB) -----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  adder_subtractor_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      addsub.latency            <= (others => '0');
      addsub.exp_comp           <= (others => '0');
      addsub.man_sreg           <= (others => '0');
      addsub.exp_cnt            <= (others => '0');
      addsub.man_g_ext          <= '0';
      addsub.man_r_ext          <= '0';
      addsub.man_s_ext          <= '0';
      addsub.man_comp           <= '0';
      addsub.add_stage          <= (others => '0');
      addsub.res_sign           <= '0';
      addsub.flags(fp_exc_nv_c) <= '0';
    elsif rising_edge(clk_i) then
      -- arbitration / latency --
      if (ctrl_engine.state = S_IDLE) then -- hacky "reset"
        addsub.latency <= (others => '0');
      else
        addsub.latency(0) <= addsub.start; -- input comparator delay
        if (addsub.latency(0) = '1') then
          addsub.latency(1) <= '1';
          addsub.latency(2) <= '0';
        elsif (addsub.exp_cnt(7 downto 0) = addsub.large_exp) then -- radix point not yet aligned
          addsub.latency(1) <= '0';
          addsub.latency(2) <= addsub.latency(1) and (not addsub.latency(0)); -- "shift done"
        end if;
        addsub.latency(3) <= addsub.latency(2); -- adder stage
        addsub.latency(4) <= addsub.latency(3); -- final stage
      end if;

      -- exponent check: find smaller number (radix-offset-only) --
      if (unsigned(fpu_operands.rs1(30 downto 23)) < unsigned(fpu_operands.rs2(30 downto 23))) then
        addsub.exp_comp(0) <= '1'; -- rs1 < rs2
      else
        addsub.exp_comp(0) <= '0'; -- rs1 >= rs2
      end if;
      if (unsigned(fpu_operands.rs1(30 downto 23)) = unsigned(fpu_operands.rs2(30 downto 23))) then
        addsub.exp_comp(1) <= '1'; -- rs1 == rs2
      else -- rs1 != rs2
        addsub.exp_comp(1) <= '0';
      end if;

      -- shift right small mantissa to align radix point --
      if (addsub.latency(0) = '1') then
        -- check for denorm support
        if (FPU_SUBNORMAL_SUPPORT) then
          if ((fpu_operands.rs1_class(fp_class_pos_zero_c) or fpu_operands.rs2_class(fp_class_pos_zero_c) or
               fpu_operands.rs1_class(fp_class_neg_zero_c) or fpu_operands.rs2_class(fp_class_neg_zero_c)) = '0') then -- no input is zero
            addsub.man_sreg <= addsub.small_man;
          else
            addsub.man_sreg <= (others => '0');
          end if;
        else
          -- also use denorm for the check as we flush denorms.
          if ((fpu_operands.rs1_class(fp_class_pos_zero_c)   or fpu_operands.rs2_class(fp_class_pos_zero_c)   or
               fpu_operands.rs1_class(fp_class_neg_zero_c)   or fpu_operands.rs2_class(fp_class_neg_zero_c)   or
               fpu_operands.rs1_class(fp_class_pos_denorm_c) or fpu_operands.rs2_class(fp_class_pos_denorm_c) or
               fpu_operands.rs1_class(fp_class_neg_denorm_c) or fpu_operands.rs2_class(fp_class_neg_denorm_c)) = '0') then -- no input is zero
            addsub.man_sreg <= addsub.small_man;
          else
            addsub.man_sreg <= (others => '0');
          end if;
        end if;
        addsub.exp_cnt   <= '0' & addsub.small_exp;
        addsub.man_g_ext <= '0';
        addsub.man_r_ext <= '0';
        addsub.man_s_ext <= '0';
      elsif (addsub.exp_cnt(7 downto 0) /= addsub.large_exp) then -- shift right until same magnitude
        -- Trip: Exponent difference larger than mantissa width + 3
        -- When the difference between large_exp - small_exp is larger than 27
        -- the normalizer will always shift the smaller mantissa to 0.
        -- Catch: Set the smaller mantissa to 0 and the s_ext to '1' end go to next step.
        -- Note: The comparison is 24 mantissa bits 1.23 + 3 underflow bits.
        -- The +3 is to account for the grs underflow bits, could be set to +2 as we are always setting s to 1
        if (unsigned(addsub.large_exp(7 downto 0)) - unsigned(addsub.small_exp(7 downto 0))) > 27 then
          addsub.man_sreg  <= (others => '0');
          addsub.man_g_ext <= '0';
          addsub.man_r_ext <= '0';
          -- set s_ext to 1 as it will always be 1 from the implied 1 being shifted out.
          addsub.man_s_ext <= '1';
          -- if man_sreg is 0 set s_ext to 0 as there is no 1 that will be shifted out.
          if (to_integer(unsigned(addsub.man_sreg)) = 0) then
            addsub.man_s_ext <= '0';
          end if;
          addsub.exp_cnt(7 downto 0) <= addsub.large_exp(7 downto 0);
        else
          addsub.man_sreg  <= '0' & addsub.man_sreg(addsub.man_sreg'left downto 1);
          addsub.man_g_ext <= addsub.man_sreg(0);
          addsub.man_r_ext <= addsub.man_g_ext;
          addsub.man_s_ext <= addsub.man_s_ext or addsub.man_r_ext; -- sticky bit
          addsub.exp_cnt   <= std_ulogic_vector(unsigned(addsub.exp_cnt) + 1);
        end if;
      end if;

      -- mantissa check: find smaller number (magnitude-only) --
      if (unsigned(addsub.man_sreg) <= unsigned(addsub.large_man)) then
        addsub.man_comp <= '1';
      else
        addsub.man_comp <= '0';
      end if;

      -- actual addition/subtraction (incl. overflow) --
      if ((ctrl_i.ir_funct12(7) xor (fpu_operands.rs1(31) xor fpu_operands.rs2(31))) = '0') then -- add
        addsub.add_stage <= std_ulogic_vector(unsigned('0' & addsub.man_l) + unsigned('0' & addsub.man_s));
      else -- sub
        addsub.add_stage <= std_ulogic_vector(unsigned('0' & addsub.man_l) - unsigned('0' & addsub.man_s));
      end if;

      -- result sign --
      if (ctrl_i.ir_funct12(7) = '0') then -- add
        if (fpu_operands.rs1(31) = fpu_operands.rs2(31)) then -- identical signs
          addsub.res_sign <= fpu_operands.rs1(31);
        else -- different signs
          -- if the result is not 0.0 set the sign normally
          if ((to_integer(unsigned(addsub.add_stage))) /= 0 ) then
            if (addsub.exp_comp(1) = '1') then -- exp are equal (also check relation of mantissas)
              addsub.res_sign <= fpu_operands.rs1(31) xor (not addsub.man_comp);
            else
              addsub.res_sign <= fpu_operands.rs1(31) xor addsub.exp_comp(0);
            end if;
          else
            --  roundTowardNegative; under that attribute, the sign of an exact zero sum (or difference) shall be -0
            if (fpu_operands.frm = "010") then -- round down (towards -infinity)
              addsub.res_sign <= '1'; -- set the sign to 0 to generate a +0.0 result
            else
              addsub.res_sign <= '0'; -- set the sign to 0 to generate a +0.0 result
            end if;
          end if;
        end if;
      else -- sub
        -- identical signs
        -- if the result is not 0.0 set the sign normally
        if (fpu_operands.rs1(31) = fpu_operands.rs2(31)) then
          if ((to_integer(unsigned(addsub.add_stage))) /= 0 ) then
            if (addsub.exp_comp(1) = '1') then -- exp are equal (also check relation of mantissas)
              addsub.res_sign <= fpu_operands.rs1(31) xor (not addsub.man_comp);
            else
              addsub.res_sign <= fpu_operands.rs1(31) xor addsub.exp_comp(0);
            end if;
          else
            --  roundTowardNegative; under that attribute, the sign of an exact zero sum (or difference) shall be -0
            if (fpu_operands.frm = "010") then -- round down (towards -infinity)
              addsub.res_sign <= '1'; -- set the sign to 0 to generate a +0.0 result
            else
              addsub.res_sign <= '0'; -- set the sign to 0 to generate a +0.0 result
            end if;
          end if;
        else -- different signs
          addsub.res_sign <= fpu_operands.rs1(31);
        end if;
      end if;

      -- Infinities decoder ring
      -- fadd:
      -- Rs1 \ Rs2 | +inf | -inf | <- Rs2
      -- --------------------------------
      --      +inf | +inf |  NV  |
      -- --------------------------------
      --      -inf |  NV  | -inf |
      -- --------------------------------
      --     ^
      --     |
      --    Rs1
      --
      -- fsub:
      -- Rs1 \ Rs2 | +inf | -inf | <- Rs2
      -- --------------------------------
      --      +inf |  NV  | +inf |
      -- --------------------------------
      --      -inf | -inf |  NV  |
      -- --------------------------------
      --     ^
      --     |
      --    Rs1
      -- Assume the operation is valid
      addsub.flags(fp_exc_nv_c) <= '0';
      if (ctrl_i.ir_funct12(7) = '0') then -- add
        -- Do we have 2 infinities of opposite sign?
        if (((fpu_operands.rs1_class(fp_class_pos_inf_c) and fpu_operands.rs2_class(fp_class_neg_inf_c)) or
             (fpu_operands.rs1_class(fp_class_neg_inf_c) and fpu_operands.rs2_class(fp_class_pos_inf_c))) = '1') then
          addsub.flags(fp_exc_nv_c) <= '1';
        end if;
      else -- sub
        -- Do we have 2 infinities of same sign?
        if (((fpu_operands.rs1_class(fp_class_pos_inf_c) and fpu_operands.rs2_class(fp_class_pos_inf_c)) or
             (fpu_operands.rs1_class(fp_class_neg_inf_c) and fpu_operands.rs2_class(fp_class_neg_inf_c))) = '1') then
          addsub.flags(fp_exc_nv_c) <= '1';
        end if;
      end if;
    end if;
  end process adder_subtractor_core;

  -- exceptions - unused --
  addsub.flags(fp_exc_dz_c) <= '0'; -- division by zero -> not possible
  addsub.flags(fp_exc_of_c) <= '0'; -- not possible here (but may occur in normalizer)
  addsub.flags(fp_exc_uf_c) <= '0'; -- not possible here (but may occur in normalizer)
  addsub.flags(fp_exc_nx_c) <= '0'; -- not possible here (but may occur in normalizer)

  -- exponent check: find smaller number (magnitude-only) --
  addsub.small_exp <=        fpu_operands.rs1(30 downto 23)  when (addsub.exp_comp(0) = '1') else        fpu_operands.rs2(30 downto 23);
  addsub.large_exp <=        fpu_operands.rs2(30 downto 23)  when (addsub.exp_comp(0) = '1') else        fpu_operands.rs1(30 downto 23);
  addsub.small_man <= ('1' & fpu_operands.rs1(22 downto 0))  when (addsub.exp_comp(0) = '1') else ('1' & fpu_operands.rs2(22 downto 0));
  addsub.large_man <= ('1' & fpu_operands.rs2(22 downto 0))  when (addsub.exp_comp(0) = '1') else ('1' & fpu_operands.rs1(22 downto 0));

  -- mantissa check: find smaller number (magnitude-only) --
  addsub.man_s <= (addsub.man_sreg & addsub.man_g_ext & addsub.man_r_ext & addsub.man_s_ext) when (addsub.man_comp = '1') else (addsub.large_man & "000");
  addsub.man_l <= (addsub.large_man & "000") when (addsub.man_comp = '1') else (addsub.man_sreg & addsub.man_g_ext & addsub.man_r_ext & addsub.man_s_ext);

  -- latency --
  addsub.start   <= fu_addsub.start;
  addsub.done    <= addsub.latency(addsub.latency'left);
  fu_addsub.done <= addsub.done;

  -- mantissa result --
  addsub.res_sum <= addsub.add_stage(27 downto 0);


  -- result class --
  adder_subtractor_class_core: process(rstn_i, clk_i)
    variable a_pos_norm_v, a_neg_norm_v, b_pos_norm_v, b_neg_norm_v : std_ulogic;
    variable a_pos_subn_v, a_neg_subn_v, b_pos_subn_v, b_neg_subn_v : std_ulogic;
    variable a_pos_zero_v, a_neg_zero_v, b_pos_zero_v, b_neg_zero_v : std_ulogic;
    variable a_pos_inf_v,  a_neg_inf_v,  b_pos_inf_v,  b_neg_inf_v  : std_ulogic;
    variable a_snan_v,     a_qnan_v,     b_snan_v,     b_qnan_v     : std_ulogic;
  begin
    if (rstn_i = '0') then
      addsub.res_class <= (others => '0');
    elsif rising_edge(clk_i) then
      -- minions --
      a_pos_norm_v := fpu_operands.rs1_class(fp_class_pos_norm_c); b_pos_norm_v := fpu_operands.rs2_class(fp_class_pos_norm_c);
      a_neg_norm_v := fpu_operands.rs1_class(fp_class_neg_norm_c); b_neg_norm_v := fpu_operands.rs2_class(fp_class_neg_norm_c);
      -- as we can now correctly classify subnormals we need to override the post-add class
      -- if we don't support subnormals as part of the add/sub circuit
      if (FPU_SUBNORMAL_SUPPORT) then
        a_pos_subn_v := fpu_operands.rs1_class(fp_class_pos_denorm_c); b_pos_subn_v := fpu_operands.rs2_class(fp_class_pos_denorm_c);
        a_neg_subn_v := fpu_operands.rs1_class(fp_class_neg_denorm_c); b_neg_subn_v := fpu_operands.rs2_class(fp_class_neg_denorm_c);
      else
        a_pos_subn_v := '0'; b_pos_subn_v := '0';
        a_neg_subn_v := '0'; b_neg_subn_v := '0';
      end if;
      if (FPU_SUBNORMAL_SUPPORT) then
        a_pos_zero_v := fpu_operands.rs1_class(fp_class_pos_zero_c); b_pos_zero_v := fpu_operands.rs2_class(fp_class_pos_zero_c);
        a_neg_zero_v := fpu_operands.rs1_class(fp_class_neg_zero_c); b_neg_zero_v := fpu_operands.rs2_class(fp_class_neg_zero_c);
      else
        a_pos_zero_v := fpu_operands.rs1_class(fp_class_pos_zero_c) or fpu_operands.rs1_class(fp_class_pos_denorm_c);
        b_pos_zero_v := fpu_operands.rs2_class(fp_class_pos_zero_c) or fpu_operands.rs2_class(fp_class_pos_denorm_c);
        a_neg_zero_v := fpu_operands.rs1_class(fp_class_neg_zero_c) or fpu_operands.rs1_class(fp_class_neg_denorm_c);
        b_neg_zero_v := fpu_operands.rs2_class(fp_class_neg_zero_c) or fpu_operands.rs2_class(fp_class_neg_denorm_c);
      end if;
      a_pos_inf_v := fpu_operands.rs1_class(fp_class_pos_inf_c); b_pos_inf_v := fpu_operands.rs2_class(fp_class_pos_inf_c);
      a_neg_inf_v := fpu_operands.rs1_class(fp_class_neg_inf_c); b_neg_inf_v := fpu_operands.rs2_class(fp_class_neg_inf_c);
      a_snan_v    := fpu_operands.rs1_class(fp_class_snan_c);    b_snan_v    := fpu_operands.rs2_class(fp_class_snan_c);
      a_qnan_v    := fpu_operands.rs1_class(fp_class_qnan_c);    b_qnan_v    := fpu_operands.rs2_class(fp_class_qnan_c);

      if (ctrl_i.ir_funct12(7) = '0') then -- addition
        -- +infinity --
        addsub.res_class(fp_class_pos_inf_c) <=
          (a_pos_inf_v  and b_pos_inf_v)  or -- +inf    + +inf
          (a_pos_inf_v  and b_pos_zero_v) or -- +inf    + +zero
          (a_pos_zero_v and b_pos_inf_v)  or -- +zero   + +inf
          (a_pos_inf_v  and b_neg_zero_v) or -- +inf    + -zero
          (a_neg_zero_v and b_pos_inf_v)  or -- -zero   + +inf
          --
          (a_pos_inf_v  and b_pos_norm_v) or -- +inf    + +norm
          (a_pos_norm_v and b_pos_inf_v)  or -- +norm   + +inf
          (a_pos_inf_v  and b_pos_subn_v) or -- +inf    + +denorm
          (a_pos_subn_v and b_pos_inf_v)  or -- +denorm + +inf
          --
          (a_pos_inf_v  and b_neg_norm_v) or -- +inf    + -norm
          (a_neg_norm_v and b_pos_inf_v)  or -- -norm   + +inf
          (a_pos_inf_v  and b_neg_subn_v) or -- +inf    + -denorm
          (a_neg_subn_v and b_pos_inf_v);    -- -denorm + +inf
        -- -infinity --
        addsub.res_class(fp_class_neg_inf_c) <=
          (a_neg_inf_v  and b_neg_inf_v)  or -- -inf    + -inf
          (a_neg_inf_v  and b_pos_zero_v) or -- -inf    + +zero
          (a_pos_zero_v and b_neg_inf_v)  or -- +zero   + -inf
          (a_neg_inf_v  and b_neg_zero_v) or -- -inf    + -zero
          (a_neg_zero_v and b_neg_inf_v)  or -- -zero   + -inf
          --
          (a_neg_inf_v  and b_pos_norm_v) or -- -inf    + +norm
          (a_pos_norm_v and b_neg_inf_v)  or -- +norm   + -inf
          (a_neg_inf_v  and b_neg_norm_v) or -- -inf    + -norm
          (a_neg_norm_v and b_neg_inf_v)  or -- -norm   + -inf
          --
          (a_neg_inf_v  and b_pos_subn_v) or -- -inf    + +denorm
          (a_pos_subn_v and b_neg_inf_v)  or -- +denorm + -inf
          (a_neg_inf_v  and b_neg_subn_v) or -- -inf    + -denorm
          (a_neg_subn_v and b_neg_inf_v);    -- -denorm + -inf

        -- +zero --
        addsub.res_class(fp_class_pos_zero_c) <=
          (a_pos_zero_v and b_pos_zero_v) or -- +zero + +zero
          (a_pos_zero_v and b_neg_zero_v) or -- +zero + -zero
          (a_neg_zero_v and b_pos_zero_v);   -- -zero + +zero
        -- -zero --
        addsub.res_class(fp_class_neg_zero_c) <=
          (a_neg_zero_v and b_neg_zero_v);   -- -zero + -zero

        -- qNaN --
        addsub.res_class(fp_class_qnan_c) <=
          (a_snan_v    or  b_snan_v)    or -- any input is sNaN
          (a_qnan_v    or  b_qnan_v)    or -- any input is qNaN
          (a_pos_inf_v and b_neg_inf_v) or -- +inf + -inf
          (a_neg_inf_v and b_pos_inf_v);   -- -inf + +inf

      else -- subtraction
        -- +infinity --
        addsub.res_class(fp_class_pos_inf_c) <=
          (a_pos_inf_v  and b_neg_inf_v)  or -- +inf    - -inf
          (a_pos_inf_v  and b_pos_zero_v) or -- +inf    - +zero
          (a_pos_inf_v  and b_neg_zero_v) or -- +inf    - -zero
          (a_pos_inf_v  and b_pos_norm_v) or -- +inf    - +norm
          (a_pos_inf_v  and b_pos_subn_v) or -- +inf    - +denorm
          (a_pos_inf_v  and b_neg_norm_v) or -- +inf    - -norm
          (a_pos_inf_v  and b_neg_subn_v) or -- +inf    - -denorm
          --
          (a_pos_zero_v and b_neg_inf_v)  or -- +zero   - -inf
          (a_neg_zero_v and b_neg_inf_v)  or -- -zero   - -inf
          --
          (a_pos_norm_v and b_neg_inf_v)  or -- +norm   - -inf
          (a_pos_subn_v and b_neg_inf_v)  or -- +denorm - -inf
          (a_neg_norm_v and b_neg_inf_v)  or -- -norm   - -inf
          (a_neg_subn_v and b_neg_inf_v);    -- -denorm - -inf
        -- -infinity --
        addsub.res_class(fp_class_neg_inf_c) <=
          (a_neg_inf_v  and b_pos_inf_v)  or -- -inf    - +inf
          (a_neg_inf_v  and b_pos_zero_v) or -- -inf    - +zero
          (a_neg_inf_v  and b_neg_zero_v) or -- -inf    - -zero
          (a_neg_inf_v  and b_pos_norm_v) or -- -inf    - +norm
          (a_neg_inf_v  and b_pos_subn_v) or -- -inf    - +denorm
          (a_neg_inf_v  and b_neg_norm_v) or -- -inf    - -norm
          (a_neg_inf_v  and b_neg_subn_v) or -- -inf    - -denorm
          --
          (a_pos_zero_v and b_pos_inf_v)  or -- +zero   - +inf
          (a_neg_zero_v and b_pos_inf_v)  or -- -zero   - +inf
          --
          (a_pos_norm_v and b_pos_inf_v)  or -- +norm   - +inf
          (a_pos_subn_v and b_pos_inf_v)  or -- +denorm - +inf
          (a_neg_norm_v and b_pos_inf_v)  or -- -norm   - +inf
          (a_neg_subn_v and b_pos_inf_v);    -- -denorm - +inf

        -- +zero --
        addsub.res_class(fp_class_pos_zero_c) <=
          (a_pos_zero_v and b_pos_zero_v) or -- +zero - +zero
          (a_pos_zero_v and b_neg_zero_v) or -- +zero - -zero
          (a_neg_zero_v and b_neg_zero_v);   -- -zero - -zero
        -- -zero --
        addsub.res_class(fp_class_neg_zero_c) <=
          (a_neg_zero_v and b_pos_zero_v);   -- -zero - +zero

        -- qNaN --
        addsub.res_class(fp_class_qnan_c) <=
          (a_snan_v    or  b_snan_v)    or -- any input is sNaN
          (a_qnan_v    or  b_qnan_v)    or -- any input is qNaN
          (a_pos_inf_v and b_pos_inf_v) or -- +inf - +inf
          (a_neg_inf_v and b_neg_inf_v);   -- -inf - -inf
      end if;

      -- normal --
      addsub.res_class(fp_class_pos_norm_c) <= (a_pos_norm_v or a_neg_norm_v) and (b_pos_norm_v or b_neg_norm_v); -- +/-norm +/- +-/norm [sign is irrelevant here]
      addsub.res_class(fp_class_neg_norm_c) <= (a_pos_norm_v or a_neg_norm_v) and (b_pos_norm_v or b_neg_norm_v); -- +/-norm +/- +-/norm [sign is irrelevant here]

      -- sNaN --
      addsub.res_class(fp_class_snan_c) <= (a_snan_v or b_snan_v); -- any input is sNaN

      -- subnormal result --
      addsub.res_class(fp_class_pos_denorm_c) <= '0'; -- is evaluated by the normalizer
      addsub.res_class(fp_class_neg_denorm_c) <= '0'; -- is evaluated by the normalizer
    end if;
  end process adder_subtractor_class_core;

  -- unused --
  fu_addsub.result <= (others => '0');
  fu_addsub.flags  <= (others => '0');


-- ****************************************************************************************************************************
-- FPU Core - Normalize & Round
-- ****************************************************************************************************************************

  -- Normalizer Input -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  normalizer_input_select: process(funct_ff, addsub, multiplier, fu_conv_i2f)
  begin
    case funct_ff is
      when op_addsub_c => -- addition/subtraction
        normalizer.mode      <= '0'; -- normalization
        normalizer.sign      <= addsub.res_sign;
        normalizer.xexp      <= addsub.exp_cnt;
        normalizer.xmantissa(47 downto 23) <= addsub.res_sum(27 downto 3);
        normalizer.xmantissa(22) <= addsub.res_sum(2);
        normalizer.xmantissa(21) <= addsub.res_sum(1);
        normalizer.xmantissa(20 downto 1) <= (others => '0');
        normalizer.xmantissa(0) <= addsub.res_sum(0);
        normalizer.class     <= addsub.res_class;
        normalizer.flags_in  <= addsub.flags;
        normalizer.start     <= addsub.done;
      when op_mul_c => -- multiplication
        normalizer.mode      <= '0'; -- normalization
        normalizer.sign      <= multiplier.sign;
        normalizer.xexp      <= '0' & multiplier.exp_res(7 downto 0);
        normalizer.xmantissa <= multiplier.product;
        normalizer.class     <= multiplier.res_class;
        normalizer.flags_in  <= multiplier.flags;
        normalizer.start     <= multiplier.done;
      when others => -- op_i2f_c
        normalizer.mode      <= '1'; -- int_to_float
        normalizer.sign      <= fu_conv_i2f.sign;
        normalizer.xexp      <= "001111111"; -- bias = 127
        normalizer.xmantissa <= (others => '0'); -- don't care
        normalizer.class     <= (others => '0'); -- don't care
        normalizer.flags_in  <= (others => '0'); -- no flags yet
        normalizer.start     <= fu_conv_i2f.done;
    end case;
  end process normalizer_input_select;


  -- Normalizer & Rounding Unit -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cpu_cp_fpu_normalizer_inst: neorv32_cpu_cp_fpu_normalizer
  generic map (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT => FPU_SUBNORMAL_SUPPORT -- Implemented sub-normal support, default false
  )
  port map (
    -- control --
    clk_i      => clk_i,                -- global clock, rising edge
    rstn_i     => rstn_i,               -- global reset, low-active, async
    start_i    => normalizer.start,     -- trigger operation
    abort_i    => ctrl_i.cpu_trap,      -- abort current operation
    rmode_i    => fpu_operands.frm,     -- rounding mode
    funct_i    => normalizer.mode,      -- operation mode
    -- input --
    sign_i     => normalizer.sign,      -- sign
    exponent_i => normalizer.xexp,      -- extended exponent
    mantissa_i => normalizer.xmantissa, -- extended mantissa
    integer_i  => fu_conv_i2f.result,   -- integer input
    class_i    => normalizer.class,     -- input number class
    flags_i    => normalizer.flags_in,  -- exception flags input
    -- output --
    result_o   => normalizer.result,    -- result (float or int)
    flags_o    => normalizer.flags_out, -- exception flags
    done_o     => normalizer.done       -- operation done
  );


-- ****************************************************************************************************************************
-- FPU Core - Result
-- ****************************************************************************************************************************

  -- Output Result to CPU Pipeline ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  output_gate: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      res_o  <= (others => '0');
      fflags <= (others => '0');
    elsif rising_edge(clk_i) then
      res_o  <= (others => '0');
      fflags <= (others => '0');
      if (ctrl_engine.valid = '1') then
        case funct_ff is
          when op_class_c =>
            res_o  <= fu_classify.result;
            fflags <= fu_classify.flags;
          when op_comp_c =>
            res_o  <= fu_compare.result;
            fflags <= fu_compare.flags;
          when op_f2i_c =>
            res_o  <= fu_conv_f2i.result;
            fflags <= fu_conv_f2i.flags;
          when op_sgnj_c =>
            res_o  <= fu_sign_inject.result;
            fflags <= fu_sign_inject.flags;
          when op_minmax_c =>
            res_o  <= fu_min_max.result;
            fflags <= fu_min_max.flags;
          when others => -- op_mul_c, op_addsub_c, op_i2f_c, ...
            res_o  <= normalizer.result;
            fflags <= normalizer.flags_out;
        end case;
      end if;
    end if;
  end process output_gate;

  -- operation done --
  fu_core_done <= fu_compare.done or fu_classify.done or fu_sign_inject.done or fu_min_max.done or normalizer.done or fu_conv_f2i.done;


end neorv32_cpu_cp_fpu_rtl;


-- ================================================================================ --
-- NEORV32 CPU - Single-Precision Floating-Point Unit: Normalizer and Rounding Unit --
-- -------------------------------------------------------------------------------- --
-- This unit also performs integer-to-float conversions.                            --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2024 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_cp_fpu_normalizer is
  generic (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT : boolean := false -- Implemented sub-normal support, default false
  );
  port (
    -- control --
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    start_i    : in  std_ulogic; -- trigger operation
    abort_i    : in  std_ulogic; -- abort current operation
    rmode_i    : in  std_ulogic_vector(2 downto 0); -- rounding mode
    funct_i    : in  std_ulogic; -- operating mode (0=norm&round, 1=int-to-float)
    -- input --
    sign_i     : in  std_ulogic; -- sign
    exponent_i : in  std_ulogic_vector(8 downto 0); -- extended exponent
    mantissa_i : in  std_ulogic_vector(47 downto 0); -- extended mantissa
    integer_i  : in  std_ulogic_vector(31 downto 0); -- integer input
    class_i    : in  std_ulogic_vector(9 downto 0); -- input number class
    flags_i    : in  std_ulogic_vector(4 downto 0); -- exception flags input
    -- output --
    result_o   : out std_ulogic_vector(31 downto 0); -- float result
    flags_o    : out std_ulogic_vector(4 downto 0); -- exception flags output
    done_o     : out std_ulogic -- operation done
  );
end neorv32_cpu_cp_fpu_normalizer;

architecture neorv32_cpu_cp_fpu_normalizer_rtl of neorv32_cpu_cp_fpu_normalizer is

  -- controller --
  type ctrl_engine_state_t is (S_IDLE, S_PREPARE_I2F, S_CHECK_I2F, S_PREPARE_NORM, S_PREPARE_SHIFT, S_NORMALIZE_BUSY, S_ROUND, S_CHECK, S_FINALIZE);
  type ctrl_t is record
    state   : ctrl_engine_state_t; -- current state
    norm_r  : std_ulogic; -- normalization round 0 or 1
    cnt     : std_ulogic_vector(8 downto 0); -- interation counter/exponent (incl. overflow)
    cnt_pre : std_ulogic_vector(8 downto 0);
    cnt_of  : std_ulogic; -- counter overflow
    cnt_uf  : std_ulogic; -- counter underflow
    rounded : std_ulogic; -- output is rounded
    res_sgn : std_ulogic;
    res_exp : std_ulogic_vector(7 downto 0);
    res_man : std_ulogic_vector(22 downto 0);
    class   : std_ulogic_vector(9 downto 0);
    flags   : std_ulogic_vector(4 downto 0);
  end record;
  signal ctrl : ctrl_t;

  -- normalization shift register --
  type sreg_t is record
    done  : std_ulogic;
    dir   : std_ulogic; -- shift direction: 0=right, 1=left
    zero  : std_ulogic;
    upper : std_ulogic_vector(31 downto 0);
    lower : std_ulogic_vector(22 downto 0);
    ext_g : std_ulogic; -- guard bit
    ext_r : std_ulogic; -- round bit
    ext_s : std_ulogic; -- sticky bit
  end record;
  signal sreg : sreg_t;

  -- rounding unit --
  type round_t is record
    en     : std_ulogic; -- enable rounding
    sub    : std_ulogic; -- 0=decrement, 1=increment
    output : std_ulogic_vector(24 downto 0); -- mantissa size + hidden one + 1
  end record;
  signal round : round_t;

begin

  -- Control Engine -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  ctrl_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl.state   <= S_IDLE;
      ctrl.norm_r  <= '0';
      ctrl.cnt     <= (others => '0');
      ctrl.cnt_pre <= (others => '0');
      ctrl.cnt_of  <= '0';
      ctrl.cnt_uf  <= '0';
      ctrl.rounded <= '0';
      ctrl.res_exp <= (others => '0');
      ctrl.res_man <= (others => '0');
      ctrl.res_sgn <= '0';
      ctrl.class   <= (others => '0');
      ctrl.flags   <= (others => '0');
      --
      sreg.upper   <= (others => '0');
      sreg.lower   <= (others => '0');
      sreg.dir     <= '0';
      sreg.ext_g   <= '0';
      sreg.ext_r   <= '0';
      sreg.ext_s   <= '0';
      --
      done_o       <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      ctrl.cnt_pre <= ctrl.cnt;
      done_o       <= '0';

      -- exponent counter underflow/overflow --
      if ((ctrl.cnt_pre(8 downto 7) = "01") and (ctrl.cnt(8 downto 7) = "10")) then -- overflow
        ctrl.cnt_of <= '1';
      elsif (ctrl.cnt_pre(8 downto 7) = "00") and (ctrl.cnt(8 downto 7) = "11") then -- underflow
        ctrl.cnt_uf <= '1';
      end if;

      -- fsm --
      case ctrl.state is

        when S_IDLE => -- wait for operation trigger
        -- ------------------------------------------------------------
          ctrl.norm_r  <= '0'; -- start with first normalization
          ctrl.rounded <= '0'; -- not rounded yet
          ctrl.cnt_of  <= '0';
          ctrl.cnt_uf  <= '0';
          --
          if (start_i = '1') then
            ctrl.cnt     <= exponent_i;
            ctrl.res_sgn <= sign_i;
            ctrl.class   <= class_i;
            -- As we currently do not support sub-normals we need to convert the denorm class to a 0.0 class
            if (not FPU_SUBNORMAL_SUPPORT) then
              if (class_i(fp_class_neg_denorm_c) = '1') then
                ctrl.class(fp_class_neg_denorm_c)  <= '0';
                ctrl.class(fp_class_neg_zero_c)    <= '1';
              end if;
              if (class_i(fp_class_pos_denorm_c) = '1') then
                ctrl.class(fp_class_pos_denorm_c)  <= '0';
                ctrl.class(fp_class_pos_zero_c)    <= '1';
              end if;
            end if;
            ctrl.flags   <= flags_i;
            if (funct_i = '0') then -- float -> float
              ctrl.state <= S_PREPARE_NORM;
            else -- integer -> float
              ctrl.state <= S_PREPARE_I2F;
            end if;
          end if;

        when S_PREPARE_I2F => -- prepare integer-to-float conversion
        -- ------------------------------------------------------------
          sreg.upper <= integer_i;
          sreg.lower <= (others => '0');
          sreg.ext_g <= '0';
          sreg.ext_r <= '0';
          sreg.ext_s <= '0';
          sreg.dir   <= '0'; -- shift right
          ctrl.state <= S_CHECK_I2F;

        when S_CHECK_I2F => -- check if converting zero
        -- ------------------------------------------------------------
          if (sreg.zero = '1') then -- all zero
            ctrl.class(fp_class_pos_zero_c) <= '1';
            ctrl.state <= S_FINALIZE;
          else
            ctrl.state <= S_NORMALIZE_BUSY;
          end if;

        when S_PREPARE_NORM => -- prepare "normal" normalization & rounding
        -- ------------------------------------------------------------
          sreg.upper(31 downto 2) <= (others => '0');
          sreg.upper(1 downto 0)  <= mantissa_i(47 downto 46);
          sreg.lower <= mantissa_i(45 downto 23);
          sreg.ext_g <= mantissa_i(22);
          sreg.ext_r <= mantissa_i(21);
          if (or_reduce_f(mantissa_i(20 downto 0)) = '1') then
            sreg.ext_s <= '1';
          else
            sreg.ext_s <= '0';
          end if;
          -- check for special cases --
          if ((ctrl.class(fp_class_snan_c)       or ctrl.class(fp_class_qnan_c)       or -- NaN
               ctrl.class(fp_class_neg_zero_c)   or ctrl.class(fp_class_pos_zero_c)   or -- zero
               ctrl.class(fp_class_neg_denorm_c) or ctrl.class(fp_class_pos_denorm_c) or -- subnormal
               ctrl.class(fp_class_neg_inf_c)    or ctrl.class(fp_class_pos_inf_c)    or -- infinity
               ctrl.flags(fp_exc_uf_c) or -- underflow
               ctrl.flags(fp_exc_of_c) or -- overflow
               ctrl.flags(fp_exc_nv_c)) = '1') then -- invalid
            ctrl.state <= S_FINALIZE;
          -- The normalizer only checks the class of the inputs and not the result.
          -- Check whether adder result is 0.0 which can happen if eg. 1.0 - 1.0.
          -- Set ctrl.cnt to 0 to force the resulting exponent to be 0.
          -- Do not change sreg.lower as that is already all 0s.
          -- Do not change sign as that should be the right sign from the add/sub.
          elsif (unsigned(mantissa_i(47 downto 0)) = 0) then
            ctrl.cnt <= (others => '0');
            ctrl.state <= S_FINALIZE;
          else
            ctrl.state <= S_PREPARE_SHIFT;
          end if;

        when S_PREPARE_SHIFT => -- prepare shift direction (for "normal" normalization only)
        -- ------------------------------------------------------------
          if (sreg.zero = '0') then -- number < 1.0
            sreg.dir <= '0'; -- shift right
          else -- number >= 1.0
            sreg.dir <= '1'; -- shift left
          end if;
          ctrl.state <= S_NORMALIZE_BUSY;

        when S_NORMALIZE_BUSY => -- running normalization cycle
        -- ------------------------------------------------------------
          -- shift until normalized or exception --
          if (sreg.done = '1') or (ctrl.cnt_uf = '1') or (ctrl.cnt_of = '1') then
            -- normalization control --
            ctrl.norm_r <= '1';
            if (ctrl.norm_r = '0') then -- first normalization cycle done
              ctrl.state <= S_ROUND;
            else -- second normalization cycle done
              ctrl.state <= S_CHECK;
            end if;
          else
            if (sreg.dir = '0') then -- shift right
              ctrl.cnt   <= std_ulogic_vector(unsigned(ctrl.cnt) + 1);
              sreg.upper <= '0' & sreg.upper(sreg.upper'left downto 1);
              sreg.lower <= sreg.upper(0) & sreg.lower(sreg.lower'left downto 1);
              sreg.ext_g <= sreg.lower(0);
              sreg.ext_r <= sreg.ext_g;
              sreg.ext_s <= sreg.ext_r or sreg.ext_s; -- sticky bit
            else -- shift left
              ctrl.cnt   <= std_ulogic_vector(unsigned(ctrl.cnt) - 1);
              sreg.upper <= sreg.upper(sreg.upper'left-1 downto 0) & sreg.lower(sreg.lower'left);
              sreg.lower <= sreg.lower(sreg.lower'left-1 downto 0) & sreg.ext_g;
              sreg.ext_g <= sreg.ext_r;
              sreg.ext_r <= sreg.ext_s;
              sreg.ext_s <= sreg.ext_s; -- sticky bit
            end if;
          end if;

        when S_ROUND => -- rounding cycle (after first normalization)
        -- ------------------------------------------------------------
          ctrl.rounded <= ctrl.rounded or round.en;
          sreg.upper(31 downto 2) <= (others => '0');
          sreg.upper(1 downto 0)  <= round.output(24 downto 23);
          sreg.lower <= round.output(22 downto 0);
          -- If after the first shift we get a bit in any of the guard bits then independent of rounding mode
          -- the end result will be inexact as we are truncating away information
          ctrl.flags(fp_exc_nx_c) <= sreg.ext_g or sreg.ext_r or sreg.ext_s;
          sreg.ext_g <= '0';
          sreg.ext_r <= '0';
          sreg.ext_s <= '0';
          ctrl.state <= S_PREPARE_SHIFT;

        when S_CHECK => -- check for overflow/underflow
        -- ------------------------------------------------------------
          if (ctrl.cnt_uf = '1') then -- underflow
            ctrl.flags(fp_exc_uf_c) <= '1';
            -- As is defined in '754, under default exception handling, underflow is
            -- only signalled when the result is tiny and inexact. In such a case,
            -- both the underflow and inexact flags are raised.
            ctrl.flags(fp_exc_nx_c) <= '1';
          elsif (ctrl.cnt_of = '1') then -- overflow
            ctrl.flags(fp_exc_of_c) <= '1';
            -- As is defined in '754, under default exception handling, overflow is
            -- only signalled when the result is large and inexact. In such a case,
            -- both the underflow and inexact flags are raised.
            ctrl.flags(fp_exc_nx_c) <= '1';
          elsif (ctrl.cnt(7 downto 0) = x"00") then -- subnormal
            ctrl.flags(fp_exc_uf_c) <= '1';
            -- As is defined in '754, under default exception handling, underflow is
            -- only signalled when the result is tiny and inexact. In such a case,
            -- both the underflow and inexact flags are raised.
            ctrl.flags(fp_exc_nx_c) <= '1';
          elsif (ctrl.cnt(7 downto 0) = x"FF") then -- infinity
            ctrl.flags(fp_exc_of_c) <= '1';
            -- As is defined in '754, under default exception handling, overflow is
            -- only signalled when the result is large and inexact. In such a case,
            -- both the underflow and inexact flags are raised.
            ctrl.flags(fp_exc_nx_c) <= '1';
          end if;
          ctrl.state <= S_FINALIZE;

        when S_FINALIZE => -- result finalization
        -- ------------------------------------------------------------
          -- generate result word (the ORDER of checks is important here!) --
          if (ctrl.class(fp_class_snan_c) = '1') or (ctrl.class(fp_class_qnan_c) = '1') then -- sNaN / qNaN
            ctrl.res_sgn <= fp_single_qnan_c(31);
            ctrl.res_exp <= fp_single_qnan_c(30 downto 23);
            ctrl.res_man <= fp_single_qnan_c(22 downto 0);
          elsif (ctrl.class(fp_class_neg_inf_c) = '1') or (ctrl.class(fp_class_pos_inf_c) = '1') or -- infinity
                (ctrl.flags(fp_exc_of_c) = '1') then -- overflow
            -- if rounding mode is towards 0 we cannot generate an infinity instead we need to generate +MAX
            if ((rmode_i = "001") and (ctrl.flags(fp_exc_of_c) = '1')) then
              ctrl.res_exp <= fp_single_pos_max_c(30 downto 23); -- keep original sign
              ctrl.res_man <= fp_single_pos_max_c(22 downto 0);
            -- if rounding mode is towards -inf we cannot generate a positive infinity instead we need to generate +MAX
            elsif ((rmode_i = "010") and (ctrl.flags(fp_exc_of_c) = '1') and (sign_i = '0')) then
              ctrl.res_exp <= fp_single_pos_max_c(30 downto 23); -- keep original sign
              ctrl.res_man <= fp_single_pos_max_c(22 downto 0);
            -- if rounding mode is towards +inf we cannot generate a negative infinity instead we need to generate -MAX
            elsif ((rmode_i = "011") and (ctrl.flags(fp_exc_of_c) = '1') and (sign_i = '1')) then
              ctrl.res_exp <= fp_single_neg_max_c(30 downto 23); -- keep original sign
              ctrl.res_man <= fp_single_neg_max_c(22 downto 0);
            else
              ctrl.res_exp <= fp_single_pos_inf_c(30 downto 23); -- keep original sign
              ctrl.res_man <= fp_single_pos_inf_c(22 downto 0);
            end if;
          elsif (ctrl.class(fp_class_neg_zero_c) = '1') or (ctrl.class(fp_class_pos_zero_c) = '1') then -- zero
            ctrl.res_sgn <= ctrl.class(fp_class_neg_zero_c);
            ctrl.res_exp <= fp_single_pos_zero_c(30 downto 23);
            ctrl.res_man <= fp_single_pos_zero_c(22 downto 0);
          elsif (ctrl.flags(fp_exc_uf_c) = '1') or -- underflow
                (sreg.zero = '1') or (ctrl.class(fp_class_neg_denorm_c) = '1') or (ctrl.class(fp_class_pos_denorm_c) = '1') then -- denormalized (flush-to-zero)
            ctrl.res_exp <= fp_single_pos_zero_c(30 downto 23); -- keep original sign
            ctrl.res_man <= fp_single_pos_zero_c(22 downto 0);
          else -- result is fine as it is
            ctrl.res_exp <= ctrl.cnt(7 downto 0);
            ctrl.res_man <= sreg.lower;
          end if;
          -- generate exception flags --
          ctrl.flags(fp_exc_nv_c) <= ctrl.flags(fp_exc_nv_c) or ctrl.class(fp_class_snan_c); -- invalid if input is SIGNALING NaN
          ctrl.flags(fp_exc_nx_c) <= ctrl.flags(fp_exc_nx_c) or ctrl.rounded; -- inexact if result is rounded
          -- processing done --
          done_o     <= '1';
          ctrl.state <= S_IDLE;

        when others => -- undefined
        -- ------------------------------------------------------------
          ctrl.state <= S_IDLE;

      end case;

      -- override: abort operation --
      if (abort_i = '1') then
        ctrl.state <= S_IDLE;
      end if;
    end if;
  end process ctrl_engine;

  -- stop shifting when normalized --
  sreg.done <= '1' when (or_reduce_f(sreg.upper(sreg.upper'left downto 1)) = '0') and (sreg.upper(0) = '1') else '0'; -- input is zero, hidden one is set

  -- all-zero including hidden bit --
  sreg.zero <= '1' when (or_reduce_f(sreg.upper) = '0') else '0';

  -- result --
  result_o(31)           <= ctrl.res_sgn;
  result_o(30 downto 23) <= ctrl.res_exp;
  result_o(22 downto 0)  <= ctrl.res_man;

  -- exception flags --
  flags_o(fp_exc_nv_c) <= ctrl.flags(fp_exc_nv_c); -- invalid operation
  flags_o(fp_exc_dz_c) <= ctrl.flags(fp_exc_dz_c); -- divide by zero
  flags_o(fp_exc_of_c) <= ctrl.flags(fp_exc_of_c); -- overflow
  flags_o(fp_exc_uf_c) <= ctrl.flags(fp_exc_uf_c); -- underflow
  flags_o(fp_exc_nx_c) <= ctrl.flags(fp_exc_nx_c); -- inexact


  -- Rounding -------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  rounding_unit_ctrl: process(rmode_i, sreg, sign_i)
  begin
    -- defaults --
    round.en  <= '0';
    round.sub <= '0';
    -- rounding mode --
    case rmode_i(2 downto 0) is
      when "000" => -- round to nearest, ties to even
        if (sreg.ext_g = '0') then
          round.en <= '0'; -- round down (do nothing)
        else
          if (sreg.ext_r = '0') and (sreg.ext_s = '0') then -- tie!
            round.en <= sreg.lower(0); -- round up if LSB of mantissa is set
          else
            round.en <= '1'; -- round up
          end if;
        end if;
        round.sub <= '0'; -- increment
      when "001" => -- round towards zero
        round.en <= '0'; -- no rounding -> just truncate
      when "010" => -- round down (towards -infinity)
        -- If the number is positive truncate to round down towards -inf
        if (sign_i = '0') then
          round.en <= '0'; -- truncate
        else -- if the number is negative and we have a remainder increment to round up towards -inf
          round.en  <= sreg.ext_g or sreg.ext_r or sreg.ext_s;
          round.sub <= '0'; -- decrement
        end if;
      when "011" => -- round up (towards +infinity)
        -- if the number is negative truncate to round down towards +inf
        if (sign_i = '1') then
          round.en <= '0'; -- truncate
        else -- if the number is positive and we have a remainder increment to round up towards +inf
          round.en  <= sreg.ext_g or sreg.ext_r or sreg.ext_s;
          round.sub <= '0'; -- increment
        end if;
      when "100" => -- round to nearest, ties to max magnitude
        -- similar to rount to nearest, ties to even. This is basically "classic" round
        -- if the remainder is <0.5 (g = 0) we truncate
        if (sreg.ext_g = '0') then
          round.en <= '0'; -- round down (do nothing)
        else -- the remaind is >= 0.5 (g = 1) we round up
          round.en <= '1'; -- round up
        end if;
        round.sub <= '0'; -- increment
      when others => -- undefined
        round.en <= '0';
    end case;
  end process rounding_unit_ctrl;


  -- incrementer/decrementer --
  rounding_unit_add: process(round, sreg)
    variable tmp_v : std_ulogic_vector(24 downto 0);
  begin
    tmp_v := '0' & sreg.upper(0) & sreg.lower;
    if (round.en = '1') then
      if (round.sub = '0') then -- increment
        round.output <= std_ulogic_vector(unsigned(tmp_v) + 1);
      else -- decrement
        round.output <= std_ulogic_vector(unsigned(tmp_v) - 1);
      end if;
    else -- do nothing
      round.output <= tmp_v;
    end if;
  end process rounding_unit_add;


end neorv32_cpu_cp_fpu_normalizer_rtl;


-- ================================================================================ --
-- NEORV32 CPU - Single-Precision Floating-Point Unit: Float-To-Int Converter       --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2024 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_cp_fpu_f2i is
  generic (
    -- FPU-specific options --
    FPU_SUBNORMAL_SUPPORT : boolean := false -- Implemented sub-normal support, default false
  );
  port (
    -- control --
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    start_i    : in  std_ulogic; -- trigger operation
    abort_i    : in  std_ulogic; -- abort current operation
    rmode_i    : in  std_ulogic_vector(2 downto 0); -- rounding mode
    funct_i    : in  std_ulogic; -- 0=signed, 1=unsigned
    -- input --
    sign_i     : in  std_ulogic; -- sign
    exponent_i : in  std_ulogic_vector(7 downto 0); -- exponent
    mantissa_i : in  std_ulogic_vector(22 downto 0); -- mantissa
    class_i    : in  std_ulogic_vector(9 downto 0); -- operand class
    -- output --
    result_o   : out std_ulogic_vector(31 downto 0); -- integer result
    flags_o    : out std_ulogic_vector(4 downto 0); -- exception flags
    done_o     : out std_ulogic -- operation done
  );
end neorv32_cpu_cp_fpu_f2i;

architecture neorv32_cpu_cp_fpu_f2i_rtl of neorv32_cpu_cp_fpu_f2i is

  -- controller --
  type ctrl_engine_state_t is (S_IDLE, S_PREPARE_F2I, S_NORMALIZE_BUSY, S_ROUND, S_FINALIZE);
  type ctrl_t is record
    state      : ctrl_engine_state_t; -- current state
    unsign     : std_ulogic;
    cnt        : std_ulogic_vector(7 downto 0); -- interation counter/exponent
    sign       : std_ulogic;
    class      : std_ulogic_vector(9 downto 0);
    rounded    : std_ulogic; -- output is rounded
    over       : std_ulogic; -- output is overflowing
    under      : std_ulogic; -- output in underflowing
    result_tmp : std_ulogic_vector(31 downto 0);
    result     : std_ulogic_vector(31 downto 0);
    flags      : std_ulogic_vector(4 downto 0); -- we need to generate flags during the normalizing processes
  end record;
  signal ctrl : ctrl_t;

  -- conversion shift register --
  type sreg_t is record
    int   : std_ulogic_vector(31 downto 0); -- including hidden-zero
    mant  : std_ulogic_vector(22 downto 0);
    ext_g : std_ulogic; -- guard bit
    ext_r : std_ulogic; -- round bit
    ext_s : std_ulogic; -- sticky bit
  end record;
  signal sreg : sreg_t;

  -- rounding unit --
  type round_t is record
    en     : std_ulogic; -- enable rounding
    sub    : std_ulogic; -- 0=decrement, 1=increment
    output : std_ulogic_vector(32 downto 0); -- result + overflow
  end record;
  signal round : round_t;

begin

  -- Control Engine -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  ctrl_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl.state      <= S_IDLE;
      ctrl.cnt        <= (others => '0');
      ctrl.sign       <= '0';
      ctrl.class      <= (others => '0');
      ctrl.rounded    <= '0';
      ctrl.over       <= '0';
      ctrl.under      <= '0';
      ctrl.unsign     <= '0';
      ctrl.result     <= (others => '0');
      ctrl.result_tmp <= (others => '0');
      -- clear the flags
      ctrl.flags      <= (others => '0');
      sreg.int        <= (others => '0');
      sreg.mant       <= (others => '0');
      sreg.ext_g      <= '0';
      sreg.ext_r      <= '0';
      sreg.ext_s      <= '0';
      done_o          <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      done_o <= '0';

      -- fsm --
      case ctrl.state is

        when S_IDLE => -- wait for operation trigger
        -- ------------------------------------------------------------
          ctrl.rounded <= '0'; -- not rounded yet
          ctrl.over    <= '0'; -- not overflowing yet
          ctrl.under   <= '0'; -- not underflowing yet
          ctrl.unsign  <= funct_i;
          -- Need to clear G and R as well
          sreg.ext_g   <= '0';
          sreg.ext_r   <= '0';
          sreg.ext_s   <= '0'; -- init
          if (start_i = '1') then
            ctrl.cnt    <= exponent_i;
            ctrl.sign   <= sign_i;
            ctrl.class  <= class_i;
            sreg.mant   <= mantissa_i;
            ctrl.state  <= S_PREPARE_F2I;
            -- Ensure that the flags are held until the FPU can capture them
            ctrl.flags  <= (others => '0');
          end if;

        when S_PREPARE_F2I => -- prepare float-to-integer conversion
        -- ------------------------------------------------------------
          -- if the exponent is small enough only S will be set, assuming the number is not 0
          if (unsigned(ctrl.cnt) < 125) then -- less than 0.5
            sreg.int    <= (others => '0');
            sreg.mant   <= "001" & sreg.mant(sreg.mant'left downto 3);
            ctrl.under  <= '1'; -- this is an underflow!
            ctrl.cnt    <= (others => '0');
          elsif (unsigned(ctrl.cnt) = 125) then -- less than 0.5
            sreg.int    <= (others => '0');
            sreg.mant   <= "01" & sreg.mant(sreg.mant'left downto 2);
            ctrl.under  <= '1'; -- this is an underflow!
            ctrl.cnt    <= (others => '0');
          elsif (unsigned(ctrl.cnt) = 126) then -- num < 1.0 but num >= 0.5
            sreg.int    <= (others => '0');
            sreg.mant   <= '1' & sreg.mant(sreg.mant'left downto 1);
            -- As the number cannot be represented correctly it will be an underflow
            ctrl.under  <= '1'; -- this is an underflow!
            ctrl.cnt    <= (others => '0');
          else
            sreg.int    <= (others => '0');
            sreg.int(0) <= '1'; -- hidden one
            ctrl.cnt    <= std_ulogic_vector(unsigned(ctrl.cnt) - 127); -- remove bias to get raw number of left shifts
          end if;
          -- check terminal cases --
          if ((ctrl.class(fp_class_neg_inf_c)  or ctrl.class(fp_class_pos_inf_c) or
               ctrl.class(fp_class_neg_zero_c) or ctrl.class(fp_class_pos_zero_c) or
               ctrl.class(fp_class_snan_c)     or ctrl.class(fp_class_qnan_c)) = '1') then
            ctrl.state <= S_FINALIZE;
          -- check for denorm case if we do not support subnormals
          elsif ((not FPU_SUBNORMAL_SUPPORT) and
                ((ctrl.class(fp_class_neg_denorm_c) or ctrl.class(fp_class_pos_denorm_c)) = '1')) then
            ctrl.state <= S_FINALIZE;
          else
            -- Trip: If the float exponent is to large to fit in an integer we are
            -- shifting the float mantissa out of the integer causing an overflow.
            -- We detect this when the exponent is larger than 127 + XLEN + 1.
            -- Catch: When the exponent is larger than XLEN + 1 set the overflow flag and go to the next stage.
            -- Note: We use 127 as that is an exponent of 0, XLEN for the integer width and + 1 for safety.
            -- In principle the +1 shouldn't be needed.
            if (unsigned(ctrl.cnt) > (127+XLEN+1)) then -- 0 + 32 + 1 or 127 + 32 + 1
              ctrl.over <= '1';
              ctrl.state <= S_FINALIZE;
            else
              ctrl.state <= S_NORMALIZE_BUSY;
            end if;
          end if;

        when S_NORMALIZE_BUSY => -- running normalization cycle
        -- ------------------------------------------------------------
          -- if we are at the last step of a normal shift right update the G, R and S
          if (or_reduce_f(ctrl.cnt(ctrl.cnt'left-1 downto 0)) = '0') then
            sreg.ext_g <= sreg.mant(sreg.mant'left);
            sreg.ext_r <= sreg.mant(sreg.mant'left-1);
            if (or_reduce_f(sreg.mant(sreg.mant'left-2 downto 0)) = '1') then
              sreg.ext_s <= '1'; -- sticky bit
            end if;
            if (ctrl.unsign = '0') then -- signed conversion
              ctrl.over <= ctrl.over or sreg.int(sreg.int'left); -- update overrun flag again to check for numerical overflow into sign bit
            end if;
            ctrl.state <= S_ROUND;
          else -- shift left
            ctrl.cnt  <= std_ulogic_vector(unsigned(ctrl.cnt) - 1);
            sreg.int  <= sreg.int(sreg.int'left-1 downto 0) & sreg.mant(sreg.mant'left);
            sreg.mant <= sreg.mant(sreg.mant'left-1 downto 0) & '0';
            ctrl.over <= ctrl.over or sreg.int(sreg.int'left);
            sreg.ext_g <= '0'; -- as we are shifting left these will always be 0
            sreg.ext_r <= '0'; -- as we are shifting left these will always be 0
            sreg.ext_s <= '0'; -- sticky bit
          end if;

        when S_ROUND => -- rounding cycle
        -- ------------------------------------------------------------
          ctrl.rounded    <= ctrl.rounded or round.en;
          ctrl.over       <= ctrl.over or round.output(round.output'left); -- overflow after rounding
          ctrl.result_tmp <= round.output(round.output'left-1 downto 0);
          ctrl.state      <= S_FINALIZE;
          -- If after the round we get bits in the guard band
          -- the end result will be inexact as we are truncating away information
          ctrl.flags(fp_exc_nx_c) <= ctrl.flags(fp_exc_nx_c) or sreg.ext_g or sreg.ext_r or sreg.ext_s;

        when S_FINALIZE => -- check for corner cases and finalize result
        -- ------------------------------------------------------------
        -- per RISCV specification the resulting flags can only be: Not Valid (NV) and Not Exact (NX).
        -- "All floating-point conversion instructions set the Inexact exception flag if the rounded result differs from
        -- the operand value and the Invalid exception flag is not set."
        -- Both flags cannot be set concurrently.
        -- Overflow and Underflow flags are never set.
        -- "If the rounded result is not representable in the destination format, it is clipped to the nearest value and
        -- the invalid flag is set. Table 15 gives the range of valid inputs for FCVT.int.S and the behavior for
        -- invalid inputs."
          if (ctrl.unsign = '1') then -- unsigned conversion
            if (ctrl.class(fp_class_snan_c) = '1') or (ctrl.class(fp_class_qnan_c) = '1') or (ctrl.class(fp_class_pos_inf_c) = '1') or -- NaN or +inf
               ((ctrl.sign = '0') and (ctrl.over = '1')) then -- positive out-of-range
              ctrl.result <= x"ffffffff";
              -- As we are saturating the result is also NV but never NX
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            -- split to better handle the subnormal case and infinity case
            elsif ((ctrl.class(fp_class_neg_inf_c) = '1')) then -- -inf
              ctrl.result <= x"00000000";
              -- As we are saturating the result is also NV but never NX
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            elsif (ctrl.class(fp_class_neg_zero_c) = '1') or (ctrl.class(fp_class_pos_zero_c) = '1') then -- zero
              ctrl.result <= x"00000000";
            elsif ((not FPU_SUBNORMAL_SUPPORT) and ((ctrl.class(fp_class_neg_denorm_c) = '1') or (ctrl.class(fp_class_pos_denorm_c) = '1'))) then -- subnormal
              ctrl.result <= x"00000000";
            elsif ((ctrl.under = '1') and (ctrl.result_tmp(0) = '0')) then -- +/- underflow
              ctrl.result <= x"00000000";
              -- if we had an underflow we are inexact
              ctrl.flags(fp_exc_nx_c) <= '1';
            elsif ((ctrl.sign = '1')) then -- negative out-of-range
              ctrl.result <= x"00000000";
              -- As we are saturating the result is also NV but never NX
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            -- if underflow is set the number is too small, but the rounding mode can cause the LSB to be
            -- set and thus we still have a valid result
            else
              ctrl.result <= ctrl.result_tmp;
            end if;

          else -- signed conversion
            -- Split up the potential causes for +MAX to better manage flags
            if (ctrl.class(fp_class_snan_c) = '1') or (ctrl.class(fp_class_qnan_c) = '1') then  -- NaN
              ctrl.result <= x"7fffffff";
              -- if NAN the number is not-valid but never inexact
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            elsif (ctrl.class(fp_class_pos_inf_c) = '1') then  -- +inf
              ctrl.result <= x"7fffffff";
              -- if INF the number is not-valid but never inexact
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            elsif ((ctrl.sign = '0') and (ctrl.over = '1')) then -- positive out-of-range
              ctrl.result <= x"7fffffff";
              -- if we had are out of range we are not-valid but never inexact
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            -- Split up all the potential causes for 0 generation to better manage flags
            elsif (ctrl.class(fp_class_neg_zero_c) = '1') or (ctrl.class(fp_class_pos_zero_c) = '1') then -- zero
              ctrl.result <= x"00000000";
            -- if we do no support subnormals treat them as +/- zero
            elsif ((not FPU_SUBNORMAL_SUPPORT) and ((ctrl.class(fp_class_neg_denorm_c) = '1') or (ctrl.class(fp_class_pos_denorm_c) = '1'))) then -- subnormal
              ctrl.result <= x"00000000";
            -- if underflow is set the number is too small, but the rounding mode can cause the LSB to be
            -- set and thus we still have a valid result
            elsif ((ctrl.under = '1') and (ctrl.result_tmp(0) = '0')) then -- underflow
              ctrl.result <= x"00000000";
              -- if we had an underflow we are inexact as we are still within the legal range
              ctrl.flags(fp_exc_nx_c) <= '1';
            -- Split up negative infinity to better generate flags
            elsif (ctrl.class(fp_class_neg_inf_c) = '1') then -- -inf
              ctrl.result <= x"80000000";
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            -- If the floating point number is negative, and we have and overflow and the integer MSB is not 1 and
            -- the mantissa is not 0 (without hidden 1) then we have a true overflow.
            -- Otherwise we have a "real" 1 in the result MSB which should result in -MAX as the correct value.
            -- This captures the corner case where the number is exactly 2^-31
            elsif ((ctrl.sign = '1') and (ctrl.over = '1') and
                   (ctrl.result_tmp /= x"80000000") and (mantissa_i /= "00000000000000000000000")) then -- negative out-of-range
              ctrl.result <= x"80000000";
              -- if we had a negative out of range we are not valid but never inexact
              ctrl.flags(fp_exc_nv_c) <= '1';
              ctrl.flags(fp_exc_nx_c) <= '0';
            else -- result is ok, make sign adaption
              -- if we rounded we are inexact, but need to remember if we had remainders in the guard bits
              ctrl.flags(fp_exc_nx_c) <= ctrl.flags(fp_exc_nx_c) or ctrl.rounded;
              if (ctrl.sign = '1') then
                ctrl.result <= std_ulogic_vector(0 - unsigned(ctrl.result_tmp)); -- abs()
              else
                ctrl.result <= ctrl.result_tmp;
              end if;
            end if;
          end if;
          done_o     <= '1';
          ctrl.state <= S_IDLE;

        when others => -- undefined
        -- ------------------------------------------------------------
          ctrl.state <= S_IDLE;

      end case;

      -- override: abort operation --
      if (abort_i = '1') then
        ctrl.state <= S_IDLE;
      end if;
    end if;
  end process ctrl_engine;

  -- result --
  result_o <= ctrl.result;

  -- exception flags --
  -- add generated flags
  flags_o(fp_exc_nv_c) <= ctrl.flags(fp_exc_nv_c); -- invalid operation
  flags_o(fp_exc_dz_c) <= '0'; -- divide by zero - not possible here
  flags_o(fp_exc_of_c) <= '0'; -- overflow not possible as overflow is flagged as NV ctrl.flags(fp_exc_of_c) or ctrl.over or ctrl.class(fp_class_pos_inf_c) or ctrl.class(fp_class_neg_inf_c); -- overflow
  flags_o(fp_exc_uf_c) <= '0'; -- underflow is not possible as it will either be NV if out of range or inexact. ctrl.flags(fp_exc_uf_c) or ctrl.under; -- underflow
  flags_o(fp_exc_nx_c) <= ctrl.flags(fp_exc_nx_c); -- inexact if result was rounded

  -- Rounding -------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  rounding_unit_ctrl: process(rmode_i, sreg, sign_i)
  begin
    -- defaults --
    round.en  <= '0';
    round.sub <= '0';
    -- rounding mode --
    case rmode_i(2 downto 0) is
      when "000" => -- round to nearest, ties to even
        if (sreg.ext_g = '0') then
          round.en <= '0'; -- round down (do nothing)
        else
          if (sreg.ext_r = '0') and (sreg.ext_s = '0') then -- tie!
            round.en <= sreg.int(0); -- round up if LSB of integer is set
          else
            round.en <= '1'; -- round up
          end if;
        end if;
        round.sub <= '0'; -- increment
      when "001" => -- round towards zero
        round.en <= '0'; -- no rounding -> just truncate
      when "010" => -- round down (towards -infinity)
        -- If the number is positive truncate to round down towards -inf
        if (sign_i = '0') then
          round.en <= '0'; -- truncate
        else -- if the number is negative and we have a remainder increment to round up towards -inf
          round.en  <= sreg.ext_g or sreg.ext_r or sreg.ext_s;
          round.sub <= '0'; -- decrement
        end if;
      when "011" => -- round up (towards +infinity)
        -- if the number is negative truncate to round down towards +inf
        if (sign_i = '1') then
          round.en <= '0'; -- truncate
        else -- if the number is positive and we have a remainder increment to round up towards +inf
          round.en  <= sreg.ext_g or sreg.ext_r or sreg.ext_s;
          round.sub <= '0'; -- increment
        end if;
      when "100" => -- round to nearest, ties to max magnitude
        -- similar to rount to nearest, ties to even. This is basically "classic" round
        -- if the remainder is <0.5 (g = 0) we truncate
        if (sreg.ext_g = '0') then
          round.en <= '0'; -- round down (do nothing)
        else -- the remaind is >= 0.5 (g = 1) we round up
          round.en <= '1'; -- round up
        end if;
        round.sub <= '0'; -- increment
      when others => -- undefined
        round.en <= '0';
    end case;
  end process rounding_unit_ctrl;

  -- incrementer/decrementer --
  rounding_unit_add: process(round, sreg)
    variable tmp_v : std_ulogic_vector(32 downto 0); -- including overflow
  begin
    tmp_v := '0' & sreg.int;
    if (round.en = '1') then
      if (round.sub = '0') then -- increment
        round.output <= std_ulogic_vector(unsigned(tmp_v) + 1);
      else -- decrement
        round.output <= std_ulogic_vector(unsigned(tmp_v) - 1);
      end if;
    else -- do nothing
      round.output <= tmp_v;
    end if;
  end process rounding_unit_add;


end neorv32_cpu_cp_fpu_f2i_rtl;
