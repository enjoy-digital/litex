-- ================================================================================ --
-- NEORV32 OCD - RISC-V-Compatible Debug Transport Module (DTM)                     --
-- -------------------------------------------------------------------------------- --
-- Compatible to RISC-V debug spec. versions 0.13 and 1.0.                          --
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

entity neorv32_debug_dtm is
  generic (
    IDCODE_VERSION : std_ulogic_vector(3 downto 0);  -- version
    IDCODE_PARTID  : std_ulogic_vector(15 downto 0); -- part number
    IDCODE_MANID   : std_ulogic_vector(10 downto 0)  -- manufacturer id
  );
  port (
    -- global control --
    clk_i      : in  std_ulogic; -- global clock line
    rstn_i     : in  std_ulogic; -- global reset line, low-active
    -- JTAG connection (TAP access) --
    jtag_tck_i : in  std_ulogic; -- serial clock
    jtag_tdi_i : in  std_ulogic; -- serial data input
    jtag_tdo_o : out std_ulogic; -- serial data output
    jtag_tms_i : in  std_ulogic; -- mode select
    -- debug module interface (DMI) --
    dmi_req_o  : out dmi_req_t;  -- request
    dmi_rsp_i  : in  dmi_rsp_t   -- response
  );
end neorv32_debug_dtm;

architecture neorv32_debug_dtm_rtl of neorv32_debug_dtm is

  -- TAP data registers --
  constant addr_idcode_c : std_ulogic_vector(4 downto 0) := "00001";
  constant addr_dtmcs_c  : std_ulogic_vector(4 downto 0) := "10000";
  constant addr_dmi_c    : std_ulogic_vector(4 downto 0) := "10001";
  constant addr_bypass_c : std_ulogic_vector(4 downto 0) := "11111";
  --
  constant size_idcode_c : natural := 32;
  constant size_dtmcs_c  : natural := 32;
  constant size_dmi_c    : natural := 7+32+2; -- 7-bit address + 32-bit data + 2-bit operation/status
  constant size_bypass_c : natural := 1;

  -- JTAG signal synchronizer --
  signal tck_ff : std_ulogic_vector(2 downto 0);
  signal tdi_ff, tms_ff : std_ulogic_vector(1 downto 0);
  signal tck_rise, tck_fall, tdi, tms : std_ulogic;

  -- TAP controller --
  type state_t is (LOGIC_RESET, DR_SCAN, DR_CAPTURE, DR_SHIFT, DR_EXIT1, DR_PAUSE, DR_EXIT2, DR_UPDATE,
                      RUN_IDLE, IR_SCAN, IR_CAPTURE, IR_SHIFT, IR_EXIT1, IR_PAUSE, IR_EXIT2, IR_UPDATE);
  signal state, state2 : state_t;

  -- TAP registers --
  signal ireg : std_ulogic_vector(4 downto 0);
  signal dreg : std_ulogic_vector(size_dmi_c-1 downto 0); -- max size (= dmi size)

  -- misc --
  signal update, dmihardreset, dmireset : std_ulogic;

  -- debug module interface controller --
  signal dmi : dmi_req_t;
  signal busy, err : std_ulogic;

begin

  -- JTAG Input Synchronizer ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tap_synchronizer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tck_ff <= (others => '0');
      tdi_ff <= (others => '0');
      tms_ff <= (others => '0');
    elsif rising_edge(clk_i) then
      tck_ff <= tck_ff(1 downto 0) & jtag_tck_i;
      tdi_ff <= tdi_ff(0) & jtag_tdi_i;
      tms_ff <= tms_ff(0) & jtag_tms_i;
    end if;
  end process tap_synchronizer;

  -- JTAG clock edges --
  tck_rise <= '1' when (tck_ff(2 downto 1) = "01") else '0';
  tck_fall <= '1' when (tck_ff(2 downto 1) = "10") else '0';

  -- JTAG inputs --
  tms <= tms_ff(1);
  tdi <= tdi_ff(1);


  -- JTAG Tap Control FSM -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tap_control: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      state2 <= LOGIC_RESET;
      state  <= LOGIC_RESET;
    elsif rising_edge(clk_i) then
      state2 <= state;
      if (tck_rise = '1') then -- clock pulse (evaluate TMS on the rising edge of TCK)
        case state is -- JTAG state machine
          when LOGIC_RESET => if (tms = '0') then state <= RUN_IDLE;   else state <= LOGIC_RESET; end if;
          when RUN_IDLE    => if (tms = '0') then state <= RUN_IDLE;   else state <= DR_SCAN;     end if;
          when DR_SCAN     => if (tms = '0') then state <= DR_CAPTURE; else state <= IR_SCAN;     end if;
          when DR_CAPTURE  => if (tms = '0') then state <= DR_SHIFT;   else state <= DR_EXIT1;    end if;
          when DR_SHIFT    => if (tms = '0') then state <= DR_SHIFT;   else state <= DR_EXIT1;    end if;
          when DR_EXIT1    => if (tms = '0') then state <= DR_PAUSE;   else state <= DR_UPDATE;   end if;
          when DR_PAUSE    => if (tms = '0') then state <= DR_PAUSE;   else state <= DR_EXIT2;    end if;
          when DR_EXIT2    => if (tms = '0') then state <= DR_SHIFT;   else state <= DR_UPDATE;   end if;
          when DR_UPDATE   => if (tms = '0') then state <= RUN_IDLE;   else state <= DR_SCAN;     end if;
          when IR_SCAN     => if (tms = '0') then state <= IR_CAPTURE; else state <= LOGIC_RESET; end if;
          when IR_CAPTURE  => if (tms = '0') then state <= IR_SHIFT;   else state <= IR_EXIT1;    end if;
          when IR_SHIFT    => if (tms = '0') then state <= IR_SHIFT;   else state <= IR_EXIT1;    end if;
          when IR_EXIT1    => if (tms = '0') then state <= IR_PAUSE;   else state <= IR_UPDATE;   end if;
          when IR_PAUSE    => if (tms = '0') then state <= IR_PAUSE;   else state <= IR_EXIT2;    end if;
          when IR_EXIT2    => if (tms = '0') then state <= IR_SHIFT;   else state <= IR_UPDATE;   end if;
          when IR_UPDATE   => if (tms = '0') then state <= RUN_IDLE;   else state <= DR_SCAN;     end if;
          when others      => state <= LOGIC_RESET;
        end case;
      end if;
    end if;
  end process tap_control;

  -- DR_UPDATE edge detector --
  update <= '1' when (state = DR_UPDATE) and (state2 /= DR_UPDATE) else '0';


  -- Tap Register Access --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  reg_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ireg       <= (others => '0');
      dreg       <= (others => '0');
      jtag_tdo_o <= '0';
    elsif rising_edge(clk_i) then
      -- instruction register input --
      if (state = LOGIC_RESET) or (state = IR_CAPTURE) then -- capture phase
        ireg <= addr_idcode_c;
      elsif (state = IR_SHIFT) and (tck_rise = '1') then -- access phase; [JTAG-SYNC] evaluate TDI on rising edge of TCK
        ireg <= tdi & ireg(ireg'left downto 1);
      end if;
      -- data register input --
      if (state = DR_CAPTURE) then -- capture phase
        dreg <= (others => '0');
        case ireg is -- make data MSB-aligned
          when addr_idcode_c => dreg(dreg'left downto dreg'left-(size_idcode_c-1)) <= IDCODE_VERSION & IDCODE_PARTID & IDCODE_MANID & '1';
          when addr_dtmcs_c  => dreg(dreg'left downto dreg'left-(size_dtmcs_c-1))  <= x"00000071";
          when addr_dmi_c    => dreg(dreg'left downto dreg'left-(size_dmi_c-1))    <= dmi.addr & dmi.data & err & err;
          when others        => dreg(dreg'left downto dreg'left-(size_bypass_c-1)) <= (others => '0');
        end case;
      elsif (state = DR_SHIFT) and (tck_rise = '1') then -- access phase; [JTAG-SYNC] evaluate TDI on rising edge of TCK
        dreg <= tdi & dreg(dreg'left downto 1);
      end if;
      -- output --
      if (tck_fall = '1') then -- [JTAG-SYNC] update TDO on falling edge of TCK
        if (state = IR_SHIFT) then
          jtag_tdo_o <= ireg(0);
        elsif (state = DR_SHIFT) then
          case ireg is -- data is MSB-aligned so select the logical LSB as output
            when addr_idcode_c => jtag_tdo_o <= dreg(dreg'left-(size_idcode_c-1));
            when addr_dtmcs_c  => jtag_tdo_o <= dreg(dreg'left-(size_dtmcs_c-1));
            when addr_dmi_c    => jtag_tdo_o <= dreg(dreg'left-(size_dmi_c-1));
            when others        => jtag_tdo_o <= dreg(dreg'left-(size_bypass_c-1));
          end case;
        end if;
      end if;
    end if;
  end process reg_access;

  -- reset control --
  dmihardreset <= '1' when (update = '1') and (ireg = addr_dtmcs_c) and (dreg(17) = '1') else '0';
  dmireset     <= '1' when (update = '1') and (ireg = addr_dtmcs_c) and (dreg(16) = '1') else '0';


  -- Debug Module Interface -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  dmi_controller: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      busy <= '0';
      err  <= '0';
      dmi  <= dmi_req_terminate_c;
    elsif rising_edge(clk_i) then
      -- sticky error: access attempt while DMI is busy --
      if (dmireset = '1') or (dmihardreset = '1') then
        err <= '0';
      elsif (update = '1') and (ireg = addr_dmi_c) and (busy = '1') then
        err <= '1';
      end if;
      -- interface arbiter --
      dmi.op <= dmi_req_nop_c; -- default
      if (busy = '0') then -- idle: waiting for new request
        if (update = '1') and (ireg = addr_dmi_c) then
          dmi.addr <= dreg(40 downto 34);
          dmi.data <= dreg(33 downto 2);
          dmi.op   <= dreg(1 downto 0);
          busy     <= or_reduce_f(dreg(1 downto 0));
        end if;
      elsif (dmi_rsp_i.ack = '1') or (dmihardreset = '1') then -- busy: wait for access termination
        dmi.data <= dmi_rsp_i.data;
        busy     <= '0';
      end if;
    end if;
  end process dmi_controller;

  -- DMI output --
  dmi_req_o <= dmi;


end neorv32_debug_dtm_rtl;
