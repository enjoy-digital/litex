-- ================================================================================ --
-- NEORV32 SoC - RISC-V Core Local Interruptor (CLINT)                              --
-- -------------------------------------------------------------------------------- --
-- Compatible to the RISC-V & SiFive CLINT specification. Supports machine software --
-- interrupts and machine timer interrupts for up to 4095 harts.                    --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2024 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_clint is
  generic (
    NUM_HARTS : natural range 1 to 4095 -- number of physical CPU cores
  );
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- global reset line, low-active, async
    bus_req_i : in  bus_req_t; -- bus request
    bus_rsp_o : out bus_rsp_t; -- bus response
    time_o    : out std_ulogic_vector(63 downto 0); -- current system time
    mti_o     : out std_ulogic_vector(NUM_HARTS-1 downto 0); -- machine timer interrupt
    msi_o     : out std_ulogic_vector(NUM_HARTS-1 downto 0) -- machine software interrupt
  );
end neorv32_clint;

architecture neorv32_clint_rtl of neorv32_clint is

  -- global machine timer --
  component neorv32_clint_mtime
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    en_i    : in  std_ulogic;
    rw_i    : in  std_ulogic;
    addr_i  : in  std_ulogic;
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0);
    mtime_o : out std_ulogic_vector(63 downto 0)
  );
  end component;

  -- time interrupt generator --
  component neorv32_clint_mtimecmp
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    en_i    : in  std_ulogic;
    rw_i    : in  std_ulogic;
    addr_i  : in  std_ulogic;
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0);
    mtime_i : in  std_ulogic_vector(63 downto 0);
    mti_o   : out std_ulogic
  );
  end component;

  -- software interrupt trigger --
  component neorv32_clint_swi
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    en_i    : in  std_ulogic;
    rw_i    : in  std_ulogic;
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0);
    swi_o   : out std_ulogic
  );
  end component;

  -- device offsets --
  constant clic_mswi_base_c     : unsigned(15 downto 0) := x"0000";
  constant clic_mtimecmp_base_c : unsigned(15 downto 0) := x"4000";
  constant clic_mtime_base_c    : unsigned(15 downto 0) := x"bff8";

  -- device access --
  signal mtime_en    : std_ulogic;
  signal mtimecmp_en : std_ulogic_vector(NUM_HARTS-1 downto 0);
  signal mswi_en     : std_ulogic_vector(NUM_HARTS-1 downto 0);

  -- read-back --
  type rb32_t is array (0 to NUM_HARTS-1) of std_ulogic_vector(31 downto 0);
  signal mtime_rd    : std_ulogic_vector(31 downto 0);
  signal mtimecmp_rd : rb32_t;
  signal mswi_rd     : rb32_t;

  -- misc --
  signal mtime : std_ulogic_vector(63 downto 0);
  signal ack_q : std_ulogic;
  signal rdata : std_ulogic_vector(31 downto 0);

begin

  -- MTIME - Machine Timer ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_clint_mtime_inst: neorv32_clint_mtime
  port map (
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    en_i    => mtime_en,
    rw_i    => bus_req_i.rw,
    addr_i  => bus_req_i.addr(2),
    wdata_i => bus_req_i.data,
    rdata_o => mtime_rd,
    mtime_o => mtime
  );

  -- device access --
  mtime_en <= '1' when (bus_req_i.stb = '1') and (unsigned(bus_req_i.addr(15 downto 3)) = clic_mtime_base_c(15 downto 3)) else '0';

  -- system time output: synchronize low and high words --
  time_output: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      time_o(31 downto 0) <= (others => '0');
    elsif rising_edge(clk_i) then
      time_o(31 downto 0) <= mtime(31 downto 0);
    end if;
  end process time_output;

  time_o(63 downto 32) <= mtime(63 downto 32);


  -- MTIMECMP - Per-Hart Time Comparator / Interrupt Generator ------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_clint_mtimecmp_gen:
  for i in 0 to NUM_HARTS-1 generate

    neorv32_clint_mtimecmp_inst: neorv32_clint_mtimecmp
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      en_i    => mtimecmp_en(i),
      rw_i    => bus_req_i.rw,
      addr_i  => bus_req_i.addr(2),
      wdata_i => bus_req_i.data,
      rdata_o => mtimecmp_rd(i),
      mtime_i => mtime,
      mti_o   => mti_o(i)
    );

    -- device access --
    mtimecmp_en(i) <= '1' when (bus_req_i.stb = '1') and (unsigned(bus_req_i.addr(15 downto 3)) = (clic_mtimecmp_base_c(15 downto 3) + i)) else '0';

  end generate;


  -- MSWI - Per-Hart Machine Software Interrupt Trigger -------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_clint_swi_gen:
  for i in 0 to NUM_HARTS-1 generate

    neorv32_clint_swi_inst: neorv32_clint_swi
    port map (
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      en_i    => mswi_en(i),
      rw_i    => bus_req_i.rw,
      wdata_i => bus_req_i.data,
      rdata_o => mswi_rd(i),
      swi_o   => msi_o(i)
    );

    -- device access --
    mswi_en(i) <= '1' when (bus_req_i.stb = '1') and (unsigned(bus_req_i.addr(15 downto 2)) = (clic_mswi_base_c(15 downto 2) + i)) else '0';

  end generate;


  -- Data Read-Back (OR all device read-backs) ----------------------------------------------
  -- -------------------------------------------------------------------------------------------
  read_back: process(mtime_rd, mtimecmp_rd, mswi_rd)
    variable mti_v, msi_v : std_ulogic_vector(31 downto 0);
  begin
    mti_v := (others => '0');
    msi_v := (others => '0');
    for i in 0 to NUM_HARTS-1 loop
      mti_v := mti_v or mtimecmp_rd(i);
      msi_v := msi_v or mswi_rd(i);
    end loop;
    rdata <= mtime_rd or mti_v or msi_v;
  end process read_back;


  -- Bus Handshake --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ack_q <= '0';
    elsif rising_edge(clk_i) then
      ack_q <= bus_req_i.stb;
    end if;
  end process bus_access;

  bus_rsp_o.ack  <= ack_q;
  bus_rsp_o.err  <= '0';
  bus_rsp_o.data <= rdata;


end neorv32_clint_rtl;


-- ================================================================================ --
-- NEORV32 SoC - CLINT MTIME (global machine timer)                                 --
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

entity neorv32_clint_mtime is
  port (
    clk_i   : in  std_ulogic; -- global clock line
    rstn_i  : in  std_ulogic; -- global reset line, low-active, async
    en_i    : in  std_ulogic; -- access-enable
    rw_i    : in  std_ulogic; -- read (0) / write (1)
    addr_i  : in  std_ulogic; -- low/high word select
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0); -- read data
    mtime_o : out std_ulogic_vector(63 downto 0)  -- global mtime.time (async words!)
  );
end neorv32_clint_mtime;

architecture neorv32_clint_mtime_rtl of neorv32_clint_mtime is

  signal we_q, re_q : std_ulogic_vector(1 downto 0);
  signal mtime_q : std_ulogic_vector(63 downto 0);
  signal carry_q : std_ulogic_vector(0 downto 0);
  signal inc_lo, inc_hi : std_ulogic_vector(32 downto 0);

begin

  -- 64-Bit Timer Core (split into two 32-bit registers) ------------------------------------
  -- -------------------------------------------------------------------------------------------
  mtime_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      we_q    <= (others => '0');
      re_q    <= (others => '0');
      mtime_q <= (others => '0');
      carry_q <= (others => '0');
    elsif rising_edge(clk_i) then
      we_q(0) <= en_i and rw_i and (not addr_i);
      we_q(1) <= en_i and rw_i and (    addr_i);
      re_q(0) <= en_i and (not addr_i);
      re_q(1) <= en_i and (    addr_i);
      -- low-word --
      if (we_q(0) = '1') then
        mtime_q(31 downto 0) <= wdata_i;
      else
        mtime_q(31 downto 0) <= inc_lo(31 downto 0);
      end if;
      carry_q(0) <= inc_lo(32); -- low-to-high carry
      -- high-word --
      if (we_q(1) = '1') then
        mtime_q(63 downto 32) <= wdata_i;
      else
        mtime_q(63 downto 32) <= inc_hi(31 downto 0);
      end if;
    end if;
  end process mtime_core;

  -- increments --
  inc_lo <= std_ulogic_vector(unsigned('0' & mtime_q(31 downto  0)) + 1);
  inc_hi <= std_ulogic_vector(unsigned('0' & mtime_q(63 downto 32)) + unsigned(carry_q));

  -- global time output; low and high words are off-sync by one cycle! --
  mtime_o <= mtime_q;

  -- read access --
  rdata_o <= mtime_q(63 downto 32) when (re_q(1) = '1') else
             mtime_q(31 downto  0) when (re_q(0) = '1') else (others => '0');


end neorv32_clint_mtime_rtl;


-- ================================================================================ --
-- NEORV32 SoC - CLINT MTIMECMP (per-hart time comparator)                          --
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

entity neorv32_clint_mtimecmp is
  port (
    clk_i   : in  std_ulogic; -- global clock line
    rstn_i  : in  std_ulogic; -- global reset line, low-active, async
    en_i    : in  std_ulogic; -- access-enable
    rw_i    : in  std_ulogic; -- read (0) / write (1)
    addr_i  : in  std_ulogic; -- low/high word select
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0); -- read data
    mtime_i : in  std_ulogic_vector(63 downto 0); -- global mtime.time (async words!)
    mti_o   : out std_ulogic -- interrupt
  );
end neorv32_clint_mtimecmp;

architecture neorv32_clint_mtimecmp_rtl of neorv32_clint_mtimecmp is

  signal rden_q : std_ulogic_vector(1 downto 0);
  signal mtimecmp_q : std_ulogic_vector(63 downto 0);
  signal cmp_lo_eq, cmp_lo_gt, cmp_lo_ge, cmp_hi_eq, cmp_hi_gt : std_ulogic;

begin

  -- MTIMECMP Access ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rden_q     <= (others => '0');
      mtimecmp_q <= (others => '0');
    elsif rising_edge(clk_i) then
      rden_q(0) <= en_i and (not addr_i);
      rden_q(1) <= en_i and (    addr_i);
      if (en_i = '1') and (rw_i = '1') then
        if (addr_i = '0') then
          mtimecmp_q(31 downto 0) <= wdata_i;
        else
          mtimecmp_q(63 downto 32) <= wdata_i;
        end if;
      end if;
    end if;
  end process write_access;

  -- read access --
  rdata_o <= mtimecmp_q(63 downto 32) when (rden_q(1) = '1') else
             mtimecmp_q(31 downto 00) when (rden_q(0) = '1') else (others => '0');


  -- Interrupt Generator (comparator is split across two cycles) ----------------------------
  -- -------------------------------------------------------------------------------------------
  irq_gen: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      cmp_lo_ge <= '0';
      mti_o     <= '0';
    elsif rising_edge(clk_i) then
      cmp_lo_ge <= cmp_lo_gt or cmp_lo_eq; -- low word greater-than or equal
      mti_o     <= cmp_hi_gt or (cmp_hi_eq and cmp_lo_ge);
    end if;
  end process irq_gen;

  -- sub-word comparators; there is one cycle delay between low (earlier) and high (later) word --
  cmp_lo_eq <= '1' when (unsigned(mtime_i(31 downto  0)) = unsigned(mtimecmp_q(31 downto  0))) else '0';
  cmp_lo_gt <= '1' when (unsigned(mtime_i(31 downto  0)) > unsigned(mtimecmp_q(31 downto  0))) else '0';
  cmp_hi_eq <= '1' when (unsigned(mtime_i(63 downto 32)) = unsigned(mtimecmp_q(63 downto 32))) else '0';
  cmp_hi_gt <= '1' when (unsigned(mtime_i(63 downto 32)) > unsigned(mtimecmp_q(63 downto 32))) else '0';


end neorv32_clint_mtimecmp_rtl;


-- ================================================================================ --
-- NEORV32 SoC - CLINT SWI (software interrupt trigger)                             --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

entity neorv32_clint_swi is
  port (
    clk_i   : in  std_ulogic; -- global clock line
    rstn_i  : in  std_ulogic; -- global reset line, low-active, async
    en_i    : in  std_ulogic; -- access-enable
    rw_i    : in  std_ulogic; -- read (0) / write (1)
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0); -- read data
    swi_o   : out std_ulogic -- interrupt
  );
end neorv32_clint_swi;

architecture neorv32_clint_swi_rtl of neorv32_clint_swi is

  signal rden_q, sip_q : std_ulogic;

begin

  -- MSI Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rden_q <= '0';
      sip_q  <= '0';
    elsif rising_edge(clk_i) then
      rden_q <= en_i;
      if (en_i = '1') and (rw_i = '1') then
        sip_q <= wdata_i(0);
      end if;
    end if;
  end process write_access;

  -- read access --
  rdata_o(31 downto 1) <= (others => '0');
  rdata_o(0) <= sip_q when (rden_q = '1') else '0';

  -- interrupt --
  swi_o <= sip_q;


end neorv32_clint_swi_rtl;
