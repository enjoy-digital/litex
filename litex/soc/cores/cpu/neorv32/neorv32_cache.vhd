-- ================================================================================ --
-- NEORV32 SoC - Generic Cache                                                      --
-- -------------------------------------------------------------------------------- --
-- Configurable generic cache module. The cache is direct-mapped and implements     --
-- "write-back" and "write-allocate" strategies.                                    --
--                                                                                  --
-- Uncached / direct accesses: Several bus transaction types will bypass the cache: --
-- * atomic memory operations                                                       --
-- * accesses within debug-mode (on-chip debugger)                                  --
-- * accesses to the explicit "uncached address space page" (or higher); defined by --
--   the 4 most significant address bits (UC_BEGIN)                                 --
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

entity neorv32_cache is
  generic (
    NUM_BLOCKS : natural range 2 to 1024;       -- number of cache blocks (min 2), has to be a power of 2
    BLOCK_SIZE : natural range 4 to 32768;      -- cache block size in bytes (min 4), has to be a power of 2
    UC_BEGIN   : std_ulogic_vector(3 downto 0); -- begin of uncached address space (page number / 4 MSBs of address)
    READ_ONLY  : boolean                        -- read-only accesses for host
  );
  port (
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    clean_o    : out std_ulogic; -- cache is clean
    host_req_i : in  bus_req_t;  -- host request
    host_rsp_o : out bus_rsp_t;  -- host response
    bus_req_o  : out bus_req_t;  -- bus request
    bus_rsp_i  : in  bus_rsp_t   -- bus response
  );
end neorv32_cache;

architecture neorv32_cache_rtl of neorv32_cache is

  -- make sure cache sizes are a power of two --
  constant block_num_c  : natural := 2**index_size_f(NUM_BLOCKS);
  constant block_size_c : natural := 2**index_size_f(BLOCK_SIZE);

  -- cache layout --
  constant offset_size_c : natural := index_size_f(block_size_c/4); -- WORD offset!
  constant index_size_c  : natural := index_size_f(block_num_c);
  constant tag_size_c    : natural := 32 - (offset_size_c + index_size_c + 2);

  -- cache memory component --
  component neorv32_cache_memory
  generic (
    NUM_BLOCKS : natural;
    BLOCK_SIZE : natural;
    READ_ONLY  : boolean
  );
  port (
    rstn_i  : in  std_ulogic;
    clk_i   : in  std_ulogic;
    inval_i : in  std_ulogic;
    new_i   : in  std_ulogic;
    dirty_i : in  std_ulogic;
    hit_o   : out std_ulogic;
    dirty_o : out std_ulogic;
    tag_o   : out std_ulogic_vector(31 downto 0);
    clean_o : out std_ulogic;
    addr_i  : in  std_ulogic_vector(31 downto 0);
    we_i    : in  std_ulogic_vector(3 downto 0);
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0)
  );
  end component;

  -- control -> cache interface --
  type cache_o_t is record
    cmd_inv : std_ulogic;
    cmd_new : std_ulogic;
    cmd_dir : std_ulogic;
    addr    : std_ulogic_vector(31 downto 0);
    data    : std_ulogic_vector(31 downto 0);
    we      : std_ulogic_vector(3 downto 0);
  end record;
  signal cache_o : cache_o_t;

  -- cache -> control interface --
  type cache_i_t is record
    sta_hit : std_ulogic;
    sta_dir : std_ulogic;
    sta_cln : std_ulogic;
    sta_tag : std_ulogic_vector(31 downto 0);
    data    : std_ulogic_vector(31 downto 0);
  end record;
  signal cache_i : cache_i_t;

  -- control fsm --
  type state_t is (
    S_IDLE, S_LOOKUP, S_DIRECT_REQ, S_DIRECT_RSP,
    S_DOWNLOAD_REQ, S_DOWNLOAD_RSP, S_DOWNLOAD_DONE, S_DOWNLOAD_ERR,
    S_UPLOAD_GET, S_UPLOAD_REQ, S_UPLOAD_RSP,
    S_FLUSH_START, S_FLUSH_READ, S_FLUSH_CHECK, S_FLUSH_DONE,
    S_ERROR
  );
  type ctrl_t is record
    state    : state_t;
    stret    : state_t;
    buf_req  : std_ulogic;
    buf_sync : std_ulogic;
  end record;
  signal ctrl, ctrl_nxt : ctrl_t;

  -- address generator --
  type addr_t is record
    tag : std_ulogic_vector(tag_size_c-1 downto 0);
    idx : std_ulogic_vector(index_size_c-1 downto 0);
    ofs : std_ulogic_vector(offset_size_c-1 downto 0); -- word offset
  end record;
  signal addr, addr_nxt : addr_t;

begin

  -- Control Engine FSM Sync ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  ctrl_engine_sync: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl.state    <= S_IDLE;
      ctrl.stret    <= S_IDLE;
      ctrl.buf_req  <= '0';
      ctrl.buf_sync <= '0';
      addr.tag      <= (others => '0');
      addr.idx      <= (others => '0');
      addr.ofs      <= (others => '0');
      clean_o       <= '0';
    elsif rising_edge(clk_i) then
      ctrl.state    <= ctrl_nxt.state;
      ctrl.stret    <= ctrl_nxt.stret;
      ctrl.buf_req  <= ctrl_nxt.buf_req;
      ctrl.buf_sync <= ctrl_nxt.buf_sync;
      addr          <= addr_nxt;
      -- cache clean (sync with downstream memory)? --
      if (cache_i.sta_cln = '1') and (ctrl.state = S_IDLE) then
        clean_o <= '1';
      else
        clean_o <= '0';
      end if;
    end if;
  end process ctrl_engine_sync;


  -- Control Engine FSM Comb ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  ctrl_engine_comb: process(ctrl, addr, host_req_i, cache_i, bus_rsp_i)
  begin
    -- control engine defaults --
    ctrl_nxt.state    <= ctrl.state;
    ctrl_nxt.stret    <= ctrl.stret;
    ctrl_nxt.buf_req  <= ctrl.buf_req or host_req_i.stb;
    ctrl_nxt.buf_sync <= ctrl.buf_sync or host_req_i.fence;
    addr_nxt          <= addr;

    -- cache access defaults --
    cache_o.cmd_inv <= '0';
    cache_o.cmd_new <= '0';
    cache_o.cmd_dir <= '0';
    cache_o.addr    <= host_req_i.addr;
    cache_o.we      <= (others => '0');
    cache_o.data    <= host_req_i.data;

    -- host response defaults --
    host_rsp_o <= rsp_terminate_c; -- all-zero

    -- bus interface defaults (default = host access) --
    bus_req_o.addr  <= addr.tag & addr.idx & addr.ofs & "00"; -- always word-aligned
    bus_req_o.data  <= cache_i.data;
    bus_req_o.ben   <= (others => '1'); -- full-word writes only
    bus_req_o.stb   <= '0'; -- no request by default
    bus_req_o.rw    <= '0';
    bus_req_o.src   <= host_req_i.src; -- pass-through
    bus_req_o.priv  <= host_req_i.priv; -- pass-through
    bus_req_o.debug <= host_req_i.debug; -- pass-through
    bus_req_o.amo   <= '0'; -- cache accesses cannot be atomic
    bus_req_o.amoop <= (others => '0'); -- cache accesses cannot be atomic
    bus_req_o.fence <= '0'; -- no fence by default

    -- fsm --
    case ctrl.state is

      when S_IDLE => -- wait for request
      -- ------------------------------------------------------------
        if (host_req_i.fence = '1') or (ctrl.buf_sync = '1') then -- (pending) sync request
          ctrl_nxt.state <= S_FLUSH_START;
        elsif (host_req_i.stb = '1') or (ctrl.buf_req = '1') then -- (pending) access request
          if (host_req_i.rw = '1') and (READ_ONLY = true) then -- invalid write access
            ctrl_nxt.state <= S_ERROR;
          elsif (unsigned(host_req_i.addr(31 downto 28)) >= unsigned(UC_BEGIN)) or -- uncached address space
                (host_req_i.amo = '1') or (host_req_i.debug = '1') then -- atomic or debug access
            ctrl_nxt.state <= S_DIRECT_REQ;
          else
            ctrl_nxt.state <= S_LOOKUP;
          end if;
        end if;

      when S_LOOKUP => -- check if cache hit
      -- ------------------------------------------------------------
        ctrl_nxt.buf_req <= '0'; -- access (about to be) completed
        host_rsp_o.data  <= cache_i.data; -- cache response data (for hit)
        addr_nxt.ofs     <= (others => '0'); -- align block base address for upload/download
        addr_nxt.idx     <= host_req_i.addr((offset_size_c+2+index_size_c)-1 downto offset_size_c+2); -- index of referenced block
        ctrl_nxt.stret   <= S_DOWNLOAD_REQ; -- start block download immediately after upload has completed
        --
        if (cache_i.sta_hit = '1') then -- cache hit
          if (host_req_i.rw = '0') or (READ_ONLY = true) then -- read access
            host_rsp_o.ack <= '1';
          else -- write access
            cache_o.cmd_dir <= '1'; -- cache block is dirty now
            cache_o.we      <= host_req_i.ben; -- finalize cache write access
            host_rsp_o.ack  <= '1';
          end if;
          ctrl_nxt.state <= S_IDLE;
        else -- cache miss
          if (cache_i.sta_dir = '1') and (READ_ONLY = false) then -- block is dirty, upload first
            addr_nxt.tag   <= cache_i.sta_tag(31 downto 32-tag_size_c); -- tag of accessed block
            ctrl_nxt.state <= S_UPLOAD_GET;
          else -- block is clean, replace by new block
            addr_nxt.tag   <= host_req_i.addr(31 downto 32-tag_size_c); -- tag of referenced block
            ctrl_nxt.state <= S_DOWNLOAD_REQ;
          end if;
        end if;


      when S_DIRECT_REQ => -- direct (uncached) access request
      -- ------------------------------------------------------------
        bus_req_o        <= host_req_i; -- pass-through (cache bypass)
        bus_req_o.stb    <= '1';
        ctrl_nxt.buf_req <= '0'; -- access (about to be) completed
        ctrl_nxt.state   <= S_DIRECT_RSP;
--     -- update cache if accessed address is cached --
--     [NOTE] not implemented: this would make atomic memory access / memory coherence even more difficult to understand
--     if (cache_i.sta_hit = '1') and (host_req_i.rw = '1') and (READ_ONLY = false) then -- cache write hit
--       cache_o.we <= host_req_i.ben;
--     end if;

      when S_DIRECT_RSP => -- wait for direct (uncached) access response
      -- ------------------------------------------------------------
        bus_req_o     <= host_req_i; -- pass-through (cache bypass)
        bus_req_o.stb <= '0';
        host_rsp_o    <= bus_rsp_i; -- pass-through (cache bypass)
        if (bus_rsp_i.ack = '1') or (bus_rsp_i.err = '1') then
          ctrl_nxt.state <= S_IDLE;
        end if;
--     -- update cache if accessed address is cached --
--     [NOTE] not implemented: this would make atomic memory access / memory coherence even more difficult to understand
--     cache_o.data <= bus_rsp_i.data;
--     if (cache_i.sta_hit = '1') and (host_req_i.rw = '0') and (bus_rsp_i.ack = '1') then -- cache read hit
--       cache_o.we <= (others => '1');
--     end if;


      when S_DOWNLOAD_REQ => -- download new cache block: request new word
      -- ------------------------------------------------------------
        cache_o.addr   <= addr.tag & addr.idx & addr.ofs & "00";
        cache_o.data   <= bus_rsp_i.data;
        bus_req_o.rw   <= '0'; -- read access
        bus_req_o.stb  <= '1'; -- request new transfer
        ctrl_nxt.state <= S_DOWNLOAD_RSP;

      when S_DOWNLOAD_RSP => -- download new cache block: wait for bus response
      -- ------------------------------------------------------------
        cache_o.addr    <= addr.tag & addr.idx & addr.ofs & "00";
        cache_o.data    <= bus_rsp_i.data;
        cache_o.cmd_new <= '1'; -- set new block (set tag, make valid & clean)
        bus_req_o.rw    <= '0'; -- read access
        --
        if (bus_rsp_i.err = '1') then --
          ctrl_nxt.state <= S_DOWNLOAD_ERR;
        elsif (bus_rsp_i.ack = '1') then
          cache_o.we   <= (others => '1'); -- cache: full-word write
          addr_nxt.ofs <= std_ulogic_vector(unsigned(addr.ofs) + 1);
          if (and_reduce_f(addr.ofs) = '1') then -- block completed
            ctrl_nxt.state <= S_DOWNLOAD_DONE;
          else -- get next word
            ctrl_nxt.state <= S_DOWNLOAD_REQ;
          end if;
        end if;

      when S_DOWNLOAD_DONE => -- delay cycle for update of cache status
      -- ------------------------------------------------------------
        ctrl_nxt.state <= S_LOOKUP;

      when S_DOWNLOAD_ERR => -- error during block download
      -- ------------------------------------------------------------
        cache_o.cmd_inv <= '1'; -- this block in broken
        ctrl_nxt.state  <= S_ERROR;


      when S_UPLOAD_GET => -- upload dirty cache block: read word from cache
      -- ------------------------------------------------------------
        if (READ_ONLY = true) then
          ctrl_nxt.state <= S_IDLE;
        else
          cache_o.addr   <= addr.tag & addr.idx & addr.ofs & "00";
          bus_req_o.rw   <= '1'; -- write access
          ctrl_nxt.state <= S_UPLOAD_REQ;
        end if;

      when S_UPLOAD_REQ => -- upload dirty cache block: request bus write
      -- ------------------------------------------------------------
        if (READ_ONLY = true) then
          ctrl_nxt.state <= S_IDLE;
        else
          cache_o.addr   <= addr.tag & addr.idx & addr.ofs & "00";
          bus_req_o.rw   <= '1'; -- write access
          bus_req_o.stb  <= '1'; -- request new transfer
          ctrl_nxt.state <= S_UPLOAD_RSP;
        end if;

      when S_UPLOAD_RSP => -- upload dirty cache block: wait for bus response
      -- ------------------------------------------------------------
        if (READ_ONLY = true) then
          ctrl_nxt.state <= S_IDLE;
        else
          cache_o.addr    <= addr.tag & addr.idx & addr.ofs & "00";
          bus_req_o.rw    <= '1'; -- write access
          cache_o.cmd_new <= '1'; -- set new block (set tag, make valid & clean)
          if (bus_rsp_i.err = '1') then -- bus error (this is really bad...)
            ctrl_nxt.state <= S_ERROR;
          elsif (bus_rsp_i.ack = '1') then
            addr_nxt.ofs <= std_ulogic_vector(unsigned(addr.ofs) + 1);
            if (and_reduce_f(addr.ofs) = '1') then -- block completed
              ctrl_nxt.state <= ctrl.stret; -- go back to "upload-done return state"
            else -- get next word
              ctrl_nxt.state <= S_UPLOAD_GET;
            end if;
          end if;
        end if;


      when S_FLUSH_START => -- start checking for dirty blocks
      -- ------------------------------------------------------------
        cache_o.addr   <= addr.tag & addr.idx & addr.ofs & "00";
        addr_nxt.idx   <= (others => '0'); -- start with index 0
        ctrl_nxt.stret <= S_FLUSH_READ; -- go back to S_FLUSH_READ after block UPLOAD
        ctrl_nxt.state <= S_FLUSH_READ;

      when S_FLUSH_READ => -- cache read access latency cycle
      -- ------------------------------------------------------------
        cache_o.addr   <= addr.tag & addr.idx & addr.ofs & "00";
        ctrl_nxt.state <= S_FLUSH_CHECK;

      when S_FLUSH_CHECK => -- check if currently indexed block is dirty
      -- ------------------------------------------------------------
        cache_o.addr    <= addr.tag & addr.idx & addr.ofs & "00";
        addr_nxt.tag    <= cache_i.sta_tag(31 downto 32-tag_size_c); -- tag of currently index block
        cache_o.cmd_inv <= '1'; -- invalidate currently indexed block
        --
        if (cache_i.sta_dir = '1') and (READ_ONLY = false) then -- block dirty?
          ctrl_nxt.state <= S_UPLOAD_GET;
        else -- move on to next block
          addr_nxt.idx <= std_ulogic_vector(unsigned(addr.idx) + 1);
          if (and_reduce_f(addr.idx) = '1') then -- all blocks done
            ctrl_nxt.state <= S_FLUSH_DONE;
          else -- go to next block
            ctrl_nxt.state <= S_FLUSH_READ;
          end if;
        end if;

      when S_FLUSH_DONE => -- flush completed
      -- ------------------------------------------------------------
        if not READ_ONLY then
          bus_req_o.fence <= '1'; -- forward fence request
        end if;
        ctrl_nxt.buf_sync <= '0'; -- sync completed
        ctrl_nxt.state    <= S_IDLE;


      when S_ERROR => -- block operation error
      -- ------------------------------------------------------------
        host_rsp_o.err <= '1';
        ctrl_nxt.state <= S_IDLE;

      when others => -- undefined
      -- ------------------------------------------------------------
        ctrl_nxt.state <= S_IDLE;

    end case;
  end process ctrl_engine_comb;


  -- Cache Memory Core (Cache Storage and Status Management) --------------------------------
  -- -------------------------------------------------------------------------------------------
  neorv32_cache_memory_inst: neorv32_cache_memory
  generic map (
    NUM_BLOCKS => block_num_c,  -- number of blocks (min 2), has to be a power of 2
    BLOCK_SIZE => block_size_c, -- block size in bytes (min 4), has to be a power of 2
    READ_ONLY  => READ_ONLY     -- cache is read-only (for host)
  )
  port map (
    -- global control --
    rstn_i  => rstn_i,          -- global reset, async, low-active
    clk_i   => clk_i,           -- global clock, rising edge
    -- management --
    inval_i => cache_o.cmd_inv, -- make accessed block invalid
    new_i   => cache_o.cmd_new, -- make accessed block valid, clean and set tag
    dirty_i => cache_o.cmd_dir, -- make accessed block dirty
    -- status --
    hit_o   => cache_i.sta_hit, -- cache hit
    dirty_o => cache_i.sta_dir, -- accessed block is dirty
    tag_o   => cache_i.sta_tag, -- tag of current block (MSB-aligned)
    clean_o => cache_i.sta_cln, -- cache is clean (global status)
    -- cache access --
    addr_i  => cache_o.addr,    -- access address
    we_i    => cache_o.we,      -- byte-wide data write enable
    wdata_i => cache_o.data,    -- write data
    rdata_o => cache_i.data     -- read data
  );

end neorv32_cache_rtl;


-- ================================================================================ --
-- NEORV32 SoC - Generic Cache: Data and Status Memory (direct-mapped)              --
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

entity neorv32_cache_memory is
  generic (
    NUM_BLOCKS : natural; -- number of blocks (min 2), has to be a power of 2
    BLOCK_SIZE : natural; -- block size in bytes (min 4), has to be a power of 2
    READ_ONLY  : boolean  -- cache is read-only (for host)
  );
  port (
    -- global control --
    rstn_i  : in  std_ulogic;                     -- global reset, async, low-active
    clk_i   : in  std_ulogic;                     -- global clock, rising edge
    -- management --
    inval_i : in  std_ulogic;                     -- make accessed block invalid
    new_i   : in  std_ulogic;                     -- make accessed block valid, clean and set tag
    dirty_i : in  std_ulogic;                     -- make accessed block dirty
    -- status --
    hit_o   : out std_ulogic;                     -- cache hit
    dirty_o : out std_ulogic;                     -- accessed block is dirty
    tag_o   : out std_ulogic_vector(31 downto 0); -- tag of current block (MSB-aligned)
    clean_o : out std_ulogic;                     -- cache is clean (global status)
    -- cache access --
    addr_i  : in  std_ulogic_vector(31 downto 0); -- access address
    we_i    : in  std_ulogic_vector(3 downto 0);  -- byte-wide data write enable
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0)  -- read data
  );
end neorv32_cache_memory;

architecture neorv32_cache_memory_rtl of neorv32_cache_memory is

  -- cache layout --
  constant offset_size_c : natural := index_size_f(BLOCK_SIZE/4); -- offset addresses full 32-bit words
  constant index_size_c  : natural := index_size_f(NUM_BLOCKS); -- index size
  constant tag_size_c    : natural := 32 - (offset_size_c + index_size_c + 2); -- 2 additional bits for byte offset

  -- status flag memory --
  signal valid_mem, dirty_mem : std_ulogic_vector(NUM_BLOCKS-1 downto 0);
  signal valid_mem_rd, dirty_mem_rd : std_ulogic;

  -- tag memory --
  type tag_mem_t is array (0 to NUM_BLOCKS-1) of std_ulogic_vector(tag_size_c-1 downto 0);
  signal tag_mem : tag_mem_t;
  signal tag_mem_rd : std_ulogic_vector(tag_size_c-1 downto 0);

  -- cache data memory --
  type data_mem_t is array (0 to (NUM_BLOCKS * (BLOCK_SIZE/4))-1) of std_ulogic_vector(7 downto 0);
  signal data_mem_b0, data_mem_b1, data_mem_b2, data_mem_b3 : data_mem_t; -- byte-wide sub-memories

  -- access address decomposition --
  signal acc_tag : std_ulogic_vector(tag_size_c-1 downto 0);
  signal acc_idx : std_ulogic_vector(index_size_c-1 downto 0);
  signal acc_off : std_ulogic_vector(offset_size_c-1 downto 0);
  signal acc_adr : std_ulogic_vector((index_size_c+offset_size_c)-1 downto 0);

begin

  -- Access Address Decomposition -----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  acc_tag <= addr_i(31 downto 31-(tag_size_c-1));
  acc_idx <= addr_i(31-tag_size_c downto 2+offset_size_c);
  acc_off <= addr_i(2+(offset_size_c-1) downto 2);
  acc_adr <= acc_idx & acc_off;


  -- Status Flag Memory ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  status_memory: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      valid_mem    <= (others => '0');
      dirty_mem    <= (others => '0');
      valid_mem_rd <= '0';
      dirty_mem_rd <= '0';
    elsif rising_edge(clk_i) then
      if (new_i = '1') then -- set new block
        valid_mem(to_integer(unsigned(acc_idx))) <= '1'; -- valid
        dirty_mem(to_integer(unsigned(acc_idx))) <= '0'; -- clean
      else
        if (inval_i = '1') then -- invalidate current block
          valid_mem(to_integer(unsigned(acc_idx))) <= '0';
        end if;
        if (dirty_i = '1') and (READ_ONLY = false) then -- make current block dirty
          dirty_mem(to_integer(unsigned(acc_idx))) <= '1';
        end if;
      end if;
      -- sync read --
      valid_mem_rd <= valid_mem(to_integer(unsigned(acc_idx)));
      dirty_mem_rd <= dirty_mem(to_integer(unsigned(acc_idx)));
    end if;
  end process status_memory;


  -- Tag Memory -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tag_memory: process(clk_i) -- no reset to allow inferring of blockRAM
  begin
    if rising_edge(clk_i) then
      if (new_i = '1') then -- set new cache entry
        tag_mem(to_integer(unsigned(acc_idx))) <= acc_tag;
      end if;
      tag_mem_rd <= tag_mem(to_integer(unsigned(acc_idx)));
    end if;
  end process tag_memory;

  -- tag of accessed block --
  tag_o(31 downto 31-(tag_size_c-1)) <= tag_mem_rd;
  tag_o(31-tag_size_c downto 0) <= (others => '0');


  -- Access Status (1 Cycle Latency) --------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  hit_o   <= '1' when (valid_mem_rd = '1') and (tag_mem_rd = acc_tag) else '0'; -- cache access hit
  dirty_o <= '1' when (valid_mem_rd = '1') and (dirty_mem_rd = '1') and (READ_ONLY = false) else '0'; -- block is dirty

  -- cache is clean if all blocks are invalid --
  clean_read_only:
  if READ_ONLY generate
    clean_o <= '1' when (or_reduce_f(valid_mem) = '0') else '0';
  end generate;

  -- cache is clean if all valid blocks are clean --
  clean_read_write:
  if not READ_ONLY generate
    clean_o <= '1' when (or_reduce_f(valid_mem and dirty_mem) = '0') else '0';
  end generate;


  -- Cache Data Memory ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cache_mem_access: process(clk_i) -- no reset to allow inferring of blockRAM
  begin
    if rising_edge(clk_i) then
      -- write access --
      if (we_i(0) = '1') then
        data_mem_b0(to_integer(unsigned(acc_adr))) <= wdata_i(7 downto 0);
      end if;
      if (we_i(1) = '1') then
        data_mem_b1(to_integer(unsigned(acc_adr))) <= wdata_i(15 downto 8);
      end if;
      if (we_i(2) = '1') then
        data_mem_b2(to_integer(unsigned(acc_adr))) <= wdata_i(23 downto 16);
      end if;
      if (we_i(3) = '1') then
        data_mem_b3(to_integer(unsigned(acc_adr))) <= wdata_i(31 downto 24);
      end if;
      -- read access --
      rdata_o(7 downto 0)   <= data_mem_b0(to_integer(unsigned(acc_adr)));
      rdata_o(15 downto 8)  <= data_mem_b1(to_integer(unsigned(acc_adr)));
      rdata_o(23 downto 16) <= data_mem_b2(to_integer(unsigned(acc_adr)));
      rdata_o(31 downto 24) <= data_mem_b3(to_integer(unsigned(acc_adr)));
    end if;
  end process cache_mem_access;


end neorv32_cache_memory_rtl;
