-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: Integer Mul/Div Unit (RISC-V "M" Extension)          --
-- -------------------------------------------------------------------------------- --
-- Multiplier core (signed/unsigned) uses serial add-and-shift algorithm.           --
-- Multiplications can be mapped to DSP blocks (faster!) when FAST_MUL_EN = true.   --
-- Divider core (unsigned-only; pre and post sign-compensation logic) uses serial   --
-- restoring serial algorithm.                                                      --
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

entity neorv32_cpu_cp_muldiv is
  generic (
    FAST_MUL_EN : boolean; -- use DSPs for faster multiplication
    DIVISION_EN : boolean  -- implement divider hardware
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    ctrl_i  : in  ctrl_bus_t; -- main control bus
    -- data input --
    rs1_i   : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 1
    rs2_i   : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 2
    -- result and status --
    res_o   : out std_ulogic_vector(XLEN-1 downto 0); -- operation result
    valid_o : out std_ulogic -- data output valid
  );
end neorv32_cpu_cp_muldiv;

architecture neorv32_cpu_cp_muldiv_rtl of neorv32_cpu_cp_muldiv is

  -- operations --
  constant op_mul_c    : std_ulogic_vector(2 downto 0) := "000"; -- mul
  constant op_mulh_c   : std_ulogic_vector(2 downto 0) := "001"; -- mulh
  constant op_mulhsu_c : std_ulogic_vector(2 downto 0) := "010"; -- mulhsu
  constant op_mulhu_c  : std_ulogic_vector(2 downto 0) := "011"; -- mulhu
  constant op_div_c    : std_ulogic_vector(2 downto 0) := "100"; -- div
  constant op_divu_c   : std_ulogic_vector(2 downto 0) := "101"; -- divu
  constant op_rem_c    : std_ulogic_vector(2 downto 0) := "110"; -- rem
  constant op_remu_c   : std_ulogic_vector(2 downto 0) := "111"; -- remu

  -- instruction decode --
  signal valid_cmd : std_ulogic;

  -- controller --
  type state_t is (S_IDLE, S_BUSY, S_DONE);
  type ctrl_t is record
    state         : state_t;
    cnt           : std_ulogic_vector(index_size_f(XLEN)-1 downto 0); -- iteration counter
    rs1_is_signed : std_ulogic;
    rs2_is_signed : std_ulogic;
    out_en        : std_ulogic;
  end record;
  signal ctrl : ctrl_t;

  -- divider core --
  type div_t is record
    start     : std_ulogic; -- start new division
    sign_mod  : std_ulogic; -- result sign correction
    rs2_abs   : std_ulogic_vector(XLEN-1 downto 0);
    remainder : std_ulogic_vector(XLEN-1 downto 0);
    quotient  : std_ulogic_vector(XLEN-1 downto 0);
    sub       : std_ulogic_vector(XLEN   downto 0); -- try subtraction (and restore if underflow)
    res_u     : std_ulogic_vector(XLEN-1 downto 0); -- unsigned result
    res       : std_ulogic_vector(XLEN-1 downto 0);
  end record;
  signal div : div_t;

  -- multiplier core --
  type mul_t is record
    start  : std_ulogic; -- start new multiplication
    prod   : std_ulogic_vector((2*XLEN)-1 downto 0); -- product
    add    : std_ulogic_vector(XLEN downto 0); -- addition step
    p_sext : std_ulogic; -- product sign-extension
    dsp_x  : signed(XLEN downto 0); -- input for using DSPs
    dsp_y  : signed(XLEN downto 0); -- input for using DSPs
    dsp_z  : signed(2*XLEN+1 downto 0);
  end record;
  signal mul : mul_t;

begin

  -- Valid Instruction? ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  valid_cmd <= '1' when (ctrl_i.alu_cp_alu = '1') and (ctrl_i.ir_opcode(5) = '1') and
                        (ctrl_i.ir_funct12(11 downto 5) = "0000001") and
                        ((ctrl_i.ir_funct3(2) = '0') or ((ctrl_i.ir_funct3(2) = '1') and DIVISION_EN)) else '0';


  -- Co-Processor Controller ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  control: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl.state  <= S_IDLE;
      ctrl.cnt    <= (others => '0');
      ctrl.out_en <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      ctrl.out_en <= '0';
      ctrl.cnt    <= std_ulogic_vector(to_unsigned(XLEN-2, ctrl.cnt'length)); -- cycle counter initialization

      -- fsm --
      case ctrl.state is

        when S_IDLE => -- wait for start signal
        -- ------------------------------------------------------------
          if (valid_cmd = '1') then -- trigger new operation
            if (ctrl_i.ir_funct3(2) = '0') and FAST_MUL_EN then -- is fast multiplication?
              ctrl.state <= S_DONE;
            else -- serial division or serial multiplication
              ctrl.state <= S_BUSY;
            end if;
          end if;

        when S_BUSY => -- processing
        -- ------------------------------------------------------------
          ctrl.cnt <= std_ulogic_vector(unsigned(ctrl.cnt) - 1);
          if (or_reduce_f(ctrl.cnt) = '0') or (ctrl_i.cpu_trap = '1') then -- abort on trap
            ctrl.state <= S_DONE;
          end if;

        when others => -- S_DONE: final step / enable output for one cycle
        -- ------------------------------------------------------------
          ctrl.out_en <= '1';
          ctrl.state  <= S_IDLE;

      end case;
    end if;
  end process control;

  -- done? assert one cycle before actual data output --
  valid_o <= '1' when (ctrl.state = S_DONE) else '0';

  -- input operands treated as signed? --
  ctrl.rs1_is_signed <= '1' when (ctrl_i.ir_funct3 = op_mulh_c) or (ctrl_i.ir_funct3 = op_mulhsu_c) or
                                 (ctrl_i.ir_funct3 = op_div_c)  or (ctrl_i.ir_funct3 = op_rem_c) else '0';
  ctrl.rs2_is_signed <= '1' when (ctrl_i.ir_funct3 = op_mulh_c) or
                                 (ctrl_i.ir_funct3 = op_div_c)  or (ctrl_i.ir_funct3 = op_rem_c) else '0';

  -- operation trigger --
  mul.start <= '1' when (valid_cmd = '1') and (ctrl_i.ir_funct3(2) = '0') else '0';
  div.start <= '1' when (valid_cmd = '1') and (ctrl_i.ir_funct3(2) = '1') else '0';


  -- Multiplier Core (signed/unsigned) - Full Parallel --------------------------------------
  -- -------------------------------------------------------------------------------------------
  multiplier_core_parallel:
  if FAST_MUL_EN generate

    -- input registers --
    multiplier_core_in_reg: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        mul.dsp_x <= (others => '0');
        mul.dsp_y <= (others => '0');
      elsif rising_edge(clk_i) then
        if (mul.start = '1') then
          mul.dsp_x <= signed((rs1_i(rs1_i'left) and ctrl.rs1_is_signed) & rs1_i);
          mul.dsp_y <= signed((rs2_i(rs2_i'left) and ctrl.rs2_is_signed) & rs2_i);
        end if;
      end if;
    end process multiplier_core_in_reg;

    -- actual multiplication --
    mul.dsp_z <= mul.dsp_x * mul.dsp_y;

    -- output register --
    multiplier_core_out_reg: process(clk_i)
    begin
      if rising_edge(clk_i) then -- no reset to improve DSP mapping
        mul.prod <= std_ulogic_vector(mul.dsp_z(63 downto 0));
      end if;
    end process multiplier_core_out_reg;

  end generate; --/multiplier_core_parallel

  -- no parallel multiplier --
  multiplier_core_parallel_none:
  if not FAST_MUL_EN generate
    mul.dsp_x <= (others => '0');
    mul.dsp_y <= (others => '0');
    mul.dsp_z <= (others => '0');
  end generate;


  -- Multiplier Core (signed/unsigned) - Iterative ------------------------------------------
  -- -------------------------------------------------------------------------------------------
  multiplier_core_serial:
  if not FAST_MUL_EN generate

    -- shift-and-add algorithm --
    multiplier_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        mul.prod <= (others => '0');
      elsif rising_edge(clk_i) then
        if (mul.start = '1') then -- start new multiplication
          mul.prod(63 downto 32) <= (others => '0');
          mul.prod(31 downto 0)  <= rs1_i;
        elsif (ctrl.state /= S_IDLE) then -- processing steps or sign-finalization step
          mul.prod(63 downto 31) <= mul.add(32 downto 0);
          mul.prod(30 downto 0)  <= mul.prod(31 downto 1);
        end if;
      end if;
    end process multiplier_core;

    -- multiply with 0/-1/+1 via shift and subtraction/addition --
    mul_update: process(mul, ctrl, rs2_i)
    begin
      if (mul.prod(0) = '1') then -- multiply with 1
        if (ctrl.state = S_DONE) and (ctrl.rs1_is_signed = '1') then -- for signed operations only: take care of negative weighted MSB -> multiply with -1
          mul.add <= std_ulogic_vector(unsigned(mul.p_sext & mul.prod(63 downto 32)) - unsigned((rs2_i(rs2_i'left) and ctrl.rs2_is_signed) & rs2_i));
        else -- multiply with +1
          mul.add <= std_ulogic_vector(unsigned(mul.p_sext & mul.prod(63 downto 32)) + unsigned((rs2_i(rs2_i'left) and ctrl.rs2_is_signed) & rs2_i));
        end if;
      else -- multiply with 0
        mul.add <= mul.p_sext & mul.prod(63 downto 32);
      end if;
    end process mul_update;

    -- product sign extension bit --
    mul.p_sext <= mul.prod(mul.prod'left) and ctrl.rs2_is_signed;

  end generate; -- /multiplier_core_serial

  -- no serial multiplier --
  multiplier_core_serial_none:
  if FAST_MUL_EN generate
    mul.add    <= (others => '0');
    mul.p_sext <= '0';
  end generate;


  -- Divider Core (unsigned) - Iterative ----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  divider_core_serial:
  if DIVISION_EN generate

    -- restoring division algorithm --
    divider_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        div.quotient  <= (others => '0');
        div.rs2_abs   <= (others => '0');
        div.sign_mod  <= '0';
        div.remainder <= (others => '0');
      elsif rising_edge(clk_i) then
        if (div.start = '1') then -- start new division
          -- abs(rs1) --
          if ((rs1_i(rs1_i'left) and ctrl.rs1_is_signed) = '1') then -- signed division?
            div.quotient <= std_ulogic_vector(0 - unsigned(rs1_i)); -- make positive
          else
            div.quotient <= rs1_i;
          end if;
          -- abs(rs2) --
          if ((rs2_i(rs2_i'left) and ctrl.rs2_is_signed) = '1') then -- signed division?
            div.rs2_abs <= std_ulogic_vector(0 - unsigned(rs2_i)); -- make positive
          else
            div.rs2_abs <= rs2_i;
          end if;
          -- check relevant input signs for result sign compensation --
          if (ctrl_i.ir_funct3(1 downto 0) = op_div_c(1 downto 0)) then -- signed div operation
            div.sign_mod <= (rs1_i(rs1_i'left) xor rs2_i(rs2_i'left)) and or_reduce_f(rs2_i); -- different signs AND divisor not zero
          elsif (ctrl_i.ir_funct3(1 downto 0) = op_rem_c(1 downto 0)) then -- signed rem operation
            div.sign_mod <= rs1_i(rs1_i'left);
          else
            div.sign_mod <= '0';
          end if;
          --
          div.remainder <= (others => '0');
        elsif (ctrl.state = S_BUSY) or (ctrl.state = S_DONE) then -- running?
          div.quotient <= div.quotient(30 downto 0) & (not div.sub(32));
          if (div.sub(32) = '0') then -- implicit shift
            div.remainder <= div.sub(31 downto 0);
          else -- underflow: restore and explicit shift
            div.remainder <= div.remainder(30 downto 0) & div.quotient(31);
          end if;
        end if;
      end if;
    end process divider_core;

    -- try another subtraction (and shift) --
    div.sub <= std_ulogic_vector(unsigned('0' & div.remainder(30 downto 0) & div.quotient(31)) - unsigned('0' & div.rs2_abs));

    -- result and sign compensation --
    div.res_u <= div.quotient when (ctrl_i.ir_funct3(2 downto 1) = op_div_c(2 downto 1)) else div.remainder; -- division only
    div.res   <= std_ulogic_vector(0 - unsigned(div.res_u)) when (div.sign_mod = '1') else div.res_u;

  end generate; -- /divider_core_serial

  -- no divider --
  divider_core_serial_none:
  if not DIVISION_EN generate
    div.quotient  <= (others => '0');
    div.sign_mod  <= '0';
    div.rs2_abs   <= (others => '0');
    div.remainder <= (others => '0');
    div.sub       <= (others => '0');
    div.res_u     <= (others => '0');
    div.res       <= (others => '0');
  end generate;


  -- Data Output ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  operation_result: process(ctrl, ctrl_i.ir_funct3, mul.prod, div.res)
  begin
    res_o <= (others => '0'); -- default
    if (ctrl.out_en = '1') then
      case ctrl_i.ir_funct3 is
        when op_mul_c =>
          res_o <= mul.prod(31 downto 0);
        when op_mulh_c | op_mulhsu_c | op_mulhu_c =>
          res_o <= mul.prod(63 downto 32);
        when others => -- op_div_c | op_rem_c | op_divu_c | op_remu_c
          res_o <= div.res;
      end case;
    end if;
  end process operation_result;


end neorv32_cpu_cp_muldiv_rtl;
