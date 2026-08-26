-- ================================================================================ --
-- NEORV32 SoC - External Bus Interface (XBUS)                                      --
-- -------------------------------------------------------------------------------- --
-- Converts internal bus transactions into Wishbone b4-compatible bus accesses.     --
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

entity neorv32_xbus is
  generic (
    TIMEOUT_VAL : natural; -- cycles after an UNACKNOWLEDGED bus access triggers a bus fault exception
    REGSTAGE_EN : boolean  -- add XBUS register stage
  );
  port (
    clk_i      : in  std_ulogic; -- global clock line
    rstn_i     : in  std_ulogic; -- global reset line, low-active
    bus_req_i  : in  bus_req_t;  -- bus request
    bus_rsp_o  : out bus_rsp_t;  -- bus response
    xbus_adr_o : out std_ulogic_vector(31 downto 0); -- address
    xbus_dat_i : in  std_ulogic_vector(31 downto 0); -- read data
    xbus_dat_o : out std_ulogic_vector(31 downto 0); -- write data
    xbus_tag_o : out std_ulogic_vector(2 downto 0); -- access tag
    xbus_we_o  : out std_ulogic; -- read/write
    xbus_sel_o : out std_ulogic_vector(3 downto 0); -- byte enable
    xbus_stb_o : out std_ulogic; -- strobe
    xbus_cyc_o : out std_ulogic; -- valid cycle
    xbus_ack_i : in  std_ulogic; -- transfer acknowledge
    xbus_err_i : in  std_ulogic  -- transfer error
  );
end neorv32_xbus;

architecture neorv32_xbus_rtl of neorv32_xbus is

  -- register stage --
  signal bus_req : bus_req_t;
  signal bus_rsp : bus_rsp_t;

  -- bus arbiter --
  signal pending : std_ulogic_vector(1 downto 0);
  signal timeout : std_ulogic;
  signal timecnt : std_ulogic_vector(index_size_f(TIMEOUT_VAL) downto 0);

begin

  -- Optional Register Stage ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  reg_stage_inst: entity neorv32.neorv32_bus_reg
  generic map (
    REQ_REG_EN => REGSTAGE_EN,
    RSP_REG_EN => REGSTAGE_EN
  )
  port map (
    clk_i        => clk_i,
    rstn_i       => rstn_i,
    host_req_i   => bus_req_i,
    host_rsp_o   => bus_rsp_o,
    device_req_o => bus_req,
    device_rsp_i => bus_rsp
  );


  -- Bus Arbiter ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  arbiter: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      pending <= (others => '0');
    elsif rising_edge(clk_i) then
      case pending is

        when "10" => -- single access / atomic access (2nd access: store)
        -- ------------------------------------------------------------
          if (xbus_ack_i = '1') or (xbus_err_i = '1') or (timeout = '1') then
            pending <= "00";
          end if;

        when "11" => -- atomic access (1st access: load)
        -- ------------------------------------------------------------
          if (xbus_err_i = '1') or (timeout = '1') then -- abort if error
            pending <= "00";
          elsif (xbus_ack_i = '1') then
            pending <= "10";
          end if;

        when others => -- "0-": idle; waiting for request
        -- ------------------------------------------------------------
          if (bus_req.stb = '1') then
            if (bus_req.amo = '1') then
              pending <= "11";
            else
              pending <= "10";
            end if;
          end if;

      end case;
    end if;
  end process arbiter;


  -- Bus Timeout ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  timeout_enabled:
  if TIMEOUT_VAL /= 0 generate
    timeout_counter: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        timecnt <= (others => '0');
        timeout <= '0';
      elsif rising_edge(clk_i) then
        if (pending(1) = '0') then
          timecnt <= (others => '0');
        else
          timecnt <= std_ulogic_vector(unsigned(timecnt) + 1);
        end if;
        if (unsigned(timecnt) = TIMEOUT_VAL) then
          timeout <= '1';
        else
          timeout <= '0';
        end if;
      end if;
    end process timeout_counter;
  end generate;

  timeout_disabled:
  if TIMEOUT_VAL = 0 generate
    timecnt <= (others => '0');
    timeout <= '0';
  end generate;

  -- no-timeout warning --
  assert not (TIMEOUT_VAL = 0) report "[NEORV32] XBUS: NO auto-timeout configured!" severity warning;


  -- XBUS (Compatible to "pipelined" Wishbone b4 protocol) ----------------------------------
  -- -------------------------------------------------------------------------------------------
  xbus_adr_o <= bus_req.addr;
  xbus_dat_o <= bus_req.data;
  xbus_we_o  <= bus_req.rw;
  xbus_sel_o <= bus_req.ben;
  xbus_stb_o <= bus_req.stb;
  xbus_cyc_o <= bus_req.stb or pending(1);

  -- access meta data (compatible to AXI4 "xPROT") --
  xbus_tag_o(2) <= bus_req.src; -- 0 = data access, 1 = instruction fetch
  xbus_tag_o(1) <= '0'; -- always "secure" access
  xbus_tag_o(0) <= bus_req.priv or bus_req.debug; -- 0 = unprivileged access, 1 = privileged access

  -- response gating --
  bus_rsp.data <= xbus_dat_i when (pending(1) = '1') else (others => '0');
  bus_rsp.ack  <= pending(1) and xbus_ack_i;
  bus_rsp.err  <= pending(1) and (xbus_err_i or timeout);


end neorv32_xbus_rtl;
