-- ================================================================================ --
-- NEORV32 SoC - RISC-V Core-Local Interruptor (CLINT)                              --
-- -------------------------------------------------------------------------------- --
-- Compatible to the RISC-V & SiFive(R) CLINT specifications. Supports machine      --
-- software interrupts and machine timer interrupts for up to 4095 harts.           --
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

entity neorv32_clint is
  generic (
    NUM_HARTS : natural range 1 to 4095 -- number of physical CPU cores
  );
  port (
    clk_i     : in  std_ulogic;                              -- global clock line
    rstn_i    : in  std_ulogic;                              -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;                               -- bus request
    bus_rsp_o : out bus_rsp_t;                               -- bus response
    time_o    : out std_ulogic_vector(63 downto 0);          -- current system time
    mti_o     : out std_ulogic_vector(NUM_HARTS-1 downto 0); -- machine timer interrupt
    msi_o     : out std_ulogic_vector(NUM_HARTS-1 downto 0)  -- machine software interrupt
  );
end neorv32_clint;

architecture neorv32_clint_rtl of neorv32_clint is

  -- timer interrupt generator --
  component neorv32_clint_mtimecmp
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    mtime_i : in  std_ulogic_vector(63 downto 0);
    we_i    : in  std_ulogic_vector(1 downto 0);
    re_i    : in  std_ulogic_vector(1 downto 0);
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0);
    mti_o   : out std_ulogic
  );
  end component;

  -- device offsets --
  constant base_mswi_c     : unsigned(15 downto 0) := x"0000";
  constant base_mtimecmp_c : unsigned(15 downto 0) := x"4000";
  constant base_mtime_c    : unsigned(15 downto 0) := x"bff8";

  -- mtime access --
  signal mtime_en : std_ulogic;
  signal mtime_we : std_ulogic_vector(1 downto 0);

  -- mtimecmp access --
  type mtimecmp_rwe_t is array (0 to NUM_HARTS-1) of std_ulogic_vector(1 downto 0);
  signal mtimecmp_we : mtimecmp_rwe_t;
  signal mtimecmp_re : mtimecmp_rwe_t;
  signal mtimecmp_en : std_ulogic_vector(NUM_HARTS-1 downto 0);

  -- mswi access --
  signal mswi_en, mswi : std_ulogic_vector(NUM_HARTS-1 downto 0);

  -- read-back --
  type rb32_t is array (0 to NUM_HARTS-1) of std_ulogic_vector(31 downto 0);
  signal mtimecmp_rd : rb32_t;
  signal mswi_rd     : rb32_t;
  signal mtime       : std_ulogic_vector(63 downto 0);
  signal mtime_rd    : std_ulogic_vector(31 downto 0);
  signal rdata       : std_ulogic_vector(31 downto 0);

begin

  -- MTIME - Global Machine Timer -----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_clint_mtime_inst: entity neorv32.neorv32_prim_cnt
  generic map (
    CWIDTH => 64
  )
  port map (
    clk_i  => clk_i,
    rstn_i => rstn_i,
    inc_i  => '1', -- permanent increment
    we_i   => mtime_we,
    data_i => bus_req_i.data,
    oe_i   => '1', -- permanent output (required for MTIME comparators)
    cnt_o  => mtime
  );

  -- device access --
  mtime_en <= '1' when (bus_req_i.stb = '1') and (unsigned(bus_req_i.addr(15 downto 3)) = base_mtime_c(15 downto 3)) else '0';
  mtime_we(0) <= mtime_en and bus_req_i.rw and (not bus_req_i.addr(2));
  mtime_we(1) <= mtime_en and bus_req_i.rw and (    bus_req_i.addr(2));

  -- subword read-back --
  mtime_rd <= (others => '0') when (mtime_en = '0') else
              mtime(63 downto 32) when (bus_req_i.addr(2) = '1') else mtime(31 downto 0);

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
      mtime_i => mtime,
      we_i    => mtimecmp_we(i),
      re_i    => mtimecmp_re(i),
      wdata_i => bus_req_i.data,
      rdata_o => mtimecmp_rd(i),
      mti_o   => mti_o(i)
    );

    -- device access --
    mtimecmp_en(i) <= '1' when (bus_req_i.stb = '1') and (unsigned(bus_req_i.addr(15 downto 3)) = (base_mtimecmp_c(15 downto 3) + i)) else '0';
    mtimecmp_we(i)(0) <= mtimecmp_en(i) and (    bus_req_i.rw) and (not bus_req_i.addr(2));
    mtimecmp_we(i)(1) <= mtimecmp_en(i) and (    bus_req_i.rw) and (    bus_req_i.addr(2));
    mtimecmp_re(i)(0) <= mtimecmp_en(i) and (not bus_req_i.rw) and (not bus_req_i.addr(2));
    mtimecmp_re(i)(1) <= mtimecmp_en(i) and (not bus_req_i.rw) and (    bus_req_i.addr(2));

  end generate;


  -- MSWI - Per-Hart Machine Software Interrupt Trigger -------------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_clint_swi_gen:
  for i in 0 to NUM_HARTS-1 generate

    mswi_reg: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
         mswi(i) <= '0';
      elsif rising_edge(clk_i) then
        if (mswi_en(i) = '1') and (bus_req_i.rw = '1') then
           mswi(i) <= bus_req_i.data(0);
        end if;
      end if;
    end process mswi_reg;

    -- interrupt output --
    msi_o(i) <= mswi(i);

    -- device access --
    mswi_en(i) <= '1' when (bus_req_i.stb = '1') and (unsigned(bus_req_i.addr(15 downto 2)) = (base_mswi_c(15 downto 2) + i)) else '0';

    -- read-back --
    mswi_rd(i) <= (others => '0') when (mswi_en(i) = '0') else (x"0000000" & "000" & mswi(i));

  end generate;


  -- Data Read-Back (OR all device read-backs) ----------------------------------------------
  -- -------------------------------------------------------------------------------------------
  read_back: process(mtime_rd, mtimecmp_rd, mswi_rd)
    variable tmp_v : std_ulogic_vector(31 downto 0);
  begin
    tmp_v := (others => '0');
    for i in 0 to NUM_HARTS-1 loop
      tmp_v := tmp_v or mtimecmp_rd(i) or mswi_rd(i);
    end loop;
    rdata <= mtime_rd or tmp_v;
  end process read_back;


  -- Bus Response ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_response: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o <= rsp_terminate_c;
    elsif rising_edge(clk_i) then
      bus_rsp_o <= rsp_terminate_c;
      bus_rsp_o.ack <= mtime_en or or_reduce_f(mtimecmp_en) or or_reduce_f(mswi_en);
      if (bus_req_i.stb = '1') then
        bus_rsp_o.data <= rdata;
      end if;
    end if;
  end process bus_response;

end neorv32_clint_rtl;


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
    mtime_i : in  std_ulogic_vector(63 downto 0); -- global mtime (async words!)
    we_i    : in  std_ulogic_vector(1 downto 0); -- HI/LO word write enable
    re_i    : in  std_ulogic_vector(1 downto 0); -- HI/LO word read enable
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0); -- read data
    mti_o   : out std_ulogic -- interrupt
  );
end neorv32_clint_mtimecmp;

architecture neorv32_clint_mtimecmp_rtl of neorv32_clint_mtimecmp is

  signal mtimecmp_q : std_ulogic_vector(63 downto 0);
  signal cmp_lo_eq, cmp_lo_gt, cmp_lo_ge, cmp_hi_eq, cmp_hi_gt : std_ulogic;

begin

  -- MTIMECMP Access ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      mtimecmp_q <= (others => '0');
    elsif rising_edge(clk_i) then
      if (we_i(0) = '1') then
        mtimecmp_q(31 downto 0) <= wdata_i;
      end if;
      if (we_i(1) = '1') then
        mtimecmp_q(63 downto 32) <= wdata_i;
      end if;
    end if;
  end process write_access;

  -- read access --
  rdata_o <= mtimecmp_q(63 downto 32) when (re_i(1) = '1') else
             mtimecmp_q(31 downto 00) when (re_i(0) = '1') else (others => '0');


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

