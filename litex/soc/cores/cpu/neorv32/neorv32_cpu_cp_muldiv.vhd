-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: Integer Mul/Div Unit (RISC-V 'M'/'Zmmul' Extensions) --
-- -------------------------------------------------------------------------------- --
-- Multiplier core (signed/unsigned) uses serial add-and-shift algorithm.           --
-- Multiplications can be mapped to DSP blocks (faster!) when FAST_MUL_EN = true.   --
-- Divider core (unsigned-only; pre and post sign-compensation logic) uses serial   --
-- restoring serial algorithm.                                                      --
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
    rs1_i   : in  std_ulogic_vector(31 downto 0); -- rf source 1
    rs2_i   : in  std_ulogic_vector(31 downto 0); -- rf source 2
    -- result and status --
    res_o   : out std_ulogic_vector(31 downto 0); -- operation result
    valid_o : out std_ulogic                      -- data output valid
  );
end neorv32_cpu_cp_muldiv;

architecture neorv32_cpu_cp_muldiv_rtl of neorv32_cpu_cp_muldiv is

  -- absolute value --
  function abs_f(input: std_ulogic_vector; is_signed: std_ulogic) return std_ulogic_vector is
  begin
    if (input(input'left) = '1') and (is_signed = '1') then
      return std_ulogic_vector(0 - unsigned(input));
    else
      return input;
    end if;
  end function abs_f;

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
    state      : state_t;
    cnt        : std_ulogic_vector(4 downto 0);
    rs1_signed : std_ulogic;
    rs2_signed : std_ulogic;
    out_en     : std_ulogic;
  end record;
  signal ctrl : ctrl_t;

  -- divider core --
  type div_t is record
    start : std_ulogic;
    quot  : std_ulogic_vector(31 downto 0);
    rema  : std_ulogic_vector(31 downto 0);
    sign  : std_ulogic;
    sub_a : std_ulogic_vector(32 downto 0);
    sub_s : std_ulogic;
    sub   : std_ulogic_vector(32 downto 0);
    res_u : std_ulogic_vector(31 downto 0);
    res   : std_ulogic_vector(31 downto 0);
  end record;
  signal div : div_t;

  -- multiplier core --
  type mul_t is record
    start : std_ulogic;
    res   : std_ulogic_vector(63 downto 0);
    add   : std_ulogic_vector(32 downto 0);
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
      ctrl.cnt    <= std_ulogic_vector(to_unsigned(30, ctrl.cnt'length)); -- cycle counter initialization

      -- fsm --
      case ctrl.state is

        when S_BUSY => -- processing
        -- ------------------------------------------------------------
          ctrl.cnt <= std_ulogic_vector(unsigned(ctrl.cnt) - 1);
          if (or_reduce_f(ctrl.cnt) = '0') or (ctrl_i.cpu_trap = '1') then -- abort on trap
            ctrl.state <= S_DONE;
          end if;

        when S_DONE => -- S_DONE: final step / enable output for one cycle
        -- ------------------------------------------------------------
          ctrl.out_en <= '1';
          ctrl.state  <= S_IDLE;

        when others => -- S_IDLE: wait for start signal
        -- ------------------------------------------------------------
          if (valid_cmd = '1') then -- trigger new operation
            if (ctrl_i.ir_funct3(2) = '0') and FAST_MUL_EN then -- is fast multiplication?
              ctrl.state <= S_DONE;
            else -- serial division or serial multiplication
              ctrl.state <= S_BUSY;
            end if;
          end if;

      end case;
    end if;
  end process control;

  -- done? assert one cycle before actual data output --
  valid_o <= '1' when (ctrl.state = S_DONE) else '0';

  -- input operands treated as signed? --
  ctrl.rs1_signed <= '1' when (ctrl_i.ir_funct3 = op_mulh_c) or (ctrl_i.ir_funct3 = op_mulhsu_c) or
                              (ctrl_i.ir_funct3 = op_div_c)  or (ctrl_i.ir_funct3 = op_rem_c) else '0';
  ctrl.rs2_signed <= '1' when (ctrl_i.ir_funct3 = op_mulh_c) or
                              (ctrl_i.ir_funct3 = op_div_c)  or (ctrl_i.ir_funct3 = op_rem_c) else '0';

  -- operation trigger --
  mul.start <= '1' when (valid_cmd = '1') and (ctrl_i.ir_funct3(2) = '0') else '0';
  div.start <= '1' when (valid_cmd = '1') and (ctrl_i.ir_funct3(2) = '1') else '0';


  -- Multiplier Core - Full Parallel --------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  multiplier_core_parallel:
  if FAST_MUL_EN generate
    multiplier_inst: entity neorv32.neorv32_prim_mul
    generic map (
      DWIDTH => 32
    )
    port map (
      clk_i    => clk_i,
      rstn_i   => rstn_i,
      en_i     => mul.start,
      opa_i    => rs1_i,
      opa_sn_i => ctrl.rs1_signed,
      opb_i    => rs2_i,
      opb_sn_i => ctrl.rs2_signed,
      res_o    => mul.res
    );
    mul.add <= (others => '0'); -- unused
  end generate;


  -- Multiplier Core - Iterative ------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  multiplier_core_serial:
  if not FAST_MUL_EN generate

    -- shift-and-add algorithm --
    multiplier_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        mul.res <= (others => '0');
      elsif rising_edge(clk_i) then
        if (mul.start = '1') then -- start new multiplication
          mul.res(63 downto 32) <= (others => '0');
          mul.res(31 downto 0)  <= rs1_i;
        elsif (ctrl.state /= S_IDLE) then -- processing steps or sign-finalization step
          mul.res(63 downto 31) <= mul.add(32 downto 0);
          mul.res(30 downto 0)  <= mul.res(31 downto 1);
        end if;
      end if;
    end process multiplier_core;

    -- multiply by 0/-1/+1 via shift and subtraction/addition --
    mul_update: process(mul.res, ctrl, rs2_i)
      variable sign_v : std_ulogic;
      variable opb_v  : unsigned(32 downto 0);
    begin
      sign_v := mul.res(mul.res'left) and ctrl.rs2_signed; -- product sign extension bit
      opb_v  := unsigned((rs2_i(rs2_i'left) and ctrl.rs2_signed) & rs2_i);
      if (mul.res(0) = '1') then -- multiply by 1
        if (ctrl.state = S_DONE) and (ctrl.rs1_signed = '1') then -- take care of negative weighted MSB -> multiply by -1
          mul.add <= std_ulogic_vector(unsigned(sign_v & mul.res(63 downto 32)) - opb_v);
        else -- multiply by +1
          mul.add <= std_ulogic_vector(unsigned(sign_v & mul.res(63 downto 32)) + opb_v);
        end if;
      else -- multiply by 0
        mul.add <= sign_v & mul.res(63 downto 32);
      end if;
    end process mul_update;

  end generate;


  -- Divider Core - Iterative ---------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  divider_core_serial:
  if DIVISION_EN generate

    -- unsigned restoring division algorithm --
    divider_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        div.rema <= (others => '0');
        div.quot <= (others => '0');
        div.sign <= '0';
      elsif rising_edge(clk_i) then
        if (div.start = '1') then -- start new division
          div.rema <= (others => '0');
          div.quot <= abs_f(rs1_i, ctrl.rs1_signed);
          case ctrl_i.ir_funct3(1 downto 0) is -- check for result's sign compensation
            when "00"   => div.sign <= or_reduce_f(rs2_i) and (rs1_i(rs1_i'left) xor rs2_i(rs2_i'left)); -- signed div
            when "10"   => div.sign <= rs1_i(rs1_i'left); -- signed rem
            when others => div.sign <= '0';
          end case;
        elsif (ctrl.state = S_BUSY) or (ctrl.state = S_DONE) then -- running?
          div.quot <= div.quot(30 downto 0) & (not div.sub(32));
          if (div.sub(32) = '0') then
            div.rema <= div.sub(31 downto 0);
          else -- underflow: restore
            div.rema <= div.rema(30 downto 0) & div.quot(31);
          end if;
        end if;
      end if;
    end process divider_core;

    -- do another subtraction (and shift) --
    div.sub_a <= '0' & div.rema(30 downto 0) & div.quot(31);
    div.sub_s <= rs2_i(31) and ctrl.rs2_signed;
    div.sub   <= std_ulogic_vector(unsigned(div.sub_a) - unsigned(div.sub_s & rs2_i)) when (div.sub_s = '0') else
                 std_ulogic_vector(unsigned(div.sub_a) + unsigned(div.sub_s & rs2_i));

    -- result select and sign compensation --
    div.res_u <= div.quot when (ctrl_i.ir_funct3(2 downto 1) = op_div_c(2 downto 1)) else div.rema;
    div.res   <= std_ulogic_vector(0 - unsigned(div.res_u)) when (div.sign = '1') else div.res_u;

  end generate;

  -- no divider --
  divider_core_serial_none:
  if not DIVISION_EN generate
    div.quot  <= (others => '0');
    div.rema  <= (others => '0');
    div.sign  <= '0';
    div.sub_a <= (others => '0');
    div.sub_s <= '0';
    div.sub   <= (others => '0');
    div.res_u <= (others => '0');
    div.res   <= (others => '0');
  end generate;


  -- Data Output ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  operation_result: process(ctrl, ctrl_i.ir_funct3, mul.res, div.res)
  begin
    res_o <= (others => '0');
    if (ctrl.out_en = '1') then
      case ctrl_i.ir_funct3 is
        when op_mul_c =>
          res_o <= mul.res(31 downto 0);
        when op_mulh_c | op_mulhsu_c | op_mulhu_c =>
          res_o <= mul.res(63 downto 32);
        when others =>
          res_o <= div.res;
      end case;
    end if;
  end process operation_result;


end neorv32_cpu_cp_muldiv_rtl;
