-- ================================================================================ --
-- NEORV32 OCD - RISC-V-Compatible Authentication Module for the On-Chip Debugger   --
-- -------------------------------------------------------------------------------- --
-- Note that this module (in its default state) just provides a very simple and     --
-- UNSECURE authentication mechanism that is meant as an example to showcase the    --
-- interface. Users should replace this module to implement a custom (and SECURE)   --
-- authentication mechanism.                                                        --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

entity neorv32_debug_auth is
  port (
    -- global control --
    clk_i    : in  std_ulogic; -- global clock
    rstn_i   : in  std_ulogic; -- global reset, low-active, asynchronous
    -- register interface --
    we_i     : in  std_ulogic; -- wdata_i valid when high
    re_i     : in  std_ulogic; -- rdata_o has been consumed by the debugger when high
    wdata_i  : in  std_ulogic_vector(31 downto 0); -- write data (from debugger)
    rdata_o  : out std_ulogic_vector(31 downto 0); -- read data (to debugger)
    -- status --
    enable_i : in  std_ulogic; -- authenticator enabled when high; reset & clear authentication when low
    busy_o   : out std_ulogic; -- authenticator is busy when high; no further read/write accesses
    valid_o  : out std_ulogic  -- high when authentication passed; unlocks the on-chip debugger
  );
end neorv32_debug_auth;

architecture neorv32_debug_auth_rtl of neorv32_debug_auth is

  signal authenticated_q : std_ulogic;

begin

  -- Warn about Default Authenticator -------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  assert false report "[NEORV32] using DEFAULT on-chip debugger authenticator. Replace by custom module." severity warning;


  -- Exemplary Authentication Mechanism -----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  auth_ctrl: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      authenticated_q <= '0';
    elsif rising_edge(clk_i) then
      if (enable_i = '0') then
        authenticated_q <= '0'; -- clear authentication when disabled
      elsif (we_i = '1') then
        authenticated_q <= wdata_i(0); -- just write 1 to authenticate
      end if;
    end if;
  end process auth_ctrl;

  -- authenticator busy --
  busy_o <= '0'; -- this simple authenticator is always ready

  -- authentication passed --
  valid_o <= authenticated_q;

  -- read data --
  rdata_o <= (others => '0'); -- there is nothing to read here


end neorv32_debug_auth_rtl;
