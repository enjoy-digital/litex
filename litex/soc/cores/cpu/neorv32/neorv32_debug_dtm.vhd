-- ================================================================================ --
-- NEORV32 OCD - RISC-V-Compatible Debug Transport Module (DTM)                     --
-- -------------------------------------------------------------------------------- --
-- Compatible to RISC-V debug spec. versions 0.13 and 1.0.                          --
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
    -- jtag connection (TAP access) --
    jtag_tck_i : in  std_ulogic; -- serial clock
    jtag_tdi_i : in  std_ulogic; -- serial data input
    jtag_tdo_o : out std_ulogic; -- serial data output
    jtag_tms_i : in  std_ulogic; -- mode select
    -- debug module interface (DMI) --
    dmi_req_o  : out dmi_req_t; -- request
    dmi_rsp_i  : in  dmi_rsp_t  -- response
  );
end neorv32_debug_dtm;

architecture neorv32_debug_dtm_rtl of neorv32_debug_dtm is

  -- TAP data register addresses --
  constant addr_idcode_c : std_ulogic_vector(4 downto 0) := "00001"; -- identifier
  constant addr_dtmcs_c  : std_ulogic_vector(4 downto 0) := "10000"; -- DTM status and control
  constant addr_dmi_c    : std_ulogic_vector(4 downto 0) := "10001"; -- debug module interface

  -- tap JTAG signal synchronizer --
  type tap_sync_t is record
    tck_ff, tdi_ff, tms_ff : std_ulogic_vector(2 downto 0);
    tck_rising, tck_falling, tdi, tms : std_ulogic;
  end record;
  signal tap_sync : tap_sync_t;

  -- tap controller --
  type tap_ctrl_state_t is (LOGIC_RESET, DR_SCAN, DR_CAPTURE, DR_SHIFT, DR_EXIT1, DR_PAUSE, DR_EXIT2, DR_UPDATE,
                               RUN_IDLE, IR_SCAN, IR_CAPTURE, IR_SHIFT, IR_EXIT1, IR_PAUSE, IR_EXIT2, IR_UPDATE);
  signal tap_ctrl_state : tap_ctrl_state_t;

  -- tap registers --
  type tap_reg_t is record
    ireg             : std_ulogic_vector(4 downto 0);
    bypass           : std_ulogic;
    idcode           : std_ulogic_vector(31 downto 0);
    dtmcs, dtmcs_nxt : std_ulogic_vector(31 downto 0);
    dmi,   dmi_nxt   : std_ulogic_vector((7+32+2)-1 downto 0); -- 7-bit address + 32-bit data + 2-bit operation
  end record;
  signal tap_reg : tap_reg_t;

  -- update trigger --
  type dr_trigger_t is record
    sreg  : std_ulogic_vector(1 downto 0);
    valid : std_ulogic;
  end record;
  signal dr_trigger : dr_trigger_t;

  -- debug module interface controller --
  type dmi_ctrl_t is record
    busy         : std_ulogic;
    op           : std_ulogic_vector(1 downto 0);
    dmihardreset : std_ulogic;
    dmireset     : std_ulogic;
    err          : std_ulogic;
    rdata, wdata : std_ulogic_vector(31 downto 0);
    addr         : std_ulogic_vector(6 downto 0);
  end record;
  signal dmi_ctrl : dmi_ctrl_t;

begin

  -- JTAG Input Synchronizer ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tap_synchronizer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tap_sync.tck_ff <= (others => '0');
      tap_sync.tdi_ff <= (others => '0');
      tap_sync.tms_ff <= (others => '0');
    elsif rising_edge(clk_i) then
      tap_sync.tck_ff <= tap_sync.tck_ff(1 downto 0) & jtag_tck_i;
      tap_sync.tdi_ff <= tap_sync.tdi_ff(1 downto 0) & jtag_tdi_i;
      tap_sync.tms_ff <= tap_sync.tms_ff(1 downto 0) & jtag_tms_i;
    end if;
  end process tap_synchronizer;

  -- JTAG clock edges --
  tap_sync.tck_rising  <= '1' when (tap_sync.tck_ff(2 downto 1) = "01") else '0';
  tap_sync.tck_falling <= '1' when (tap_sync.tck_ff(2 downto 1) = "10") else '0';

  -- JTAG inputs --
  tap_sync.tms <= tap_sync.tms_ff(2);
  tap_sync.tdi <= tap_sync.tdi_ff(2);


  -- JTAG Tap Control FSM -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tap_control: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tap_ctrl_state <= LOGIC_RESET;
    elsif rising_edge(clk_i) then
      if (tap_sync.tck_rising = '1') then -- clock pulse (evaluate TMS on the rising edge of TCK)
        case tap_ctrl_state is -- JTAG state machine
          when LOGIC_RESET => if (tap_sync.tms = '0') then tap_ctrl_state <= RUN_IDLE;   else tap_ctrl_state <= LOGIC_RESET; end if;
          when RUN_IDLE    => if (tap_sync.tms = '0') then tap_ctrl_state <= RUN_IDLE;   else tap_ctrl_state <= DR_SCAN;     end if;
          when DR_SCAN     => if (tap_sync.tms = '0') then tap_ctrl_state <= DR_CAPTURE; else tap_ctrl_state <= IR_SCAN;     end if;
          when DR_CAPTURE  => if (tap_sync.tms = '0') then tap_ctrl_state <= DR_SHIFT;   else tap_ctrl_state <= DR_EXIT1;    end if;
          when DR_SHIFT    => if (tap_sync.tms = '0') then tap_ctrl_state <= DR_SHIFT;   else tap_ctrl_state <= DR_EXIT1;    end if;
          when DR_EXIT1    => if (tap_sync.tms = '0') then tap_ctrl_state <= DR_PAUSE;   else tap_ctrl_state <= DR_UPDATE;   end if;
          when DR_PAUSE    => if (tap_sync.tms = '0') then tap_ctrl_state <= DR_PAUSE;   else tap_ctrl_state <= DR_EXIT2;    end if;
          when DR_EXIT2    => if (tap_sync.tms = '0') then tap_ctrl_state <= DR_SHIFT;   else tap_ctrl_state <= DR_UPDATE;   end if;
          when DR_UPDATE   => if (tap_sync.tms = '0') then tap_ctrl_state <= RUN_IDLE;   else tap_ctrl_state <= DR_SCAN;     end if;
          when IR_SCAN     => if (tap_sync.tms = '0') then tap_ctrl_state <= IR_CAPTURE; else tap_ctrl_state <= LOGIC_RESET; end if;
          when IR_CAPTURE  => if (tap_sync.tms = '0') then tap_ctrl_state <= IR_SHIFT;   else tap_ctrl_state <= IR_EXIT1;    end if;
          when IR_SHIFT    => if (tap_sync.tms = '0') then tap_ctrl_state <= IR_SHIFT;   else tap_ctrl_state <= IR_EXIT1;    end if;
          when IR_EXIT1    => if (tap_sync.tms = '0') then tap_ctrl_state <= IR_PAUSE;   else tap_ctrl_state <= IR_UPDATE;   end if;
          when IR_PAUSE    => if (tap_sync.tms = '0') then tap_ctrl_state <= IR_PAUSE;   else tap_ctrl_state <= IR_EXIT2;    end if;
          when IR_EXIT2    => if (tap_sync.tms = '0') then tap_ctrl_state <= IR_SHIFT;   else tap_ctrl_state <= IR_UPDATE;   end if;
          when IR_UPDATE   => if (tap_sync.tms = '0') then tap_ctrl_state <= RUN_IDLE;   else tap_ctrl_state <= DR_SCAN;     end if;
          when others      => tap_ctrl_state <= LOGIC_RESET;
        end case;
      end if;
    end if;
  end process tap_control;

  -- trigger for UPDATE state --
  update_trigger: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      dr_trigger.sreg <= "00";
    elsif rising_edge(clk_i) then
      if (tap_ctrl_state = DR_UPDATE) then
        dr_trigger.sreg(0) <= '1';
      else
        dr_trigger.sreg(0) <= '0';
      end if;
      dr_trigger.sreg(1) <= dr_trigger.sreg(0);
    end if;
  end process update_trigger;

  -- edge detector --
  dr_trigger.valid <= '1' when (dr_trigger.sreg = "01") else '0';


  -- Tap Register Access --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  reg_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tap_reg.ireg   <= (others => '0');
      tap_reg.idcode <= (others => '0');
      tap_reg.dtmcs  <= (others => '0');
      tap_reg.dmi    <= (others => '0');
      tap_reg.bypass <= '0';
      jtag_tdo_o     <= '0';
    elsif rising_edge(clk_i) then

      -- serial data input: instruction register --
      if (tap_ctrl_state = LOGIC_RESET) or (tap_ctrl_state = IR_CAPTURE) then -- preload phase
        tap_reg.ireg <= addr_idcode_c;
      elsif (tap_ctrl_state = IR_SHIFT) and (tap_sync.tck_rising = '1') then -- access phase; [JTAG-SYNC] evaluate TDI on rising edge of TCK
        tap_reg.ireg <= tap_sync.tdi & tap_reg.ireg(tap_reg.ireg'left downto 1);
      end if;

      -- serial data input: data register --
      if (tap_ctrl_state = DR_CAPTURE) then -- preload phase
        case tap_reg.ireg is
          when addr_idcode_c => tap_reg.idcode <= IDCODE_VERSION & IDCODE_PARTID & IDCODE_MANID & '1'; -- identifier (LSB has to be set)
          when addr_dtmcs_c  => tap_reg.dtmcs  <= tap_reg.dtmcs_nxt; -- status register
          when addr_dmi_c    => tap_reg.dmi    <= tap_reg.dmi_nxt; -- register interface
          when others        => tap_reg.bypass <= '0'; -- pass through
        end case;
      elsif (tap_ctrl_state = DR_SHIFT) and (tap_sync.tck_rising = '1') then -- access phase; [JTAG-SYNC] evaluate TDI on rising edge of TCK
        case tap_reg.ireg is
          when addr_idcode_c => tap_reg.idcode <= tap_sync.tdi & tap_reg.idcode(tap_reg.idcode'left downto 1);
          when addr_dtmcs_c  => tap_reg.dtmcs  <= tap_sync.tdi & tap_reg.dtmcs(tap_reg.dtmcs'left downto 1);
          when addr_dmi_c    => tap_reg.dmi    <= tap_sync.tdi & tap_reg.dmi(tap_reg.dmi'left downto 1);
          when others        => tap_reg.bypass <= tap_sync.tdi;
        end case;
      end if;

      -- serial data output --
      if (tap_sync.tck_falling = '1') then -- [JTAG-SYNC] update TDO on falling edge of TCK
        if (tap_ctrl_state = IR_SHIFT) then
          jtag_tdo_o <= tap_reg.ireg(0);
        else
          case tap_reg.ireg is
            when addr_idcode_c => jtag_tdo_o <= tap_reg.idcode(0);
            when addr_dtmcs_c  => jtag_tdo_o <= tap_reg.dtmcs(0);
            when addr_dmi_c    => jtag_tdo_o <= tap_reg.dmi(0);
            when others        => jtag_tdo_o <= tap_reg.bypass;
          end case;
        end if;
      end if;

    end if;
  end process reg_access;

  -- DTM control and status register (dtmcs) read-back --
  tap_reg.dtmcs_nxt(31 downto 18) <= (others => '0'); -- reserved
  tap_reg.dtmcs_nxt(17)           <= dmi_ctrl.dmihardreset; -- dmihardreset
  tap_reg.dtmcs_nxt(16)           <= dmi_ctrl.dmireset; -- dmireset
  tap_reg.dtmcs_nxt(15)           <= '0'; -- reserved
  tap_reg.dtmcs_nxt(14 downto 12) <= "000"; -- minimum number of idle cycles (= 0)
  tap_reg.dtmcs_nxt(11 downto 10) <= tap_reg.dmi_nxt(1 downto 0); -- dmistat
  tap_reg.dtmcs_nxt(09 downto 04) <= "000111"; -- number of DMI address bits (7)
  tap_reg.dtmcs_nxt(03 downto 00) <= "0001"; -- compatible to debug spec. version (0.13 & 1.0)

  -- DMI register (dmi) read-back --
  tap_reg.dmi_nxt <= dmi_ctrl.addr & dmi_ctrl.rdata & replicate_f(dmi_ctrl.err, 2); -- address & read data & status


  -- Debug Module Interface -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  dmi_controller: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      dmi_ctrl.busy         <= '0';
      dmi_ctrl.op           <= "00";
      dmi_ctrl.dmihardreset <= '1';
      dmi_ctrl.dmireset     <= '0';
      dmi_ctrl.err          <= '0';
      dmi_ctrl.rdata        <= (others => '0');
      dmi_ctrl.wdata        <= (others => '0');
      dmi_ctrl.addr         <= (others => '0');
    elsif rising_edge(clk_i) then
      -- DMI reset control --
      if (dr_trigger.valid = '1') and (tap_reg.ireg = addr_dtmcs_c) then
        dmi_ctrl.dmireset     <= tap_reg.dtmcs(16);
        dmi_ctrl.dmihardreset <= tap_reg.dtmcs(17);
      elsif (dmi_ctrl.busy = '0') then
        dmi_ctrl.dmihardreset <= '0';
        dmi_ctrl.dmireset     <= '0';
      end if;

      -- sticky error --
      if (dmi_ctrl.dmireset = '1') or (dmi_ctrl.dmihardreset = '1') then
        dmi_ctrl.err <= '0';
      elsif (dmi_ctrl.busy = '1') and (dr_trigger.valid = '1') and (tap_reg.ireg = addr_dmi_c) then -- access attempt while DMI is busy
        dmi_ctrl.err <= '1';
      end if;

      -- DMI interface arbiter --
      dmi_ctrl.op <= dmi_req_nop_c; -- default
      if (dmi_ctrl.busy = '0') then -- idle: waiting for new request
        if (dmi_ctrl.dmihardreset = '0') and (dr_trigger.valid = '1') and (tap_reg.ireg = addr_dmi_c) then -- valid non-reset access
          dmi_ctrl.addr  <= tap_reg.dmi(40 downto 34);
          dmi_ctrl.wdata <= tap_reg.dmi(33 downto 02);
          if (tap_reg.dmi(1 downto 0) = dmi_req_rd_c) or (tap_reg.dmi(1 downto 0) = dmi_req_wr_c) then
            dmi_ctrl.op   <= tap_reg.dmi(1 downto 0);
            dmi_ctrl.busy <= '1';
          end if;
        end if;
      else -- busy: read/write access in progress
        dmi_ctrl.rdata <= dmi_rsp_i.data;
        if (dmi_rsp_i.ack = '1') then
          dmi_ctrl.busy <= '0';
        end if;
      end if;
    end if;
  end process dmi_controller;

  -- direct DMI output --
  dmi_req_o.op   <= dmi_ctrl.op;
  dmi_req_o.data <= dmi_ctrl.wdata;
  dmi_req_o.addr <= dmi_ctrl.addr;


end neorv32_debug_dtm_rtl;
