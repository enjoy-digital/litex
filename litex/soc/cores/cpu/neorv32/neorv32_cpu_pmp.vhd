-- ================================================================================ --
-- NEORV32 CPU - Physical Memory Protection Unit (RISC-V "Smpmp" Extension)         --
-- -------------------------------------------------------------------------------- --
-- Compatible to the RISC-V privilege architecture PMP specifications. Granularity  --
-- and supported modes can be constrained via generics to reduce area requirements  --
-- and to relax timing.                                                             --
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

entity neorv32_cpu_pmp is
  generic (
    NUM_REGIONS : natural range 0 to 16; -- number of regions (0..16)
    GRANULARITY : natural; -- minimal region granularity in bytes, has to be a power of 2, min 4 bytes
    TOR_EN      : boolean; -- implement TOR mode
    NAP_EN      : boolean  -- implement NAPOT/NA4 modes
  );
  port (
    -- global control --
    clk_i    : in  std_ulogic; -- global clock, rising edge
    rstn_i   : in  std_ulogic; -- global reset, low-active, async
    ctrl_i   : in  ctrl_bus_t; -- main control bus
    csr_o    : out std_ulogic_vector(31 downto 0); -- CSR read data
    -- instruction access check --
    i_addr_i : in  std_ulogic_vector(31 downto 0); -- access address
    i_priv_i : in  std_ulogic; -- access privilege
    i_err_o  : out std_ulogic; -- PMP fault
    -- data access check --
    d_addr_i : in  std_ulogic_vector(31 downto 0); -- access address
    d_priv_i : in  std_ulogic; -- access privilege
    d_err_o  : out std_ulogic  -- PMP fault
  );
end neorv32_cpu_pmp;

architecture neorv32_cpu_pmp_rtl of neorv32_cpu_pmp is

  -- auto-configuration --
  constant g_c : natural := cond_sel_natural_f(boolean(GRANULARITY < 4), 4, 2**index_size_f(GRANULARITY));

  -- configuration register bits --
  constant cfg_r_c  : natural := 0; -- read permission
  constant cfg_w_c  : natural := 1; -- write permission
  constant cfg_x_c  : natural := 2; -- execute permission
  constant cfg_al_c : natural := 3; -- mode bit low
  constant cfg_ah_c : natural := 4; -- mode bit high
  constant cfg_l_c  : natural := 7; -- locked

  -- operation modes --
  constant mode_off_c   : std_ulogic_vector(1 downto 0) := "00"; -- null region (disabled)
  constant mode_tor_c   : std_ulogic_vector(1 downto 0) := "01"; -- top of range
  constant mode_na4_c   : std_ulogic_vector(1 downto 0) := "10"; -- naturally aligned four-byte region
  constant mode_napot_c : std_ulogic_vector(1 downto 0) := "11"; -- naturally aligned power-of-two region (> 4 bytes)

  -- address LSB according to granularity --
  constant pmp_lsb_c : natural := index_size_f(g_c); -- min = 2

  -- configuration CSRs --
  type pmpcfg_t is array (0 to NUM_REGIONS-1) of std_ulogic_vector(7 downto 0);
  signal pmpcfg    : pmpcfg_t;
  signal pmpcfg_we : std_ulogic_vector(3 downto 0);

  -- address CSRs --
  type pmpaddr_t is array (0 to NUM_REGIONS-1) of std_ulogic_vector(31 downto 0);
  signal pmpaddr    : pmpaddr_t;
  signal pmpaddr_we : std_ulogic_vector(15 downto 0);

  -- CSR read-back --
  type csr_cfg_rd_t   is array (0 to 15) of std_ulogic_vector(7 downto 0);
  type csr_cfg_rd32_t is array (0 to 03) of std_ulogic_vector(31 downto 0);
  type csr_addr_rd_t  is array (0 to 15) of std_ulogic_vector(31 downto 0);
  signal cfg_rd   : csr_cfg_rd_t;
  signal cfg_rd32 : csr_cfg_rd32_t;
  signal addr_rd  : csr_addr_rd_t;

  -- address mask (NA4/NAPOT) --
  type addr_mask_t is array (0 to NUM_REGIONS-1) of std_ulogic_vector(31 downto pmp_lsb_c);
  signal addr_mask_napot, addr_mask : addr_mask_t;

  -- address comparators, region-match and permission check --
  type cmp_t is array (0 to NUM_REGIONS-1) of std_ulogic_vector(1 downto 0); -- 0 = instruction fetch, 1 = data access
  signal cmp_na, cmp_ge, cmp_lt, match : cmp_t;

  -- permission check --
  signal allow_ex, allow_rw : std_ulogic_vector(NUM_REGIONS-1 downto 0);

  -- access check prioritizing logic --
  signal fail_ex, fail_rw : std_ulogic_vector(NUM_REGIONS downto 0);

begin

  -- Configuration Checks -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  assert (GRANULARITY = g_c) report
    "[NEORV32] Auto-adjusting invalid PMP granularity configuration." severity warning;


  -- CSR Write Access: Configuration (PMPCFG) -----------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_we_cfg: process(ctrl_i) -- write enable decoder
  begin
    pmpcfg_we <= (others => '0');
    if (ctrl_i.csr_addr(11 downto 2) = csr_pmpcfg0_c(11 downto 2)) and (ctrl_i.csr_we = '1') then
      pmpcfg_we(to_integer(unsigned(ctrl_i.csr_addr(1 downto 0)))) <= '1';
    end if;
  end process csr_we_cfg;

  -- CSRs --
  csr_pmpcfg_gen:
  for i in 0 to NUM_REGIONS-1 generate
    csr_pmpcfg: process(rstn_i, clk_i)
      variable mode_v : std_ulogic_vector(1 downto 0);
    begin
      if (rstn_i = '0') then
        pmpcfg(i) <= (others => '0');
      elsif rising_edge(clk_i) then
        if (pmpcfg_we(i/4) = '1') and (pmpcfg(i)(cfg_l_c) = '0') then -- unlocked write access
          -- permissions --
          pmpcfg(i)(cfg_r_c) <= ctrl_i.csr_wdata((i mod 4)*8+cfg_r_c); -- R (read)
          pmpcfg(i)(cfg_w_c) <= ctrl_i.csr_wdata((i mod 4)*8+cfg_w_c); -- W (write)
          pmpcfg(i)(cfg_x_c) <= ctrl_i.csr_wdata((i mod 4)*8+cfg_x_c); -- X (execute)
          -- mode --
          mode_v := ctrl_i.csr_wdata((i mod 4)*8+cfg_ah_c downto (i mod 4)*8+cfg_al_c);
          if ((mode_v = mode_tor_c)   and (not TOR_EN)) or -- TOR mode not implemented
             ((mode_v = mode_na4_c)   and (not NAP_EN)) or -- NA4 mode not implemented
             ((mode_v = mode_napot_c) and (not NAP_EN)) or -- NAPOT mode not implemented
             ((mode_v = mode_na4_c)   and (g_c > 4)) then  -- NA4 not available
            pmpcfg(i)(cfg_ah_c downto cfg_al_c) <= mode_off_c;
          else -- valid configuration
            pmpcfg(i)(cfg_ah_c downto cfg_al_c) <= mode_v;
          end if;
          -- reserved --
          pmpcfg(i)(6 downto 5) <= (others => '0');
          -- locked --
          pmpcfg(i)(cfg_l_c)  <= ctrl_i.csr_wdata((i mod 4)*8+cfg_l_c);
        end if;
      end if;
    end process csr_pmpcfg;
  end generate;


  -- CSR Write Access: Address (PMPADDR) ----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_we_addr: process(ctrl_i) -- write enable decoder
  begin
    pmpaddr_we <= (others => '0');
    if (ctrl_i.csr_addr(11 downto 4) = csr_pmpaddr0_c(11 downto 4)) and (ctrl_i.csr_we = '1') then
      pmpaddr_we(to_integer(unsigned(ctrl_i.csr_addr(3 downto 0)))) <= '1';
    end if;
  end process csr_we_addr;

  -- CSRs --
  csr_pmpaddr_gen:
  for i in 0 to NUM_REGIONS-1 generate
    csr_pmpaddr: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        pmpaddr(i) <= (others => '0');
      elsif rising_edge(clk_i) then
        if (pmpaddr_we(i) = '1') and (pmpcfg(i)(cfg_l_c) = '0') then -- unlocked write access
          if (i < NUM_REGIONS-1) then
            if (pmpcfg(i+1)(cfg_l_c) = '0') or (pmpcfg(i+1)(cfg_ah_c downto cfg_al_c) /= mode_tor_c) then -- pmpcfg(i+1) not "LOCKED TOR"
              pmpaddr(i) <= "00" & ctrl_i.csr_wdata(29 downto 0);
            end if;
          else -- very last entry
            pmpaddr(i) <= "00" & ctrl_i.csr_wdata(29 downto 0);
          end if;
        end if;
      end if;
    end process csr_pmpaddr;
  end generate;


  -- CSR Read Access ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_read_access: process(ctrl_i.csr_addr, cfg_rd32, addr_rd)
  begin
    if (ctrl_i.csr_addr(11 downto 5) = csr_pmpcfg0_c(11 downto 5)) then -- PMP CSR
      if (ctrl_i.csr_addr(4) = '0') then -- PMP configuration CSR
        csr_o <= cfg_rd32(to_integer(unsigned(ctrl_i.csr_addr(1 downto 0))));
      else -- PMP address CSR
        csr_o <= addr_rd(to_integer(unsigned(ctrl_i.csr_addr(3 downto 0))));
      end if;
    else
      csr_o <= (others => '0');
    end if;
  end process csr_read_access;

  -- CSR read-back --
  csr_read_back_gen:
  for i in 0 to NUM_REGIONS-1 generate
    -- configuration --
    cfg_rd(i) <= pmpcfg(i);
    -- address --
    address_read_back: process(pmpaddr, pmpcfg)
    begin
      addr_rd(i) <= (others => '0');
      addr_rd(i)(29 downto pmp_lsb_c-2) <= pmpaddr(i)(29 downto pmp_lsb_c-2);
      if (g_c = 8) and TOR_EN then -- bit G-1 reads as zero in TOR or OFF mode
        if (pmpcfg(i)(cfg_ah_c) = '0') then -- TOR/OFF mode
          addr_rd(i)(pmp_lsb_c) <= '0';
        end if;
      elsif (g_c > 8) then
        if NAP_EN then
          addr_rd(i)(pmp_lsb_c-2 downto 0) <= (others => '1'); -- in NAPOT mode bits G-2:0 must read as one
        end if;
        if TOR_EN then
          if (pmpcfg(i)(cfg_ah_c) = '0') then -- TOR/OFF mode
            addr_rd(i)(pmp_lsb_c-1 downto 0) <= (others => '0'); -- in TOR or OFF mode bits G-1:0 must read as zero
          end if;
        end if;
      end if;
    end process address_read_back;
  end generate;

  -- terminate unused CSR read-backs --
  csr_read_back_terminate:
  for i in NUM_REGIONS to 15 generate
    cfg_rd(i)  <= (others => '0');
    addr_rd(i) <= (others => '0');
  end generate;

  -- pack configuration read-back --
  csr_read_back_pack:
  for i in 0 to 3 generate
    cfg_rd32(i) <= cfg_rd(i*4+3) & cfg_rd(i*4+2) & cfg_rd(i*4+1) & cfg_rd(i*4+0);
  end generate;


  -- Region Address Mask for NA-Modes -------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  mask_gen:
  for r in 0 to NUM_REGIONS-1 generate

    -- NAPOT address mask generator --
    addr_mask_napot(r)(pmp_lsb_c) <= '0';
    addr_mask_napot_gen:
    for i in pmp_lsb_c+1 to 31 generate
      addr_mask_napot(r)(i) <= addr_mask_napot(r)(i-1) or (not pmpaddr(r)(i-3));
    end generate;

    -- NAPOT address mask select --
    addr_masking: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        addr_mask(r) <= (others => '0');
      elsif rising_edge(clk_i) then
        if NAP_EN then
          if (pmpcfg(r)(cfg_al_c) = '1') then -- NAPOT
            addr_mask(r) <= addr_mask_napot(r);
          else -- NA4
            addr_mask(r) <= (others => '1');
          end if;
        else
          addr_mask(r) <= (others => '0');
        end if;
      end if;
    end process addr_masking;

  end generate;


  -- Region Access Check --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  region_gen:
  for r in 0 to NUM_REGIONS-1 generate

    -- check region address match --
    -- NA4 and NAPOT --
    cmp_na(r)(0) <= '1' when ((i_addr_i(31 downto pmp_lsb_c) and addr_mask(r)) = (pmpaddr(r)(29 downto pmp_lsb_c-2) and addr_mask(r))) and NAP_EN else '0';
    cmp_na(r)(1) <= '1' when ((d_addr_i(31 downto pmp_lsb_c) and addr_mask(r)) = (pmpaddr(r)(29 downto pmp_lsb_c-2) and addr_mask(r))) and NAP_EN else '0';
    -- TOR region 0 --
    addr_match_r0_gen:
    if (r = 0) generate -- first entry: use ZERO as base and current entry as bound
      cmp_ge(r) <= (others => '1'); -- address is always greater than or equal to zero
      cmp_lt(r) <= (others => '0'); -- cannot be less then zero
    end generate;
    -- TOR region above 0 --
    addr_match_rn_gen:
    if (r > 0) generate -- use previous entry as base and current entry as bound
      cmp_ge(r)(0) <= '1' when (unsigned(i_addr_i(31 downto pmp_lsb_c)) >= unsigned(pmpaddr(r-1)(29 downto pmp_lsb_c-2))) and TOR_EN else '0';
      cmp_lt(r)(0) <= '1' when (unsigned(i_addr_i(31 downto pmp_lsb_c)) <  unsigned(pmpaddr(r  )(29 downto pmp_lsb_c-2))) and TOR_EN else '0';
      cmp_ge(r)(1) <= '1' when (unsigned(d_addr_i(31 downto pmp_lsb_c)) >= unsigned(pmpaddr(r-1)(29 downto pmp_lsb_c-2))) and TOR_EN else '0';
      cmp_lt(r)(1) <= '1' when (unsigned(d_addr_i(31 downto pmp_lsb_c)) <  unsigned(pmpaddr(r  )(29 downto pmp_lsb_c-2))) and TOR_EN else '0';
    end generate;

    -- check region match according to configured mode --
    match_gen: process(pmpcfg, cmp_ge, cmp_lt, cmp_na)
    begin
      if (pmpcfg(r)(cfg_ah_c downto cfg_al_c) = mode_tor_c) and TOR_EN then -- TOR
        if (r = (NUM_REGIONS-1)) then -- very last region
          match(r) <= cmp_ge(r) and cmp_lt(r);
        else -- any other region
          match(r) <= cmp_ge(r) and (not cmp_ge(r+1)); -- this saves a LOT of comparators
        end if;
      elsif (pmpcfg(r)(cfg_ah_c) = mode_napot_c(1)) and NAP_EN then -- NA4/NAPOT
        match(r) <= cmp_na(r);
      else -- OFF or mode not supported
        match(r) <= (others => '0');
      end if;
    end process match_gen;

  end generate;


  -- Permission Check -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  perm_gen:
  for r in NUM_REGIONS-1 downto 0 generate -- start with lowest priority
    -- execute (X), check privilege and permission --
    allow_ex(r) <= '1' when (i_priv_i = priv_mode_m_c) and (pmpcfg(r)(cfg_l_c) = '0') else -- grant if M and not locked
                   pmpcfg(r)(cfg_x_c);
    -- read/write (RW), check privilege and permission(s) according to access type --
    allow_rw(r) <= '1' when (d_priv_i = priv_mode_m_c) and (pmpcfg(r)(cfg_l_c) = '0')    else -- grant if M and not locked
                   pmpcfg(r)(cfg_r_c) and pmpcfg(r)(cfg_w_c) when (ctrl_i.lsu_rmw = '1') else -- read-modify-write access
                   pmpcfg(r)(cfg_r_c)                        when (ctrl_i.lsu_rw = '0')  else -- read access
                   pmpcfg(r)(cfg_w_c);                                                        -- write access
  end generate;

  -- very last entry: start of chain (fail if not M-mode) --
  fail_ex(NUM_REGIONS) <= '1' when (i_priv_i /= priv_mode_m_c) else '0';
  fail_rw(NUM_REGIONS) <= '1' when (d_priv_i /= priv_mode_m_c) else '0';
  -- prioritization logic implemented as a multiplexer chain --
  prio_gen:
  for r in NUM_REGIONS-1 downto 0 generate -- start with lowest priority
    fail_ex(r) <= not allow_ex(r) when (match(r)(0) = '1') else fail_ex(r+1);
    fail_rw(r) <= not allow_rw(r) when (match(r)(1) = '1') else fail_rw(r+1);
  end generate;

  -- output buffer (ignore PMP rules when in debug-mode) --
  fault_check: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      i_err_o <= '0';
      d_err_o <= '0';
    elsif rising_edge(clk_i) then
      i_err_o <= (not ctrl_i.cpu_debug) and fail_ex(0);
      d_err_o <= (not ctrl_i.cpu_debug) and fail_rw(0);
    end if;
  end process fault_check;


end neorv32_cpu_pmp_rtl;
