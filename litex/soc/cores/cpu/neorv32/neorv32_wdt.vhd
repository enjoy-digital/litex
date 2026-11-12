-- ================================================================================ --
-- NEORV32 SoC - Watch Dog Timer (WDT)                                              --
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

entity neorv32_wdt is
  port (
    clk_i       : in  std_ulogic;                    -- global clock line
    rstn_ext_i  : in  std_ulogic;                    -- external reset, low-active
    rstn_dbg_i  : in  std_ulogic;                    -- debugger reset, low-active
    rstn_sys_i  : in  std_ulogic;                    -- system reset, low-active
    bus_req_i   : in  bus_req_t;                     -- bus request
    bus_rsp_o   : out bus_rsp_t;                     -- bus response
    clkgen_i    : in  std_ulogic_vector(7 downto 0); -- prescaled clock enables
    rstn_o      : out std_ulogic                     -- timeout reset, low_active, sync
  );
end neorv32_wdt;

architecture neorv32_wdt_rtl of neorv32_wdt is

  -- Reset password --
  constant reset_pwd_c : std_ulogic_vector(31 downto 0) := x"709d1ab3";

  -- Control register bits --
  constant ctrl_enable_c     : natural :=  0; -- r/w: WDT enable
  constant ctrl_lock_c       : natural :=  1; -- r/w: lock write access to control register when set
  constant ctrl_rcause_lo_c  : natural :=  2; -- r/-: cause of last system reset, bit 0, LSB
  constant ctrl_rcause_hi_c  : natural :=  3; -- r/-: cause of last system reset, bit 1, MSB
  constant ctrl_timeout_lo_c : natural :=  8; -- r/w: timeout value, bit 0, LSB
  constant ctrl_timeout_hi_c : natural := 31; -- r/w: timeout value, bit 23, MSB

  -- control register --
  type ctrl_t is record
    enable  : std_ulogic;
    lock    : std_ulogic;
    timeout : std_ulogic_vector(23 downto 0);
  end record;
  signal ctrl : ctrl_t;

  signal prsc_tick      : std_ulogic; -- prescaler clock generator
  signal cnt            : std_ulogic_vector(23 downto 0); -- timeout counter
  signal cnt_started    : std_ulogic; -- set when timeout counter has started
  signal cnt_inc        : std_ulogic; -- increment counter when set
  signal cnt_timeout    : std_ulogic; -- counter matches programmed timeout value
  signal reset_cause    : std_ulogic_vector(1 downto 0); -- cause of last reset
  signal hw_rst_timeout : std_ulogic; -- trigger reset because of timeout
  signal hw_rst_access  : std_ulogic; -- trigger reset because of illegal access in strict mode
  signal reset_wdt      : std_ulogic; -- reset timeout counter ("feed the watch dog")
  signal reset_force    : std_ulogic; -- trigger reset because of illegal access in strict mode (raw)

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_sys_i, clk_i)
  begin
    if (rstn_sys_i = '0') then
      bus_rsp_o    <= rsp_terminate_c;
      ctrl.enable  <= '0'; -- disable WDT after reset
      ctrl.lock    <= '0'; -- unlock after reset
      ctrl.timeout <= (others => '0');
      reset_wdt    <= '0';
      reset_force  <= '0';
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      -- defaults --
      reset_wdt   <= '0';
      reset_force <= '0';
      -- bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then -- control register
            if (ctrl.lock = '0') then -- update configuration only if not locked
              ctrl.enable  <= bus_req_i.data(ctrl_enable_c);
              ctrl.lock    <= bus_req_i.data(ctrl_lock_c);
              ctrl.timeout <= bus_req_i.data(ctrl_timeout_hi_c downto ctrl_timeout_lo_c);
            else -- write access attempt to locked CTRL register
              reset_force <= '1';
            end if;
          else -- reset timeout counter - password check
            if (bus_req_i.data(31 downto 0) = reset_pwd_c) then
              reset_wdt <= '1'; -- password correct
            else
              reset_force <= '1'; -- password incorrect
            end if;
          end if;
        else -- read access
          bus_rsp_o.data(ctrl_enable_c)                              <= ctrl.enable;
          bus_rsp_o.data(ctrl_lock_c)                                <= ctrl.lock;
          bus_rsp_o.data(ctrl_rcause_hi_c downto ctrl_rcause_lo_c)   <= reset_cause;
          bus_rsp_o.data(ctrl_timeout_hi_c downto ctrl_timeout_lo_c) <= ctrl.timeout;
        end if;
      end if;
    end if;
  end process bus_access;


  -- Timeout Counter ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  wdt_counter: process(rstn_sys_i, clk_i)
  begin
    if (rstn_sys_i = '0') then
      prsc_tick   <= '0';
      cnt_inc     <= '0';
      cnt_started <= '0';
      cnt         <= (others => '0');
    elsif rising_edge(clk_i) then
      prsc_tick   <= clkgen_i(clk_div4096_c); -- clock-enable tick
      cnt_inc     <= prsc_tick and cnt_started; -- clock tick and started
      cnt_started <= ctrl.enable and (cnt_started or prsc_tick); -- start with next clock tick
      if (ctrl.enable = '0') or (reset_wdt = '1') then -- watchdog disabled or reset with correct password
        cnt <= (others => '0');
      elsif (cnt_inc = '1') then
        cnt <= std_ulogic_vector(unsigned(cnt) + 1);
      end if;
    end if;
  end process wdt_counter;

  -- timeout detector --
  cnt_timeout <= '1' when (cnt_started = '1') and (cnt = ctrl.timeout) else '0';


  -- Reset Generator ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  reset_generator: process(rstn_sys_i, clk_i)
  begin
    if (rstn_sys_i = '0') then
      hw_rst_timeout <= '0';
      hw_rst_access  <= '0';
    elsif rising_edge(clk_i) then
      hw_rst_timeout <= ctrl.enable and cnt_timeout and prsc_tick; -- timeout
      hw_rst_access  <= ctrl.enable and ctrl.lock and reset_force; -- locked and incorrect password
    end if;
  end process reset_generator;

  -- system-wide reset --
  rstn_o <= not (hw_rst_timeout or hw_rst_access);


  -- Reset-Cause Indicator ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  reset_identifier: process(rstn_ext_i, clk_i)
  begin
    if (rstn_ext_i = '0') then
      reset_cause <= "00"; -- reset from external hardware signal
    elsif rising_edge(clk_i) then
      if (rstn_dbg_i = '0') then
        reset_cause <= "01"; -- reset from on-chip debugger
      elsif (hw_rst_timeout = '1') then
        reset_cause <= "10"; -- reset from watchdog timer
      elsif (hw_rst_access = '1') then
        reset_cause <= "11"; -- reset from invalid watchdog access (locked or incorrect password)
      end if;
    end if;
  end process reset_identifier;


end neorv32_wdt_rtl;
