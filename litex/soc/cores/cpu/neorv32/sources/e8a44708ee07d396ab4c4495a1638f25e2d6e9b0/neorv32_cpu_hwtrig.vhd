-- ================================================================================ --
-- NEORV32 CPU - Hardware Trigger Module (RISC-V "Sdtrig" ISA Extension)            --
-- -------------------------------------------------------------------------------- --
-- Each hardware trigger can operate either as HW breakpoint or as HW watchpoint.   --
-- [IMPORTANT] The trigger module is only usable by debug-mode software (DMODE=1).  --
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

entity neorv32_cpu_hwtrig is
  generic (
    NUM_TRIGGERS : natural range 1 to 16; -- number of implemented hardware triggers
    RISCV_ISA_U  : boolean := false       -- RISC-V user-mode available
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic; -- global clock, rising edge
    rstn_i : in  std_ulogic; -- global reset, low-active, async
    ctrl_i : in  ctrl_bus_t; -- main control bus
    -- data path --
    mar_i  : in  std_ulogic_vector(31 downto 0); -- memory address register
    csr_o  : out std_ulogic_vector(31 downto 0); -- CSR read data
    -- trigger firing --
    hit_o  : out std_ulogic -- high until debug-mode is entered
  );
end neorv32_cpu_hwtrig;

architecture neorv32_cpu_hwtrig_rtl of neorv32_cpu_hwtrig is

  -- log2(NUM_TRIGGERS) --
  constant log2_num_triggers_c : natural := index_size_f(NUM_TRIGGERS);

  -- match control CSRs: tdata1[tselect] and tdata2[tselect] --
  type tdata2_t is array (0 to NUM_TRIGGERS-1) of std_ulogic_vector(31 downto 0);
  signal tdata2 : tdata2_t;
  signal tdata1, tdata1_rb, tdata2_rb, tinfo_rb : std_ulogic_vector(31 downto 0);
  signal tdata1_exec, tdata1_store, tdata1_load, tdata1_hit : std_ulogic_vector(NUM_TRIGGERS-1 downto 0);

  -- trigger select --
  signal tselect     : std_ulogic_vector(log2_num_triggers_c downto 0); -- +1 to detect invalid selection
  signal sel         : std_ulogic_vector(NUM_TRIGGERS-1 downto 0); -- decoded one-hot trigger select
  signal sel_invalid : std_ulogic; -- invalid tselect value

  -- match logic --
  signal cmp_inst, cmp_data, match : std_ulogic_vector(NUM_TRIGGERS-1 downto 0);

  -- trigger module CSR access --
  signal csr_en : std_ulogic;

begin

  -- CSR Write Access -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_write: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tselect      <= (others => '0');
      tdata1_exec  <= (others => '0');
      tdata1_store <= (others => '0');
      tdata1_load  <= (others => '0');
      tdata2       <= (others => (others => '0'));
    elsif rising_edge(clk_i) then
      if (ctrl_i.csr_we = '1') and (csr_en = '1')  then
        -- tselect --
        if (ctrl_i.csr_addr(2 downto 0) = csr_tselect_c(2 downto 0)) then
          tselect <= ctrl_i.csr_wdata(log2_num_triggers_c downto 0);
        end if;
        -- tdata1 & tdata2 --
        for i in 0 to NUM_TRIGGERS-1 loop
          if (ctrl_i.cpu_debug = '1') then -- only accept write-accesses from debug-mode (DMODE = 1)
            if (sel(i) = '1') and (sel_invalid = '0') then
              -- match control --
              if (ctrl_i.csr_addr(2 downto 0) = csr_tdata1_c(2 downto 0)) then
                tdata1_exec(i)  <= ctrl_i.csr_wdata(2);
                tdata1_store(i) <= ctrl_i.csr_wdata(1);
                tdata1_load(i)  <= ctrl_i.csr_wdata(0);
              end if;
              -- address compare --
              if (ctrl_i.csr_addr(2 downto 0) = csr_tdata2_c(2 downto 0)) then
                tdata2(i) <= ctrl_i.csr_wdata;
              end if;
            end if;
          end if;
        end loop;
      end if;
    end if;
  end process csr_write;

  -- valid trigger module CSR access? --
  csr_en <= '1' when (ctrl_i.csr_addr(11 downto 3) = csr_tselect_c(11 downto 3)) else '0';

  -- decode selected trigger (one-hot encoding) --
  sel_gen:
  for i in 0 to NUM_TRIGGERS-1 generate
    sel(i) <= '1' when (tselect = std_ulogic_vector(to_unsigned(i, log2_num_triggers_c+1))) else '0';
  end generate;
  sel_invalid <= '1' when (unsigned(tselect) >= NUM_TRIGGERS) else '0'; -- invalid trigger selection


  -- CSR Read Access ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_read: process(csr_en, ctrl_i.csr_addr, tselect, tdata1_rb, tdata2_rb, tinfo_rb)
  begin
    csr_o <= (others => '0');
    if (csr_en = '1') then
      case ctrl_i.csr_addr(2 downto 0) is
        when "000"  => csr_o(log2_num_triggers_c downto 0) <= tselect; -- csr_tselect_c
        when "001"  => csr_o <= tdata1_rb; -- csr_tdata1_c
        when "010"  => csr_o <= tdata2_rb; -- csr_tdata2_c
        when "100"  => csr_o <= tinfo_rb; -- csr_tinfo_c
        when others => csr_o <= (others => '0');
      end case;
    end if;
  end process csr_read;

  -- match control (mcontrol6 @ tdata1 selected by tselect) read-back --
  tdata1(31 downto 28) <= x"6"; -- type: address match trigger (mcontrol6)
  tdata1(27)           <= '1'; -- dmode: ignore machine-mode write accesses
  tdata1(26)           <= '0'; -- uncertain: trigger satisfies the configured conditions
  tdata1(25)           <= tdata1(22); -- hit1: see hit0
  tdata1(24)           <= '0'; -- vs: VS-mode not implemented
  tdata1(23)           <= '0'; -- vu: VU-mode not implemented
  tdata1(22)           <= or_reduce_f(tdata1_hit and sel); -- hit0: trigger fired IMMEDIATELY AFTER condition has retired
  tdata1(21)           <= '0'; -- select: only address matching is supported
  tdata1(20 downto 19) <= "00"; -- reserved
  tdata1(18 downto 16) <= "000"; -- size: match accesses of any size
  tdata1(15 downto 12) <= x"1"; -- action = 1: enter debug mode on trigger match
  tdata1(11)           <= '0'; -- chain: chaining not supported
  tdata1(10 downto 7)  <= "0000"; -- match: equal-match only
  tdata1(6)            <= '1'; -- m: trigger always enabled when in machine-mode
  tdata1(5)            <= '0'; -- uncertainen: trigger satisfies the configured conditions
  tdata1(4)            <= '0'; -- s: supervisor-mode not supported
  tdata1(3)            <= bool_to_ulogic_f(RISCV_ISA_U); -- u: trigger always enabled when in user-mode (if implemented)
  tdata1(2)            <= or_reduce_f(tdata1_exec  and sel); -- execute: enable trigger on instruction address match
  tdata1(1)            <= or_reduce_f(tdata1_store and sel); -- store: enable trigger on store address match
  tdata1(0)            <= or_reduce_f(tdata1_load  and sel); -- load: enable trigger on load address match
  --
  tdata1_rb <= tdata1 when (sel_invalid = '0') else (others => '0'); -- all-zero if invalid trigger selection

  -- tdata2 read-back select --
  tdata2_readback: process(sel, sel_invalid, tdata2)
    variable res_v : std_ulogic_vector(31 downto 0);
  begin
    res_v := (others => '0');
    for i in 0 to NUM_TRIGGERS-1 loop
      if (sel(i) = '1') and (sel_invalid = '0') then
        res_v := res_v or tdata2(i);
      end if;
    end loop;
    tdata2_rb <= res_v;
  end process tdata2_readback;

  -- trigger info --
  tinfo_rb <= x"01000040" when (sel_invalid = '0') else x"01000001"; -- Sdtrig version 1.0, type-6 / type-0 only


  -- Trigger Logic --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- address comparators --
  cmp_gen:
  for i in 0 to NUM_TRIGGERS-1 generate
    cmp_inst(i) <= '1' when (tdata2(i) = ctrl_i.pc_cur) else '0';
    cmp_data(i) <= '1' when (tdata2(i) = mar_i) else '0';
  end generate;

  -- buffer matching triggers and filter events --
  match_buffer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      match <= (others => '0');
    elsif rising_edge(clk_i) then
      for i in 0 to NUM_TRIGGERS-1 loop
        match(i) <= (not ctrl_i.cpu_debug) and (match(i) or -- keep active until we are in debug-mode
                    (tdata1_exec(i)  and cmp_inst(i) and ctrl_i.cnt_event(cnt_event_ir_c))    or -- execute
                    (tdata1_store(i) and cmp_data(i) and ctrl_i.cnt_event(cnt_event_store_c)) or -- store
                    (tdata1_load(i)  and cmp_data(i) and ctrl_i.cnt_event(cnt_event_load_c)));   -- load
      end loop;
    end if;
  end process match_buffer;

  -- notify execution back-end if there is/was any trigger match --
  hit_o <= or_reduce_f(match);

  -- notify host that there is/was a trigger match --
  tdata1_hit_sync: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tdata1_hit <= (others => '0');
    elsif rising_edge(clk_i) then
      for i in 0 to NUM_TRIGGERS-1 loop
        if (tdata1_hit(i) = '0') then
          tdata1_hit(i) <= match(i); -- any match?
        elsif (sel(i) = '1') and (ctrl_i.csr_we = '1') and (csr_en = '1') and
              (ctrl_i.csr_addr(2 downto 0) = csr_tdata1_c(2 downto 0)) and
              (ctrl_i.csr_wdata(22) = '0') then -- clear currently selected tdata1.hit0 by debugger
          tdata1_hit(i) <= '0';
        end if;
      end loop;
    end if;
  end process tdata1_hit_sync;


end neorv32_cpu_hwtrig_rtl;
