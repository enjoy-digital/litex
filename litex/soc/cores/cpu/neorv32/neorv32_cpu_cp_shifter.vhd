-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: Shifter (CPU Base ISA)                               --
-- -------------------------------------------------------------------------------- --
-- FAST_SHIFT_EN = false -> Use bit-serial shifter architecture (small but slow)    --
-- FAST_SHIFT_EN = true  -> Use barrel shifter architecture (large but fast)        --
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

entity neorv32_cpu_cp_shifter is
  generic (
    FAST_SHIFT_EN : boolean -- implement fast but large barrel shifter
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    ctrl_i  : in  ctrl_bus_t; -- main control bus
    -- data input --
    rs1_i   : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 1
    shamt_i : in  std_ulogic_vector(index_size_f(XLEN)-1 downto 0); -- shift amount
    -- result and status --
    res_o   : out std_ulogic_vector(XLEN-1 downto 0); -- operation result
    valid_o : out std_ulogic -- data output valid
  );
end neorv32_cpu_cp_shifter;

architecture neorv32_cpu_cp_shifter_rtl of neorv32_cpu_cp_shifter is

  -- instruction decode --
  signal valid_cmd : std_ulogic;

  -- serial shifter --
  type shifter_t is record
    busy    : std_ulogic;
    run     : std_ulogic;
    done    : std_ulogic;
    done_ff : std_ulogic;
    cnt     : std_ulogic_vector(index_size_f(XLEN)-1 downto 0);
    sreg    : std_ulogic_vector(XLEN-1 downto 0);
  end record;
  signal shifter : shifter_t;

  -- barrel shifter --
  type bs_level_t is array (index_size_f(XLEN) downto 0) of std_ulogic_vector(XLEN-1 downto 0);
  signal bs_level  : bs_level_t;
  signal bs_sign   : std_ulogic;
  signal bs_result : std_ulogic_vector(XLEN-1 downto 0);

begin

  -- Valid Instruction? ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  valid_cmd <= '1' when (ctrl_i.alu_cp_alu = '1') and (
                         ((ctrl_i.ir_funct3 = funct3_sll_c) and (ctrl_i.ir_funct12(11 downto 5) = "0000000")) or -- SLL[I]
                         ((ctrl_i.ir_funct3 = funct3_sr_c)  and (ctrl_i.ir_funct12(11 downto 5) = "0000000")) or -- SRL[I]
                         ((ctrl_i.ir_funct3 = funct3_sr_c)  and (ctrl_i.ir_funct12(11 downto 5) = "0100000")) -- SRA[I]
                        ) else '0';


  -- Serial Shifter (small but slow) --------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  serial_shifter:
  if not FAST_SHIFT_EN generate

    serial_shifter_core: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        shifter.busy    <= '0';
        shifter.done_ff <= '0';
        shifter.cnt     <= (others => '0');
        shifter.sreg    <= (others => '0');
      elsif rising_edge(clk_i) then
        -- arbitration --
        shifter.done_ff <= shifter.busy and shifter.done;
        if (valid_cmd = '1') then
          shifter.busy <= '1';
        elsif (shifter.done = '1') or (ctrl_i.cpu_trap = '1') then -- abort on trap
          shifter.busy <= '0';
        end if;
        -- shift register --
        if (valid_cmd = '1') then -- trigger new operation
          shifter.cnt  <= shamt_i;
          shifter.sreg <= rs1_i;
        elsif (shifter.run = '1') then -- operation in progress
          shifter.cnt <= std_ulogic_vector(unsigned(shifter.cnt) - 1);
          if (ctrl_i.ir_funct3(2) = '0') then -- SLL: shift left logical
            shifter.sreg <= shifter.sreg(shifter.sreg'left-1 downto 0) & '0';
          else -- SRL: shift right logical / SRA: shift right arithmetical
            shifter.sreg <= (shifter.sreg(shifter.sreg'left) and ctrl_i.ir_funct12(10)) & shifter.sreg(shifter.sreg'left downto 1);
          end if;
        end if;
      end if;
    end process serial_shifter_core;

    -- shift control --
    shifter.run  <= or_reduce_f(shifter.cnt);
    shifter.done <= not or_reduce_f(shifter.cnt(shifter.cnt'left downto 1));
    valid_o      <= shifter.busy and shifter.done;
    res_o        <= shifter.sreg when (shifter.done_ff = '1') else (others => '0');

  end generate;


  -- Barrel Shifter (fast but large) --------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  barrel_shifter:
  if FAST_SHIFT_EN generate

    -- input layer: operand gating and convert left shifts to right shifts by bit-reversal --
    bs_level(0) <= (others => '0') when (valid_cmd = '0') else bit_rev_f(rs1_i) when (ctrl_i.ir_funct3(2) = '0') else rs1_i;
    bs_sign <= rs1_i(XLEN-1) and ctrl_i.ir_funct12(10) and valid_cmd; -- sign extension for arithmetic shifts

    -- mux layers: right-shifts only --
    barrel_shifter_core:
    for i in 0 to index_size_f(XLEN)-1 generate
      bs_level(i+1)(XLEN-1 downto XLEN-(2**i)) <= (others => bs_sign)             when (shamt_i(i) = '1') else bs_level(i)(XLEN-1 downto XLEN-(2**i));
      bs_level(i+1)((XLEN-(2**i))-1 downto 0)  <= bs_level(i)(XLEN-1 downto 2**i) when (shamt_i(i) = '1') else bs_level(i)((XLEN-(2**i))-1 downto 0);
    end generate;

    -- register layer (can be moved by the register balancing) --
    barrel_shifter_buf: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        bs_result <= (others => '0');
      elsif rising_edge(clk_i) then
        bs_result <= bs_level(bs_level'left);
      end if;
    end process barrel_shifter_buf;

    -- output layer: re-convert original left shifts --
    res_o   <= bit_rev_f(bs_result) when (ctrl_i.ir_funct3(2) = '0') else bs_result;
    valid_o <= valid_cmd;

  end generate;


end neorv32_cpu_cp_shifter_rtl;
