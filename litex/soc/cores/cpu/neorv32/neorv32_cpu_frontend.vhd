-- ================================================================================ --
-- NEORV32 CPU - Front End (Instruction Fetch)                                      --
-- -------------------------------------------------------------------------------- --
-- + Fetch engine:    Fetches aligned 32-bit chunks of instruction words            --
-- + Prefetch buffer: Buffers pre-fetched 32-bit instruction data                   --
-- + Issue engine:    Decodes RVC instructions, aligns & issues instruction words   --
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

entity neorv32_cpu_frontend is
  generic (
    HART_ID   : natural; -- hardware thread ID
    RISCV_C   : boolean; -- implement C ISA extension
    RISCV_ZCB : boolean  -- implement Zcb ISA sub-extension
  );
  port (
    -- global control --
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    ctrl_i     : in  ctrl_bus_t; -- main control bus
    -- instruction fetch interface --
    ibus_req_o : out bus_req_t; -- request
    ibus_rsp_i : in  bus_rsp_t; -- response
    -- PMP interface --
    pmp_addr_o : out std_ulogic_vector(31 downto 0); -- access address
    pmp_priv_o : out std_ulogic; -- access privilege level
    pmp_err_i  : in  std_ulogic; -- PMP access fault
    -- back-end interface --
    frontend_o : out if_bus_t -- fetch data and status
  );
end neorv32_cpu_frontend;

architecture neorv32_cpu_frontend_rtl of neorv32_cpu_frontend is

  -- instruction prefetch buffer --
  component neorv32_cpu_frontend_ipb
  generic (
    AWIDTH : natural;
    DWIDTH : natural
  );
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    clear_i : in  std_ulogic;
    wdata_i : in  std_ulogic_vector(DWIDTH-1 downto 0);
    we_i    : in  std_ulogic;
    free_o  : out std_ulogic;
    re_i    : in  std_ulogic;
    rdata_o : out std_ulogic_vector(DWIDTH-1 downto 0);
    avail_o : out std_ulogic
  );
  end component;

  -- instruction fetch engine --
  type state_t is (S_RESTART, S_REQUEST, S_PENDING);
  type fetch_t is record
    state : state_t;
    reset : std_ulogic; -- buffered restart request (after branch)
    addr  : std_ulogic_vector(31 downto 0); -- fetch address
    priv  : std_ulogic; -- fetch privilege level
    debug : std_ulogic; -- debug-mode access
  end record;
  signal fetch : fetch_t;

  -- reset instruction fetch after branch --
  signal restart : std_ulogic;

  -- instruction prefetch buffer (FIFO) interface --
  type ipb_data_t is array (0 to 1) of std_ulogic_vector(16 downto 0); -- bus_error & 16-bit instruction
  type ipb_t is record
    wdata, rdata : ipb_data_t;
    we,    re    : std_ulogic_vector(1 downto 0);
    free,  avail : std_ulogic_vector(1 downto 0);
  end record;
  signal ipb : ipb_t;

  -- instruction issue engine --
  signal align_q, align_set, align_clr : std_ulogic;
  signal issue_valid : std_ulogic_vector(1 downto 0);
  signal cmd16 : std_ulogic_vector(15 downto 0);
  signal cmd32 : std_ulogic_vector(31 downto 0);

begin

  -- ******************************************************************************************************************
  -- Instruction Fetch (always fetch 32-bit-aligned 32-bit chunks of data)
  -- ******************************************************************************************************************

  -- Fetch Engine FSM -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  fetch_fsm: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      fetch.state <= S_RESTART;
      fetch.reset <= '1'; -- reset IPB and issue engine
      fetch.addr  <= (others => '0');
      fetch.priv  <= priv_mode_m_c;
      fetch.debug <= '0';
    elsif rising_edge(clk_i) then
      case fetch.state is

        when S_RESTART => -- set new start address
        -- ------------------------------------------------------------
          fetch.reset <= '0'; -- restart done
          fetch.addr  <= ctrl_i.pc_nxt; -- initialize from PC
          fetch.priv  <= ctrl_i.cpu_priv; -- set new privilege level
          fetch.debug <= ctrl_i.cpu_debug; -- access from debug-mode
          fetch.state <= S_REQUEST;

        when S_REQUEST => -- request next 32-bit-aligned instruction word
        -- ------------------------------------------------------------
          fetch.reset <= restart; -- buffer restart request
          if (ipb.free = "11") then -- free IPB space?
            fetch.state <= S_PENDING;
          elsif (restart = '1') then -- restart request due to branch
            fetch.state <= S_RESTART;
          end if;

        when S_PENDING => -- wait for bus response and write instruction data to prefetch buffer
        -- ------------------------------------------------------------
          fetch.reset <= restart; -- buffer restart request
          if (ibus_rsp_i.ack = '1') then -- wait for bus response
            fetch.addr    <= std_ulogic_vector(unsigned(fetch.addr) + 4); -- next word
            fetch.addr(1) <= '0'; -- (re-)align to 32-bit
            if (restart = '1') then -- restart request due to branch
              fetch.state <= S_RESTART;
            else -- request next linear instruction word
              fetch.state <= S_REQUEST;
            end if;
          end if;

        when others => -- undefined
        -- ------------------------------------------------------------
          fetch.state <= S_RESTART;

      end case;
    end if;
  end process fetch_fsm;

  -- reset instruction fetch after branch --
  restart <= fetch.reset or ctrl_i.if_reset;

  -- PMP interface --
  pmp_addr_o <= fetch.addr(31 downto 2) & "00"; -- word aligned
  pmp_priv_o <= fetch.priv;

  -- instruction bus request --
  ibus_req_o.meta  <= std_ulogic_vector(to_unsigned(HART_ID, 2)) & fetch.debug & fetch.priv & '1';
  ibus_req_o.addr  <= fetch.addr(31 downto 2) & "00"; -- word aligned
  ibus_req_o.stb   <= '1' when (fetch.state = S_REQUEST) and (ipb.free = "11") else '0';
  ibus_req_o.data  <= (others => '0');  -- read-only
  ibus_req_o.ben   <= (others => '1');  -- always full-word access
  ibus_req_o.rw    <= '0';              -- read-only
  ibus_req_o.amo   <= '0';              -- cannot be an atomic memory operation
  ibus_req_o.amoop <= (others => '0');  -- cannot be an atomic memory operation
  ibus_req_o.burst <= '0';              -- only single-access
  ibus_req_o.lock  <= '0';              -- always unlocked access
  ibus_req_o.fence <= ctrl_i.if_fence;  -- fence request, valid without STB being set ("out-of-band" signal)

  -- IPB instruction data and status --
  ipb.wdata(0) <= (ibus_rsp_i.err or pmp_err_i) & ibus_rsp_i.data(15 downto 0);
  ipb.wdata(1) <= (ibus_rsp_i.err or pmp_err_i) & ibus_rsp_i.data(31 downto 16);

  -- IPB write enable --
  ipb.we(0) <= '1' when (fetch.state = S_PENDING) and (ibus_rsp_i.ack = '1') and ((fetch.addr(1) = '0') or (not RISCV_C)) else '0';
  ipb.we(1) <= '1' when (fetch.state = S_PENDING) and (ibus_rsp_i.ack = '1') else '0';


  -- Instruction Prefetch Buffer (FIFO) -----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  prefetch_buffer:
  for i in 0 to 1 generate
    ipb_inst: neorv32_cpu_frontend_ipb
    generic map (
      AWIDTH => 1, -- 1 address bit = 2 entries
      DWIDTH => 17 -- error status & instruction half-word data
    )
    port map (
      -- global control --
      clk_i   => clk_i,        -- clock, rising edge
      rstn_i  => rstn_i,       -- async reset, low-active
      clear_i => restart,      -- sync reset, high-active
      -- write port --
      wdata_i => ipb.wdata(i), -- write data
      we_i    => ipb.we(i),    -- write enable
      free_o  => ipb.free(i),  -- at least one entry is free when set
      -- read port --
      re_i    => ipb.re(i),    -- read enable
      rdata_o => ipb.rdata(i), -- read data
      avail_o => ipb.avail(i)  -- data available when set
    );
  end generate;


  -- ******************************************************************************************************************
  -- Instruction Issue (decompress 16-bit instruction and/or assemble a 32-bit instruction word)
  -- ******************************************************************************************************************

  issue_enabled:
  if RISCV_C generate

    -- Compressed Instructions Decoder --------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_cpu_decompressor_inst: entity neorv32.neorv32_cpu_decompressor
    generic map (
      ZCB_EN => RISCV_ZCB
    )
    port map (
      instr_i => cmd16,
      instr_o => cmd32
    );

    -- half-word select --
    cmd16 <= ipb.rdata(0)(15 downto 0) when (align_q = '0') else ipb.rdata(1)(15 downto 0);


    -- Issue Engine FSM -----------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    issue_fsm_sync: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        align_q <= '0'; -- start aligned after reset
      elsif rising_edge(clk_i) then
        if (fetch.reset = '1') then
          align_q <= ctrl_i.pc_nxt(1); -- branch to unaligned address?
        elsif (ipb.re(0) = '1') or (ipb.re(1) = '1') then
          align_q <= (align_q and (not align_clr)) or align_set; -- alignment "RS flip-flop"
        end if;
      end if;
    end process issue_fsm_sync;

    issue_fsm_comb: process(align_q, ipb, cmd32)
    begin
      -- defaults --
      align_set <= '0';
      align_clr <= '0';
      -- start at LOW half-word --
      if (align_q = '0') then
        if (ipb.rdata(0)(1 downto 0) /= "11") then -- compressed, consume IPB(0) entry
          align_set        <= ipb.avail(0); -- start of next instruction word is NOT 32-bit-aligned
          issue_valid(0)   <= ipb.avail(0);
          issue_valid(1)   <= '0';
          frontend_o.fault <= ipb.rdata(0)(16);
          frontend_o.instr <= cmd32;
          frontend_o.compr <= '1';
        else -- aligned uncompressed, consume both IPB entries
          issue_valid(0)   <= ipb.avail(1) and ipb.avail(0);
          issue_valid(1)   <= ipb.avail(1) and ipb.avail(0);
          frontend_o.fault <= ipb.rdata(1)(16) or ipb.rdata(0)(16);
          frontend_o.instr <= ipb.rdata(1)(15 downto 0) & ipb.rdata(0)(15 downto 0);
          frontend_o.compr <= '0';
        end if;
      -- start at HIGH half-word --
      else
        if (ipb.rdata(1)(1 downto 0) /= "11") then -- compressed, consume IPB(1) entry
          align_clr        <= ipb.avail(1); -- start of next instruction word is 32-bit-aligned again
          issue_valid(0)   <= '0';
          issue_valid(1)   <= ipb.avail(1);
          frontend_o.fault <= ipb.rdata(1)(16);
          frontend_o.instr <= cmd32;
          frontend_o.compr <= '1';
        else -- unaligned uncompressed, consume both IPB entries
          issue_valid(0)   <= ipb.avail(0) and ipb.avail(1);
          issue_valid(1)   <= ipb.avail(0) and ipb.avail(1);
          frontend_o.fault <= ipb.rdata(0)(16) or ipb.rdata(1)(16);
          frontend_o.instr <= ipb.rdata(0)(15 downto 0) & ipb.rdata(1)(15 downto 0);
          frontend_o.compr <= '0';
        end if;
      end if;
    end process issue_fsm_comb;

    -- issue valid instruction word to execution stage --
    frontend_o.valid <= issue_valid(1) or issue_valid(0);

    -- IPB read access --
    ipb.re(0) <= issue_valid(0) and ctrl_i.if_ready;
    ipb.re(1) <= issue_valid(1) and ctrl_i.if_ready;

  end generate; -- /issue_enabled

  -- issue engine disabled --
  issue_disabled:
  if not RISCV_C generate
    align_q          <= '0';
    align_set        <= '0';
    align_clr        <= '0';
    issue_valid      <= (others => '0');
    cmd16            <= (others => '0');
    cmd32            <= (others => '0');
    ipb.re           <= (others => (ctrl_i.if_ready and ipb.avail(0)));
    frontend_o.valid <= ipb.avail(0);
    frontend_o.instr <= ipb.rdata(1)(15 downto 0) & ipb.rdata(0)(15 downto 0);
    frontend_o.compr <= '0';
    frontend_o.fault <= ipb.rdata(0)(16);
  end generate;

end neorv32_cpu_frontend_rtl;


-- ================================================================================ --
-- NEORV32 CPU - Instruction Prefetch Buffer                                        --
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

entity neorv32_cpu_frontend_ipb is
  generic (
    AWIDTH : natural; -- address width
    DWIDTH : natural  -- data width
  );
  port (
    -- global control --
    clk_i   : in  std_ulogic; -- clock, rising edge
    rstn_i  : in  std_ulogic; -- async reset, low-active
    clear_i : in  std_ulogic; -- sync reset, high-active
    -- write port --
    wdata_i : in  std_ulogic_vector(DWIDTH-1 downto 0); -- write data
    we_i    : in  std_ulogic; -- write enable
    free_o  : out std_ulogic; -- at least one entry is free when set
    -- read port --
    re_i    : in  std_ulogic; -- read enable
    rdata_o : out std_ulogic_vector(DWIDTH-1 downto 0); -- read data
    avail_o : out std_ulogic  -- data available when set
  );
end neorv32_cpu_frontend_ipb;

architecture neorv32_cpu_frontend_ipb_rtl of neorv32_cpu_frontend_ipb is

  -- pointers and status --
  signal w_pnt, r_pnt : std_ulogic_vector(AWIDTH downto 0);
  signal match : std_ulogic;

  -- memory core --
  type ipb_t is array (0 to (2**AWIDTH)-1) of std_ulogic_vector(DWIDTH-1 downto 0);
  signal ipb : ipb_t;

begin

  -- Pointers -------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  pointer_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      w_pnt <= (others => '0');
      r_pnt <= (others => '0');
    elsif rising_edge(clk_i) then
      if (clear_i = '1') then
        w_pnt <= (others => '0');
      elsif (we_i = '1') then
        w_pnt <= std_ulogic_vector(unsigned(w_pnt) + 1);
      end if;
      if (clear_i = '1') then
        r_pnt <= (others => '0');
      elsif (re_i = '1') then
        r_pnt <= std_ulogic_vector(unsigned(r_pnt) + 1);
      end if;
    end if;
  end process pointer_reg;

  -- status --
  match   <= '1' when (r_pnt(AWIDTH-1 downto 0) = w_pnt(AWIDTH-1 downto 0)) else '0';
  free_o  <= '0' when (r_pnt(AWIDTH) /= w_pnt(AWIDTH)) and (match = '1') else '1';
  avail_o <= '0' when (r_pnt(AWIDTH)  = w_pnt(AWIDTH)) and (match = '1') else '1';

  -- Memory Core ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  mem_write: process(clk_i)
  begin
    if rising_edge(clk_i) then
      if (we_i = '1') then
        ipb(to_integer(unsigned(w_pnt(AWIDTH-1 downto 0)))) <= wdata_i;
      end if;
    end if;
  end process mem_write;

  -- asynchronous(!) read --
  rdata_o <= ipb(to_integer(unsigned(r_pnt(AWIDTH-1 downto 0))));

end neorv32_cpu_frontend_ipb_rtl;
