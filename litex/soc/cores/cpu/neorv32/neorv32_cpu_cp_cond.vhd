-- ================================================================================ --
-- NEORV32 CPU - Co-Processor: RISC-V Cond. Operations ('Zicond') ISA Extension     --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2024 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_cp_cond is
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
end neorv32_cpu_cp_cond;

architecture neorv32_cpu_cp_cond_rtl of neorv32_cpu_cp_cond is

  constant zero_c : std_ulogic_vector(XLEN-1 downto 0) := (others => '0');
  signal valid_cmd, rs2_zero, condition : std_ulogic;

begin

  -- Valid Instruction? ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  valid_cmd <= '1' when (ctrl_i.alu_cp_alu = '1') and (ctrl_i.ir_opcode(5) = '1') and
                        (ctrl_i.ir_funct3(2) = '1') and (ctrl_i.ir_funct3(0) = '1') and
                        (ctrl_i.ir_funct12(11 downto 5) = "0000111") else '0';


  -- Conditional Output ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cond_out: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      res_o <= (others => '0');
    elsif rising_edge(clk_i) then
      if (valid_cmd = '1') and (condition = '1') then -- unit triggered and condition true
        res_o <= rs1_i;
      else
        res_o <= (others => '0');
      end if;
    end if;
  end process cond_out;

  -- condition check --
  rs2_zero  <= '1' when (rs2_i = zero_c) else '0';
  condition <= rs2_zero xnor ctrl_i.ir_funct3(1); -- equal zero / non equal zero

  -- processing done --
  valid_o <= valid_cmd;


end neorv32_cpu_cp_cond_rtl;
