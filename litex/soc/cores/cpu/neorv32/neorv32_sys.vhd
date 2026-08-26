-- ================================================================================ --
-- NEORV32 SoC - System Infrastructure: Reset Sequencer                             --
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

entity neorv32_sys_reset is
  port (
    -- global control --
    clk_i       : in  std_ulogic; -- global clock, rising edge
    -- reset sources --
    rstn_ext_i  : in  std_ulogic; -- external reset, low-active, async
    rstn_wdt_i  : in  std_ulogic; -- watchdog reset, low-active, sync
    rstn_dbg_i  : in  std_ulogic; -- debugger reset, low-active, sync
    -- reset nets --
    rstn_ext_o  : out std_ulogic; -- external reset, low-active, synchronized
    rstn_sys_o  : out std_ulogic; -- system reset, low-active, synchronized
    -- processor reset outputs --
    xrstn_wdt_o : out std_ulogic; -- reset from watchdog, low-active, sync
    xrstn_ocd_o : out std_ulogic  -- reset from on-chip debugger, low-active, sync
  );
end neorv32_sys_reset;

architecture neorv32_sys_reset_rtl of neorv32_sys_reset is

  signal sreg_sys, sreg_ext : std_ulogic_vector(3 downto 0);

begin

  -- Reset Sequencer ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sequencer: process(rstn_ext_i, clk_i)
  begin
    if (rstn_ext_i = '0') then
      sreg_ext   <= (others => '0');
      rstn_ext_o <= '0';
      sreg_sys   <= (others => '0');
      rstn_sys_o <= '0';
    elsif rising_edge(clk_i) then
      -- external reset --
      sreg_ext   <= sreg_ext(sreg_ext'left-1 downto 0) & '1';
      rstn_ext_o <= and_reduce_f(sreg_ext);
      -- internal reset (synchronized sources) --
      if (rstn_wdt_i = '0') or (rstn_dbg_i = '0') then
        sreg_sys <= (others => '0');
      else
        sreg_sys <= sreg_sys(sreg_sys'left-1 downto 0) & '1';
      end if;
      rstn_sys_o <= and_reduce_f(sreg_sys);
    end if;
  end process sequencer;


  -- Processor Reset Output Synchronizer ----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  synchronizer: process(rstn_ext_i, clk_i)
  begin
    if (rstn_ext_i = '0') then
      xrstn_wdt_o <= '0';
      xrstn_ocd_o <= '0';
    elsif rising_edge(clk_i) then
      xrstn_wdt_o <= rstn_wdt_i;
      xrstn_ocd_o <= rstn_dbg_i;
    end if;
  end process synchronizer;


end neorv32_sys_reset_rtl;


-- ================================================================================ --
-- NEORV32 SoC - System Infrastructure: Clock Divider / Pulse Generator             --
-- -------------------------------------------------------------------------------- --
-- This module generates clock-enable pulses (high for only one clock cycle)        --
-- derived from the processor's main clock.                                         --
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

entity neorv32_sys_clock is
  generic (
    NUM_EN : natural -- number of enable-channels
  );
  port (
    clk_i    : in  std_ulogic; -- global clock, rising edge
    rstn_i   : in  std_ulogic; -- global reset, low-active, async
    enable_i : in  std_ulogic_vector(NUM_EN-1 downto 0); -- enable-channels
    clk_en_o : out std_ulogic_vector(7 downto 0) -- clock-enable ticks
  );
end neorv32_sys_clock;

architecture neorv32_sys_clock_rtl of neorv32_sys_clock is

  signal en : std_ulogic;
  signal cnt, cnt2 : std_ulogic_vector(11 downto 0);

begin

  -- Clock Tick Generator -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  ticker: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      en   <= '0';
      cnt  <= (others => '0');
      cnt2 <= (others => '0');
    elsif rising_edge(clk_i) then
      en <= or_reduce_f(enable_i);
      if (en = '1') then
        cnt <= std_ulogic_vector(unsigned(cnt) + 1);
      else
        cnt <= (others => '0'); -- reset if disabled
      end if;
      cnt2 <= cnt;
    end if;
  end process ticker;

  -- clock enables: rising edge detectors, clk_en_o signals are high for one cycle --
  clk_en_o(clk_div2_c)    <= cnt(0)  and (not cnt2(0));  -- clk_i / 2
  clk_en_o(clk_div4_c)    <= cnt(1)  and (not cnt2(1));  -- clk_i / 4
  clk_en_o(clk_div8_c)    <= cnt(2)  and (not cnt2(2));  -- clk_i / 8
  clk_en_o(clk_div64_c)   <= cnt(5)  and (not cnt2(5));  -- clk_i / 64
  clk_en_o(clk_div128_c)  <= cnt(6)  and (not cnt2(6));  -- clk_i / 128
  clk_en_o(clk_div1024_c) <= cnt(9)  and (not cnt2(9));  -- clk_i / 1024
  clk_en_o(clk_div2048_c) <= cnt(10) and (not cnt2(10)); -- clk_i / 2048
  clk_en_o(clk_div4096_c) <= cnt(11) and (not cnt2(11)); -- clk_i / 4096


end neorv32_sys_clock_rtl;
