-- ================================================================================ --
-- NEORV32 - Generic Single-Clock FIFO                                              --
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

entity neorv32_fifo is
  generic (
    FIFO_DEPTH : natural := 4;     -- number of FIFO entries; has to be a power of two; min 1
    FIFO_WIDTH : natural := 32;    -- size of data elements in FIFO
    FIFO_RSYNC : boolean := false; -- false = async read; true = sync read
    FIFO_SAFE  : boolean := false; -- true = allow read/write only if data/space available
    FULL_RESET : boolean := false  -- true = reset all memory cells (cannot be mapped to BRAM)
  );
  port (
    -- control and status --
    clk_i   : in  std_ulogic; -- clock, rising edge
    rstn_i  : in  std_ulogic; -- async reset, low-active
    clear_i : in  std_ulogic; -- sync reset, high-active
    half_o  : out std_ulogic; -- FIFO is at least half full
    level_o : out std_ulogic_vector(31 downto 0); -- fill level, zero-extended, 0 to FIFO_DEPTH
    -- write port --
    wdata_i : in  std_ulogic_vector(FIFO_WIDTH-1 downto 0); -- write data
    we_i    : in  std_ulogic; -- write enable
    free_o  : out std_ulogic; -- at least one entry is free when set
    -- read port --
    re_i    : in  std_ulogic; -- read enable
    rdata_o : out std_ulogic_vector(FIFO_WIDTH-1 downto 0); -- read data
    avail_o : out std_ulogic  -- data available when set
  );
end neorv32_fifo;

architecture neorv32_fifo_rtl of neorv32_fifo is

  -- make sure FIFO depth is a power of two --
  constant fifo_depth_c : natural := cond_sel_natural_f(is_power_of_two_f(FIFO_DEPTH), FIFO_DEPTH, 2**index_size_f(FIFO_DEPTH));

  -- FIFO storage --
  type fifo_mem_t is array (0 to fifo_depth_c-1) of std_ulogic_vector(FIFO_WIDTH-1 downto 0);
  signal fifo_mem : fifo_mem_t; -- for fifo_depth_c > 1
  signal fifo_reg : std_ulogic_vector(FIFO_WIDTH-1 downto 0); -- for fifo_depth_c = 1

  -- FIFO control and status --
  signal we, re, match, empty, full, half, free, avail : std_ulogic;

  -- write/read pointers --
  signal w_pnt, w_nxt, r_pnt, r_nxt, r_pnt_ff, level : std_ulogic_vector(index_size_f(fifo_depth_c) downto 0);

begin

  -- Access Control -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  re <= re_i when (FIFO_SAFE = false) else (re_i and avail); -- SAFE = read only if data available
  we <= we_i when (FIFO_SAFE = false) else (we_i and free);  -- SAFE = write only if free space left


  -- Pointers -------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  pointer_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      w_pnt <= (others => '0');
      r_pnt <= (others => '0');
    elsif rising_edge(clk_i) then
      w_pnt <= w_nxt;
      r_pnt <= r_nxt;
    end if;
  end process pointer_reg;

  -- pointer update --
  w_nxt <= (others => '0') when (clear_i = '1') else std_ulogic_vector(unsigned(w_pnt) + 1) when (we = '1') else w_pnt;
  r_nxt <= (others => '0') when (clear_i = '1') else std_ulogic_vector(unsigned(r_pnt) + 1) when (re = '1') else r_pnt;


  -- Status ---------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- more than 1 FIFO entry --
  check_large:
  if (fifo_depth_c > 1) generate
    match <= '1' when (r_pnt(r_pnt'left-1 downto 0) = w_pnt(w_pnt'left-1 downto 0)) else '0';
    full  <= '1' when (r_pnt(r_pnt'left) /= w_pnt(w_pnt'left)) and (match = '1') else '0';
    empty <= '1' when (r_pnt(r_pnt'left)  = w_pnt(w_pnt'left)) and (match = '1') else '0';
    level <= std_ulogic_vector(unsigned(w_pnt) - unsigned(r_pnt));
    half  <= level(level'left-1) or full;
  end generate;

  -- just 1 FIFO entry --
  check_small:
  if (fifo_depth_c = 1) generate
    match <= '1' when (r_pnt(0) = w_pnt(0)) else '0';
    full  <= not match;
    empty <= match;
    level <= (others => full);
    half  <= full;
  end generate;

  -- aliases --
  free  <= not full;
  avail <= not empty;

  -- fill level, zero-extended --
  level_extend: process(level)
  begin
    level_o <= (others => '0');
    level_o(level'left downto 0) <= level(level'left downto 0);
  end process level_extend;


  -- Write Access (with Reset) --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  memory_full_reset: -- cannot be mapped to memory primitives
  if FULL_RESET generate

    -- just 1 FIFO entry --
    fifo_write_reset_small:
    if (fifo_depth_c = 1) generate
      write_reset_small: process(rstn_i, clk_i)
      begin
        if (rstn_i = '0') then
          fifo_reg <= (others => '0');
        elsif rising_edge(clk_i) then
          if (we = '1') then
            fifo_reg <= wdata_i;
          end if;
        end if;
      end process write_reset_small;
    end generate;

    -- more than 1 FIFO entry --
    fifo_write_reset_large:
    if (fifo_depth_c > 1) generate
      write_reset_large: process(rstn_i, clk_i)
      begin
        if (rstn_i = '0') then
          fifo_mem <= (others => (others => '0'));
        elsif rising_edge(clk_i) then
          if (we = '1') then
            fifo_mem(to_integer(unsigned(w_pnt(w_pnt'left-1 downto 0)))) <= wdata_i;
          end if;
        end if;
      end process write_reset_large;
    end generate;

  end generate;


  -- Write Access (without Reset) -----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  memory_no_reset: -- no reset to infer memory primitives
  if not FULL_RESET generate

    -- just 1 FIFO entry --
    fifo_write_noreset_small:
    if (fifo_depth_c = 1) generate
      write_small: process(clk_i)
      begin
        if rising_edge(clk_i) then
          if (we = '1') then
            fifo_reg <= wdata_i;
          end if;
        end if;
      end process write_small;
    end generate;

    -- more than 1 FIFO entry --
    fifo_write_noreset_large:
    if (fifo_depth_c > 1) generate
      write_large: process(clk_i)
      begin
        if rising_edge(clk_i) then
          if (we = '1') then
            fifo_mem(to_integer(unsigned(w_pnt(w_pnt'left-1 downto 0)))) <= wdata_i;
          end if;
        end if;
      end process write_large;
    end generate;

  end generate;


  -- Asynchronous Read Access ---------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  fifo_read_async:
  if not FIFO_RSYNC generate

    -- just 1 FIFO entry --
    fifo_read_async_small:
    if (fifo_depth_c = 1) generate
      rdata_o <= fifo_reg;
    end generate;

    -- more than 1 FIFO entry --
    fifo_read_async_large:
    if (fifo_depth_c > 1) generate
      async_r_pnt_reg: process(clk_i)
      begin
        if rising_edge(clk_i) then
          r_pnt_ff <= r_nxt; -- individual read address register; allows mapping "async" FIFOs to memory primitives
        end if;
      end process async_r_pnt_reg;
      rdata_o <= fifo_mem(to_integer(unsigned(r_pnt_ff(r_pnt_ff'left-1 downto 0))));
    end generate;

    -- status --
    free_o  <= free;
    avail_o <= avail;
    half_o  <= half;

  end generate;


  -- Synchronous Read Access ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  fifo_read_sync:
  if FIFO_RSYNC generate

    -- just 1 FIFO entry --
    fifo_read_sync_small:
    if (fifo_depth_c = 1) generate
      rdata_o <= fifo_reg;
    end generate;

    -- more than 1 FIFO entry --
    fifo_read_sync_large:
    if (fifo_depth_c > 1) generate
      sync_read_large: process(clk_i)
      begin
        if rising_edge(clk_i) then
          rdata_o <= fifo_mem(to_integer(unsigned(r_pnt(r_pnt'left-1 downto 0))));
        end if;
      end process sync_read_large;
    end generate;

    -- registered status --
    sync_status: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        free_o  <= '0';
        avail_o <= '0';
        half_o  <= '0';
      elsif rising_edge(clk_i) then
        free_o  <= free;
        avail_o <= avail;
        half_o  <= half;
      end if;
    end process sync_status;

  end generate;


end neorv32_fifo_rtl;
