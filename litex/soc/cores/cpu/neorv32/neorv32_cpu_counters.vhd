-- ================================================================================ --
-- NEORV32 CPU - Hardware Counters                                                  --
-- -------------------------------------------------------------------------------- --
-- Implementing hardware counters for the following RISC-V ISA extensions:          --
-- + Zicntr: Base Counters -> [m]cycle[h] + [m]time[h] + [m]instret[h] CSRs         --
-- + Zihpm:  Hardware Performance Monitors -> [m]hpmcntx[h] + mhpmeventx CRSs       --
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

entity neorv32_cpu_counters is
  generic (
    ZICNTR_EN : boolean; -- implement base counters
    ZIHPM_EN  : boolean; -- implement hardware performance monitors
    HPM_NUM   : natural range 0 to 13; -- number of implemented HPM counters (0..13)
    HPM_WIDTH : natural range 0 to 64  -- total size of HPM counters (0..64)
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    ctrl_i  : in  ctrl_bus_t; -- main control bus
    -- read back --
    rdata_o : out std_ulogic_vector(XLEN-1 downto 0) -- read data
  );
end neorv32_cpu_counters;

architecture neorv32_cpu_counters_rtl of neorv32_cpu_counters is

  -- generic counter module --
  component neorv32_cpu_counters_cnt
  generic (
    CNT_WIDTH : natural range 0 to 64 -- counter width (0..64)
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    inc_i   : in  std_ulogic; -- enable counter increment
    -- read/write access --
    sel_i   : in  std_ulogic; -- high word / low word select
    we_i    : in  std_ulogic; -- write enable
    re_i    : in  std_ulogic; -- read enable
    wdata_i : in  std_ulogic_vector(XLEN-1 downto 0); -- write data
    rdata_o : out std_ulogic_vector(XLEN-1 downto 0) -- read data
  );
  end component;

  -- global access decoder --
  signal cnt_acc, cfg_acc : std_ulogic;
  signal sel, cnt_we, cnt_re, cfg_we, cfg_re : std_ulogic_vector(15 downto 0);

  -- counter increment control --
  signal cnt_en : std_ulogic_vector(15 downto 0);

  -- individual HPM read-backs --
  type hpmevent_t is array (3 to 15) of std_ulogic_vector(11 downto 0);
  type hpmcnt_t   is array (3 to 15) of std_ulogic_vector(XLEN-1 downto 0);
  signal hpmevent : hpmevent_t;
  signal hpmcnt   : hpmcnt_t;

  -- global read-backs --
  signal cycle_rd, time_rd, instret_rd, hpm_rd : std_ulogic_vector(XLEN-1 downto 0);

begin

  -- Access Decoder -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  acc_gen:
  for i in 0 to 15 generate
    sel(i)    <= '1' when (ctrl_i.csr_addr(3 downto 0) = std_ulogic_vector(to_unsigned(i, 4))) else '0';
    cnt_we(i) <= cnt_acc and sel(i) and ctrl_i.csr_we;
    cnt_re(i) <= cnt_acc and sel(i) and ctrl_i.csr_re;
    cfg_we(i) <= cfg_acc and sel(i) and ctrl_i.csr_we;
    cfg_re(i) <= cfg_acc and sel(i) and ctrl_i.csr_re;
  end generate;

  -- global access --
  cnt_acc <= '1' when ZICNTR_EN and ((ctrl_i.csr_addr(11 downto 5) = csr_cycle_c(11 downto 5)) or
                                     (ctrl_i.csr_addr(11 downto 5) = csr_mcycle_c(11 downto 5)) or
                                     (ctrl_i.csr_addr(11 downto 5) = csr_cycleh_c(11 downto 5)) or
                                     (ctrl_i.csr_addr(11 downto 5) = csr_mcycleh_c(11 downto 5))) else '0';
  cfg_acc <= '1' when ZIHPM_EN and (ctrl_i.csr_addr(11 downto 5) = csr_mhpmevent3_c(11 downto 5)) else '0';

  -- global data read-back --
  rdata_o <= cycle_rd or time_rd or instret_rd or hpm_rd;


  -- Counter Increment Control --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cnt_control: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      cnt_en <= (others => '0');
    elsif rising_edge(clk_i) then
      -- increment if an (enabled) event fires; do not increment if CPU is in debug mode or if counter is inhibited
      cnt_en(0) <= ctrl_i.cnt_event(cnt_event_cy_c) and (not ctrl_i.cpu_debug) and (not ctrl_i.cnt_halt(0));
      cnt_en(1) <= '0'; -- time: not available
      cnt_en(2) <= ctrl_i.cnt_event(cnt_event_ir_c) and (not ctrl_i.cpu_debug) and (not ctrl_i.cnt_halt(2));
      for i in 3 to 15 loop
        cnt_en(i) <= or_reduce_f(ctrl_i.cnt_event and hpmevent(i)) and (not ctrl_i.cpu_debug) and (not ctrl_i.cnt_halt(i));
      end loop;
    end if;
  end process cnt_control;


  -- Base Counters (Zicntr) -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  base_enabled:
  if ZICNTR_EN generate

    -- [m]cycle[h] CSR --
    cycle_inst: neorv32_cpu_counters_cnt
    generic map (
      CNT_WIDTH => 2*XLEN
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      inc_i   => cnt_en(0),
      sel_i   => ctrl_i.csr_addr(7),
      we_i    => cnt_we(0),
      re_i    => cnt_re(0),
      wdata_i => ctrl_i.csr_wdata,
      rdata_o => cycle_rd
    );

    -- time[h] CSR --
    time_rd <= (others => '0'); -- not implemented

    -- [m]instret[h] CSR --
    instret_inst: neorv32_cpu_counters_cnt
    generic map (
      CNT_WIDTH => 2*XLEN
    )
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      inc_i   => cnt_en(2),
      sel_i   => ctrl_i.csr_addr(7),
      we_i    => cnt_we(2),
      re_i    => cnt_re(2),
      wdata_i => ctrl_i.csr_wdata,
      rdata_o => instret_rd
    );

  end generate; -- /base_enabled


  base_disabled:
  if not ZICNTR_EN generate
    cycle_rd   <= (others => '0');
    time_rd    <= (others => '0');
    instret_rd <= (others => '0');
  end generate; -- /base__disabled


  -- Hardware Performance Monitors (Zihpm) --------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  hpm_enabled:
  if ZIHPM_EN and (HPM_NUM > 0) generate

    hpm_gen:
    for i in 3 to (HPM_NUM+3)-1 generate

       -- [m]hpmcntx[h] CSRs --
      hpmcnt_inst: neorv32_cpu_counters_cnt
      generic map (
        CNT_WIDTH => HPM_WIDTH
      )
      port map (
        clk_i   => clk_i,
        rstn_i  => rstn_i,
        inc_i   => cnt_en(i),
        sel_i   => ctrl_i.csr_addr(7),
        we_i    => cnt_we(i),
        re_i    => cnt_re(i),
        wdata_i => ctrl_i.csr_wdata,
        rdata_o => hpmcnt(i)
      );

      -- mhpmeventx CSRs --
      hpmevent_reg: process(rstn_i, clk_i)
      begin
        if (rstn_i = '0') then
          hpmevent(i) <= (others => '0');
        elsif rising_edge(clk_i) then
          if (cfg_we(i) = '1') then
            hpmevent(i) <= ctrl_i.csr_wdata(11 downto 0);
          end if;
          hpmevent(i)(cnt_event_tm_c) <= '0'; -- time: not available
        end if;
      end process hpmevent_reg;

    end generate; -- /hpm_gen

    -- terminate unused entries --
    hpm_terminate_gen:
    for i in HPM_NUM+3 to 15 generate
      hpmcnt(i)   <= (others => '0');
      hpmevent(i) <= (others => '0');
    end generate; -- /hpm_terminate_gen

    -- read-back --
    hpm_read_back: process(hpmcnt, cfg_re, hpmevent)
      variable cnt_v, cfg_v : std_ulogic_vector(XLEN-1 downto 0);
    begin
      cnt_v := (others => '0');
      cfg_v := (others => '0');
      for i in 3 to 15 loop
        cnt_v := cnt_v or hpmcnt(i);
        if (cfg_re(i) = '1') then -- gating
          cfg_v := cfg_v or std_ulogic_vector(resize(unsigned(hpmevent(i)), XLEN));
        end if;
      end loop;
      hpm_rd <= cnt_v or cfg_v;
    end process hpm_read_back;

  end generate; -- /hpm_enabled


  hpm_disabled:
  if (not ZIHPM_EN) or (HPM_NUM = 0) generate
    hpmcnt   <= (others => (others => '0'));
    hpmevent <= (others => (others => '0'));
    hpm_rd   <= (others => '0');
  end generate; -- /hpm_disabled

end neorv32_cpu_counters_rtl;


-- ================================================================================ --
-- NEORV32 CPU - Generic Counter Module                                             --
-- -------------------------------------------------------------------------------- --
-- If the counter is wider than 32 bit it is split into two sub-word registers in   --
-- order to shorten the carry chain length by inserting a flip flop stage.          --
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

entity neorv32_cpu_counters_cnt is
  generic (
    CNT_WIDTH : natural range 0 to 64 -- counter width (0..64)
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- global clock, rising edge
    rstn_i  : in  std_ulogic; -- global reset, low-active, async
    inc_i   : in  std_ulogic; -- enable counter increment
    -- read/write access --
    sel_i   : in  std_ulogic; -- high word / low word select
    we_i    : in  std_ulogic; -- write enable
    re_i    : in  std_ulogic; -- read enable
    wdata_i : in  std_ulogic_vector(XLEN-1 downto 0); -- write data
    rdata_o : out std_ulogic_vector(XLEN-1 downto 0) -- read data
  );
end neorv32_cpu_counters_cnt;

architecture neorv32_cpu_counters_cnt_rtl of neorv32_cpu_counters_cnt is

  -- sub-word size configuration --
  constant lo_width_c : natural := min_natural_f(CNT_WIDTH, 32); -- size low word
  constant hi_width_c : natural := CNT_WIDTH - lo_width_c; -- size high word

  -- core --
  signal lo_q : std_ulogic_vector(lo_width_c-1 downto 0);
  signal hi_q : std_ulogic_vector(hi_width_c-1 downto 0);
  signal cy_q : std_ulogic_vector(0 downto 0);
  signal nxt  : std_ulogic_vector(lo_width_c downto 0);
  signal inc  : std_ulogic_vector(0 downto 0);

begin

  -- counter low-word --
  low_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      lo_q <= (others => '0');
    elsif rising_edge(clk_i) then
      if (we_i = '1') and (sel_i = '0') then
        lo_q <= wdata_i(lo_width_c-1 downto 0);
      else
        lo_q <= nxt(lo_width_c-1 downto 0);
      end if;
    end if;
  end process low_reg;

  -- low-word increment --
  inc <= (others => inc_i);
  nxt <= std_ulogic_vector(unsigned('0' & lo_q) + unsigned(inc));


  -- counter high-word --
  high_word_enabled:
  if (CNT_WIDTH > 32) generate
    high_reg: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        cy_q <= (others => '0');
        hi_q <= (others => '0');
      elsif rising_edge(clk_i) then
        cy_q <= (others => nxt(lo_width_c)); -- low-word to high-word carry
        if (we_i = '1') and (sel_i = '1') then
          hi_q <= wdata_i(hi_width_c-1 downto 0);
        else
          hi_q <= std_ulogic_vector(unsigned(hi_q) + unsigned(cy_q));
        end if;
      end if;
    end process high_reg;
  end generate;

  high_word_disabled:
  if (CNT_WIDTH <= 32) generate
    cy_q <= (others => '0');
    hi_q <= (others => '0');
  end generate;


  -- output selected sub-word --
  output_select: process(re_i, sel_i, lo_q, hi_q)
  begin
    rdata_o <= (others => '0');
    if (re_i = '1') and (CNT_WIDTH > 0) then
      if (sel_i = '0') or (CNT_WIDTH <= 32) then
        rdata_o <= std_ulogic_vector(resize(unsigned(lo_q), XLEN));
      else
        rdata_o <= std_ulogic_vector(resize(unsigned(hi_q), XLEN));
      end if;
    end if;
  end process output_select;

end neorv32_cpu_counters_cnt_rtl;

