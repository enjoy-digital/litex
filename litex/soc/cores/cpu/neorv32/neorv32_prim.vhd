-- ================================================================================ --
-- NEORV32 - Primitives - Generic Single-Clock FIFO (FIFO)                          --
-- -------------------------------------------------------------------------------- --
-- The FIFO operates in "first-word-fall-through" (FWFT) mode: the first written    --
-- word appears directly at the output (after the synchronous-read delay) without   --
-- any explicit read access.                                                        --
--                                                                                  --
-- The status signals "free space left" (free_o) and "data available" (avail_o)     --
-- are synchronized to the according port:                                          --
-- - free_o  -> write port                                                          --
-- - avail_o -> read port                                                           --
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

entity neorv32_prim_fifo is
  generic (
    AWIDTH  : natural; -- number of FIFO entries; has to be a power of two; min 1
    DWIDTH  : natural; -- size of data elements in FIFO
    OUTGATE : boolean  -- true = output zero if no data available
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic;                           -- clock, rising edge
    rstn_i  : in  std_ulogic;                           -- async reset, low-active
    clear_i : in  std_ulogic;                           -- sync reset, high-active
    -- write port --
    wdata_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    we_i    : in  std_ulogic;                           -- write enable
    free_o  : out std_ulogic;                           -- at least one entry is free when set
    -- read port --
    re_i    : in  std_ulogic;                           -- read enable
    rdata_o : out std_ulogic_vector(DWIDTH-1 downto 0); -- read data
    avail_o : out std_ulogic                            -- data available when set
  );
end neorv32_prim_fifo;

architecture neorv32_prim_fifo_rtl of neorv32_prim_fifo is

  -- memory core --
  type ram_t is array ((2**AWIDTH)-1 downto 0) of std_ulogic_vector(DWIDTH-1 downto 0);
  signal fifo : ram_t;

  -- local signals --
  signal rdata : std_ulogic_vector(DWIDTH-1 downto 0);
  signal we, re, ram_re, match, full, empty, avail : std_ulogic;
  signal w_pnt, w_nxt, r_pnt, r_nxt : std_ulogic_vector(AWIDTH downto 0);

begin

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

  -- access control --
  re <= re_i and (not empty); -- read only if data available
  we <= we_i and (not full);  -- write only if free space available

  -- pointer update --
  w_nxt <= (others => '0') when (clear_i = '1') else std_ulogic_vector(unsigned(w_pnt) + 1) when (we = '1') else w_pnt;
  r_nxt <= (others => '0') when (clear_i = '1') else std_ulogic_vector(unsigned(r_pnt) + 1) when (re = '1') else r_pnt;

  -- Status ---------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- more than 1 FIFO entry --
  fifo_status_large:
  if (AWIDTH > 0) generate
    match <= '1' when (r_pnt(AWIDTH-1 downto 0) = w_pnt(AWIDTH-1 downto 0)) else '0';
    full  <= '1' when (r_pnt(AWIDTH) /= w_pnt(AWIDTH)) and (match = '1') else '0';
    empty <= '1' when (r_pnt(AWIDTH)  = w_pnt(AWIDTH)) and (match = '1') else '0';
    -- [important] 'avail' is synchronized to the read port --
    status_reg: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        avail <= '0';
      elsif rising_edge(clk_i) then
        avail <= not empty;
      end if;
    end process status_reg;
  end generate;

  -- just 1 FIFO entry --
  fifo_status_small:
  if (AWIDTH = 0) generate
    match <= '1' when (r_pnt(0) = w_pnt(0)) else '0';
    full  <= not match;
    empty <= match;
    avail <= not empty;
  end generate;

  -- status output --
  free_o  <= not full;
  avail_o <= avail;


  -- Memory ---------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- more than 1 FIFO entry --
  fifo_memory_large:
  if (AWIDTH > 0) generate
    memory_core: process(clk_i) -- simple dual-port RAM
    begin
      if rising_edge(clk_i) then
        if (we = '1') then
          fifo(to_integer(unsigned(w_pnt(AWIDTH-1 downto 0)))) <= wdata_i;
        end if;
        rdata <= fifo(to_integer(unsigned(r_pnt(AWIDTH-1 downto 0))));
      end if;
    end process memory_core;
  end generate;

  -- just 1 FIFO entry --
  fifo_memory_small:
  if (AWIDTH = 0) generate
    memory_core: process(rstn_i, clk_i) -- single register
    begin
      if (rstn_i = '0') then
        fifo(0) <= (others => '0');
      elsif rising_edge(clk_i) then
        if (we = '1') then
          fifo(0) <= wdata_i;
        end if;
      end if;
    end process memory_core;
    rdata <= fifo(0);
  end generate;

  -- output gate: output zero if no data available --
  rdata_o <= (others => '0') when OUTGATE and (avail = '0') else rdata;

end neorv32_prim_fifo_rtl;


-- ================================================================================ --
-- NEORV32 - Primitives - Generic Single-Port RAM (SPRAM)                           --
-- -------------------------------------------------------------------------------- --
-- Provides a single read/write port.                                               --
-- Can be mapped to blockRAM primitives.                                            --
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

entity neorv32_prim_spram is
  generic (
    AWIDTH : natural; -- address width (number of bits)
    DWIDTH : natural; -- data width (number of bits)
    OUTREG : boolean  -- add output register stage
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic;                           -- global clock
    -- read/write port --
    en_i   : in  std_ulogic;                           -- access enable
    rw_i   : in  std_ulogic;                           -- 0=read, 1=write
    addr_i : in  std_ulogic_vector(AWIDTH-1 downto 0); -- address
    data_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    data_o : out std_ulogic_vector(DWIDTH-1 downto 0)  -- read data
  );
end neorv32_prim_spram;

architecture neorv32_prim_spram_rtl of neorv32_prim_spram is

  type ram_t is array ((2**AWIDTH)-1 downto 0) of std_ulogic_vector(DWIDTH-1 downto 0);
  signal spram : ram_t;
  signal rdata : std_ulogic_vector(DWIDTH-1 downto 0);

begin

  -- Memory Core ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  memory_core: process(clk_i)
  begin
    if rising_edge(clk_i) then
      if (en_i = '1') then
        if (rw_i = '1') then
          spram(to_integer(unsigned(addr_i))) <= data_i;
        else
          rdata <= spram(to_integer(unsigned(addr_i)));
        end if;
      end if;
    end if;
  end process memory_core;

  -- Output Register ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  output_register_enabled:
  if OUTREG generate -- might improve FPGA mapping and/or timing results
    read_outreg: process(clk_i)
    begin
      if rising_edge(clk_i) then
        data_o <= rdata;
      end if;
    end process read_outreg;
  end generate;

  -- no output register --
  output_register_disabled:
  if not OUTREG generate
    data_o <= rdata;
  end generate;

end neorv32_prim_spram_rtl;


-- ================================================================================ --
-- NEORV32 - Primitives - Generic Simple Dual-Port RAM (SDPRAM)                     --
-- -------------------------------------------------------------------------------- --
-- Provides a single read/write port and a read-only port.                          --
-- Can be mapped to blockRAM primitives.                                            --
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

entity neorv32_prim_sdpram is
  generic (
    AWIDTH : natural; -- address width (number of bits)
    DWIDTH : natural; -- data width (number of bits)
    OUTREG : boolean  -- add output register stage
  );
  port (
    -- global control --
    clk_i    : in  std_ulogic;                           -- global clock
    -- read/write port --
    a_en_i   : in  std_ulogic;                           -- access enable
    a_rw_i   : in  std_ulogic;                           -- 0=read, 1=write
    a_addr_i : in  std_ulogic_vector(AWIDTH-1 downto 0); -- read/write address
    a_data_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    a_data_o : out std_ulogic_vector(DWIDTH-1 downto 0); -- read data
    -- read port --
    b_en_i   : in  std_ulogic;                           -- access enable
    b_addr_i : in  std_ulogic_vector(AWIDTH-1 downto 0); -- read address
    b_data_o : out std_ulogic_vector(DWIDTH-1 downto 0)  -- read data
  );
end neorv32_prim_sdpram;

architecture neorv32_prim_sdpram_rtl of neorv32_prim_sdpram is

  type ram_t is array ((2**AWIDTH)-1 downto 0) of std_ulogic_vector(DWIDTH-1 downto 0);
  signal sdpram : ram_t;
  signal a_rdata, b_rdata : std_ulogic_vector(DWIDTH-1 downto 0);

begin

  -- Memory Core ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  memory_core: process(clk_i)
  begin
    if rising_edge(clk_i) then
      -- port A: read/write --
      if (a_en_i = '1') then
        if (a_rw_i = '1') then
          sdpram(to_integer(unsigned(a_addr_i))) <= a_data_i;
        else
          a_rdata <= sdpram(to_integer(unsigned(a_addr_i)));
        end if;
      end if;
      -- port B: read-only --
      if (b_en_i = '1') then
        b_rdata <= sdpram(to_integer(unsigned(b_addr_i)));
      end if;
    end if;
  end process memory_core;

  -- Output Register ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  output_register_enabled:
  if OUTREG generate -- might improve FPGA mapping and/or timing results
    read_outreg: process(clk_i)
    begin
      if rising_edge(clk_i) then
        a_data_o <= a_rdata;
        b_data_o <= b_rdata;
      end if;
    end process read_outreg;
  end generate;

  -- no output register --
  output_register_disabled:
  if not OUTREG generate
    a_data_o <= a_rdata;
    b_data_o <= b_rdata;
  end generate;

end neorv32_prim_sdpram_rtl;


-- ================================================================================ --
-- NEORV32 - Primitives - Generic 2-Cycle Signed/Unsigned Integer Multiplier (MUL)  --
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

entity neorv32_prim_mul is
  generic (
    DWIDTH : natural -- operand width
  );
  port (
    -- global control --
    clk_i    : in  std_ulogic;                              -- global clock
    rstn_i   : in  std_ulogic;                              -- global reset, low-active, async
    -- data path --
    en_i     : in  std_ulogic;                              -- enable input operand registers
    opa_i    : in  std_ulogic_vector(DWIDTH-1 downto 0);    -- operand A
    opa_sn_i : in  std_ulogic;                              -- operand A is a signed number
    opb_i    : in  std_ulogic_vector(DWIDTH-1 downto 0);    -- operand B
    opb_sn_i : in  std_ulogic;                              -- operand B is a signed number
    res_o    : out std_ulogic_vector((2*DWIDTH)-1 downto 0) -- resulting product
  );
end neorv32_prim_mul;

architecture neorv32_prim_mul_rtl of neorv32_prim_mul is

  signal opa, opb : signed(DWIDTH downto 0);
  signal res : signed((2*DWIDTH)+1 downto 0);

begin

  -- Input Registers ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  in_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      opa <= (others => '0');
      opb <= (others => '0');
    elsif rising_edge(clk_i) then
      if (en_i = '1') then
        opa <= signed((opa_i(opa_i'left) and opa_sn_i) & opa_i);
        opb <= signed((opb_i(opb_i'left) and opb_sn_i) & opb_i);
      end if;
    end if;
  end process in_reg;

  -- Output Register ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  out_reg: process(clk_i)
  begin
    if rising_edge(clk_i) then -- no reset to improve DSP mapping
      res <= opa * opb;
    end if;
  end process out_reg;

  -- result --
  res_o <= std_ulogic_vector(res((2*DWIDTH)-1 downto 0));

end neorv32_prim_mul_rtl;


-- ================================================================================ --
-- NEORV32 - Primitives - Generic 64-Bit Counter Module                             --
-- -------------------------------------------------------------------------------- --
-- High and low words are split across two individual registers to improve timing   --
-- by cutting the carry chain. The actual counter width can be trimmed via CWIDTH.  --
-- [WARNING] High and low words of counter output cnt_o are _NOT_ synchronized!     --
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

entity neorv32_prim_cnt is
  generic (
    CWIDTH : natural range 0 to 64 -- actual counter width (0..64)
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic;                     -- global clock, rising edge
    rstn_i : in  std_ulogic;                     -- global reset, low-active, async
    inc_i  : in  std_ulogic;                     -- enable counter increment
    -- read/write access --
    we_i   : in  std_ulogic_vector(1 downto 0);  -- subword write enable
    data_i : in  std_ulogic_vector(31 downto 0); -- subword write data
    oe_i   : in  std_ulogic;                     -- output enable
    cnt_o  : out std_ulogic_vector(63 downto 0)  -- trimmed counter output
  );
end neorv32_prim_cnt;

architecture neorv32_prim_cnt_rtl of neorv32_prim_cnt is

  signal count : std_ulogic_vector(63 downto 0);
  signal carry, incen : std_ulogic_vector(0 downto 0);
  signal inc_lo, inc_hi : std_ulogic_vector(32 downto 0);

begin

  -- 64-Bit Counter (split across two 32-bit registers) -------------------------------------
  -- -------------------------------------------------------------------------------------------
  counter_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      incen <= (others => '0');
      count <= (others => '0');
      carry <= (others => '0');
    elsif rising_edge(clk_i) then
      -- increment enable --
      incen(0) <= inc_i;
      -- low-word --
      if (we_i(0) = '1') then
        count(31 downto 0) <= data_i;
      else
        count(31 downto 0) <= inc_lo(31 downto 0);
      end if;
      carry(0) <= inc_lo(32); -- low-to-high carry
      -- high-word --
      if (we_i(1) = '1') then
        count(63 downto 32) <= data_i;
      else
        count(63 downto 32) <= inc_hi(31 downto 0);
      end if;
    end if;
  end process counter_core;

  -- increments --
  inc_lo <= std_ulogic_vector(unsigned('0' & count(31 downto  0)) + unsigned(incen));
  inc_hi <= std_ulogic_vector(unsigned('0' & count(63 downto 32)) + unsigned(carry));

  -- Output Gating and Trimming -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trim: process(oe_i, count)
  begin
    cnt_o <= (others => '0');
    if (oe_i = '1') then
      cnt_o(CWIDTH-1 downto 0) <= count(CWIDTH-1 downto 0);
    end if;
  end process trim;

end neorv32_prim_cnt_rtl;
