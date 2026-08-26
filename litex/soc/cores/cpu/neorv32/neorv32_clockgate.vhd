-- ================================================================================ --
-- NEORV32 - Generic Clock Gating Switch                                            --
-- -------------------------------------------------------------------------------- --
-- Especially for FPGA setups, it is highly recommended to replace this default     --
-- module by a technology-/platform-specific macro or primitive (e.g. a dedicated   --
-- clock mux) wrapper.                                                              --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

entity neorv32_clockgate is
  port (
    clk_i  : in  std_ulogic; -- global clock line, always-on
    rstn_i : in  std_ulogic; -- global reset line, low-active, async
    halt_i : in  std_ulogic; -- shut down clock output when set
    clk_o  : out std_ulogic  -- switched clock output
  );
end neorv32_clockgate;

architecture neorv32_clockgate_rtl of neorv32_clockgate is

  signal enable : std_ulogic;

begin

  -- Warn about Clock Gating ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  assert false report "[NEORV32] Clock gating enabled (using default/generic clock switch)." severity warning;


  -- Clock Switch ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  clock_switch: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      enable <= '1';
    elsif falling_edge(clk_i) then -- update on falling edge to avoid glitches on 'clk_o'
      enable <= not halt_i;
    end if;
  end process clock_switch;

  -- for FPGA designs better replace this by a technology-specific primitive or macro --
  clk_o <= clk_i when (enable = '1') else '0';


end neorv32_clockgate_rtl;
