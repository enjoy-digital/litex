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

  signal sreg_ext, sreg_sys : std_ulogic_vector(3 downto 0);

begin

  -- reset sequencer --
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

  -- output synchronizer --
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
  port (
    clk_i    : in  std_ulogic;                   -- global clock, rising edge
    rstn_i   : in  std_ulogic;                   -- global reset, low-active, async
    enable_i : in  std_ulogic;                   -- generator enable
    clk_en_o : out std_ulogic_vector(7 downto 0) -- prescaled clock-enables
  );
end neorv32_sys_clock;

architecture neorv32_sys_clock_rtl of neorv32_sys_clock is

  signal cnt, cnt2, edge : std_ulogic_vector(11 downto 0);

begin

  -- tick generator --
  ticker: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      cnt  <= (others => '0');
      cnt2 <= (others => '0');
    elsif rising_edge(clk_i) then
      if (enable_i = '1') then
        cnt <= std_ulogic_vector(unsigned(cnt) + 1);
      else
        cnt <= (others => '0'); -- reset if disabled
      end if;
      cnt2 <= cnt;
    end if;
  end process ticker;

  -- rising-edge detector --
  edge <= cnt and (not cnt2);

  -- clock enables: clk_en_o signals are high for one cycle --
  clk_en_o(clk_div2_c)    <= edge(0);  -- clk_i / 2
  clk_en_o(clk_div4_c)    <= edge(1);  -- clk_i / 4
  clk_en_o(clk_div8_c)    <= edge(2);  -- clk_i / 8
  clk_en_o(clk_div64_c)   <= edge(5);  -- clk_i / 64
  clk_en_o(clk_div128_c)  <= edge(6);  -- clk_i / 128
  clk_en_o(clk_div1024_c) <= edge(9);  -- clk_i / 1024
  clk_en_o(clk_div2048_c) <= edge(10); -- clk_i / 2048
  clk_en_o(clk_div4096_c) <= edge(11); -- clk_i / 4096

end neorv32_sys_clock_rtl;
