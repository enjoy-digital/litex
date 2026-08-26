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
    rs1_i   : in  std_ulogic_vector(31 downto 0); -- rf source 1
    shamt_i : in  std_ulogic_vector(4 downto 0);  -- shift amount
    -- result and status --
    res_o   : out std_ulogic_vector(31 downto 0); -- operation result
    valid_o : out std_ulogic                      -- data output valid
  );
end neorv32_cpu_cp_shifter;

architecture neorv32_cpu_cp_shifter_rtl of neorv32_cpu_cp_shifter is

  -- instruction decode --
  signal valid_cmd : std_ulogic;

  -- serial shifter --
  type serial_t is record
    busy : std_ulogic;
    done : std_ulogic;
    oe   : std_ulogic;
    cnt  : std_ulogic_vector(4 downto 0);
    sreg : std_ulogic_vector(31 downto 0);
  end record;
  signal serial : serial_t;

  -- barrel shifter --
  type level_t is array (5 downto 0) of std_ulogic_vector(31 downto 0);
  type barrel_t is record
    lvl : level_t;
    sgn : std_ulogic;
    oe  : std_ulogic;
    res : std_ulogic_vector(31 downto 0);
  end record;
  signal barrel : barrel_t;

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

    shifter: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        serial.busy <= '0';
        serial.oe   <= '0';
        serial.cnt  <= (others => '0');
        serial.sreg <= (others => '0');
      elsif rising_edge(clk_i) then
        -- arbitration --
        if (valid_cmd = '1') then
          serial.busy <= '1';
        elsif (serial.done = '1') or (ctrl_i.cpu_trap = '1') then -- abort on trap
          serial.busy <= '0';
        serial.oe <= serial.busy and serial.done;
        end if;
        -- shift register --
        if (valid_cmd = '1') then -- trigger new operation
          serial.cnt  <= shamt_i;
          serial.sreg <= rs1_i;
        elsif (or_reduce_f(serial.cnt) = '1') then -- operation in progress
          serial.cnt <= std_ulogic_vector(unsigned(serial.cnt) - 1);
          if (ctrl_i.ir_funct3(2) = '0') then -- shift left logical
            serial.sreg <= serial.sreg(serial.sreg'left-1 downto 0) & '0';
          else -- shift right (arithmetical)
            serial.sreg <= (serial.sreg(serial.sreg'left) and ctrl_i.ir_funct12(10)) & serial.sreg(serial.sreg'left downto 1);
          end if;
        end if;
      end if;
    end process shifter;

    -- shift control --
    serial.done <= not or_reduce_f(serial.cnt(serial.cnt'left downto 1));
    valid_o     <= serial.busy and serial.done;
    res_o       <= serial.sreg when (serial.oe = '1') else (others => '0');

    -- unused --
    barrel.lvl <= (others => (others => '0'));
    barrel.sgn <= '0';
    barrel.oe  <= '0';
    barrel.res <= (others => '0');

  end generate;


  -- Barrel Shifter (fast but large) --------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  barrel_shifter:
  if FAST_SHIFT_EN generate

    -- input layer: convert left shifts to right shifts using bit-reversal --
    barrel.lvl(0) <= bit_rev_f(rs1_i) when (ctrl_i.ir_funct3(2) = '0') else rs1_i;
    barrel.sgn    <= rs1_i(31) and ctrl_i.ir_funct12(10); -- sign (extension) for arithmetic shifts

    -- mux layers: right-shifts only --
    barrel_shifter_gen:
    for i in 0 to 4 generate
      barrel.lvl(i+1)(31 downto 32-2**i) <= (others => barrel.sgn)        when (shamt_i(i) = '1') else barrel.lvl(i)(31 downto 32-2**i);
      barrel.lvl(i+1)(31-2**i downto 0)  <= barrel.lvl(i)(31 downto 2**i) when (shamt_i(i) = '1') else barrel.lvl(i)(31-2**i downto 0);
    end generate;

    -- register layer --
    pipe_reg: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        barrel.oe  <= '0';
        barrel.res <= (others => '0');
      elsif rising_edge(clk_i) then
        barrel.oe  <= valid_cmd;
        barrel.res <= barrel.lvl(5);
      end if;
    end process pipe_reg;

    -- output layer: re-convert original left shifts and result gate --
    res_o   <= (others => '0') when (barrel.oe = '0') else bit_rev_f(barrel.res) when (ctrl_i.ir_funct3(2) = '0') else barrel.res;
    valid_o <= valid_cmd;

    -- unused --
    serial.busy <= '0';
    serial.done <= '0';
    serial.oe   <= '0';
    serial.cnt  <= (others => '0');
    serial.sreg <= (others => '0');

  end generate;


end neorv32_cpu_cp_shifter_rtl;
