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
    RVC_EN : boolean -- implement compressed extension
  );
  port (
    -- global control --
    clk_i      : in  std_ulogic; -- global clock, rising edge
    rstn_i     : in  std_ulogic; -- global reset, low-active, async
    ctrl_i     : in  ctrl_bus_t; -- main control bus
    -- instruction fetch interface --
    ibus_req_o : out bus_req_t; -- request
    ibus_rsp_i : in  bus_rsp_t; -- response
    -- back-end interface --
    frontend_o : out if_bus_t
  );
end neorv32_cpu_frontend;

architecture neorv32_cpu_frontend_rtl of neorv32_cpu_frontend is

  -- instruction fetch engine --
  type fetch_state_t is (S_RESTART, S_REQUEST, S_PENDING);
  type fetch_t is record
    state   : fetch_state_t;
    restart : std_ulogic; -- buffered restart request (after branch)
    pc      : std_ulogic_vector(XLEN-1 downto 0);
    resp    : std_ulogic; -- bus response
    priv    : std_ulogic; -- fetch privilege level
    halted  : std_ulogic; -- instruction fetch has halted
  end record;
  signal fetch : fetch_t;

  -- instruction prefetch buffer (FIFO) interface --
  type ipb_data_t is array (0 to 1) of std_ulogic_vector(16 downto 0); -- bus_error & 16-bit instruction
  type ipb_t is record
    wdata, rdata : ipb_data_t;
    we,    re    : std_ulogic_vector(1 downto 0);
    free,  avail : std_ulogic_vector(1 downto 0);
  end record;
  signal ipb : ipb_t;

  -- instruction issue engine --
  type issue_t is record
    align : std_ulogic;
    alset : std_ulogic;
    alclr : std_ulogic;
    cmd16 : std_ulogic_vector(15 downto 0);
    cmd32 : std_ulogic_vector(31 downto 0);
    valid : std_ulogic_vector(1 downto 0);
    instr : std_ulogic_vector(31 downto 0);
    compr : std_ulogic;
    error : std_ulogic;
  end record;
  signal issue : issue_t;

begin

  -- ******************************************************************************************************************
  -- Instruction Fetch (always fetch 32-bit-aligned 32-bit chunks of data)
  -- ******************************************************************************************************************

  -- Fetch Engine FSM -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  fetch_fsm: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      fetch.state   <= S_RESTART;
      fetch.restart <= '1'; -- reset IPB and issue engine
      fetch.pc      <= (others => '0');
      fetch.priv    <= priv_mode_m_c;
    elsif rising_edge(clk_i) then
      case fetch.state is

        when S_REQUEST => -- request next 32-bit-aligned instruction word
        -- ------------------------------------------------------------
          fetch.restart <= fetch.restart or ctrl_i.if_reset; -- buffer restart request
          if (ipb.free = "11") then -- free IPB space?
            fetch.state <= S_PENDING;
          elsif (fetch.restart = '1') or (ctrl_i.if_reset = '1') then -- restart because of branch
            fetch.state <= S_RESTART;
          end if;

        when S_PENDING => -- wait for bus response and write instruction data to prefetch buffer
        -- ------------------------------------------------------------
          fetch.restart <= fetch.restart or ctrl_i.if_reset; -- buffer restart request
          if (fetch.resp = '1') then -- wait for bus response
            fetch.pc    <= std_ulogic_vector(unsigned(fetch.pc) + 4); -- next word
            fetch.pc(1) <= '0'; -- (re-)align to 32-bit
            if (fetch.restart = '1') or (ctrl_i.if_reset = '1') then -- restart request due to branch
              fetch.state <= S_RESTART;
            else -- request next linear instruction word
              fetch.state <= S_REQUEST;
            end if;
          end if;

        when others => -- S_RESTART: set new start address
        -- ------------------------------------------------------------
          fetch.restart <= '0'; -- restart done
          fetch.pc      <= ctrl_i.pc_nxt; -- initialize from PC
          fetch.priv    <= ctrl_i.cpu_priv; -- set new privilege level
          fetch.state   <= S_REQUEST;

      end case;
    end if;
  end process fetch_fsm;

  -- PC output for instruction fetch --
  ibus_req_o.addr <= fetch.pc(XLEN-1 downto 2) & "00"; -- word aligned

  -- instruction fetch (read) request if IPB not full --
  ibus_req_o.stb <= '1' when (fetch.state = S_REQUEST) and (ipb.free = "11") else '0';

  -- instruction bus response --
  fetch.resp <= ibus_rsp_i.ack or ibus_rsp_i.err;

  -- IPB instruction data and status --
  ipb.wdata(0) <= ibus_rsp_i.err & ibus_rsp_i.data(15 downto 0);
  ipb.wdata(1) <= ibus_rsp_i.err & ibus_rsp_i.data(31 downto 16);

  -- IPB write enable --
  ipb.we(0) <= '1' when (fetch.state = S_PENDING) and (fetch.resp = '1') and ((fetch.pc(1) = '0') or (not RVC_EN)) else '0';
  ipb.we(1) <= '1' when (fetch.state = S_PENDING) and (fetch.resp = '1') else '0';

  -- instruction fetch has halted --
  fetch.halted <= '1' when (fetch.state = S_REQUEST) and (ipb.free /= "11") else '0';

  -- bus access meta data --
  ibus_req_o.data  <= (others => '0');  -- read-only
  ibus_req_o.ben   <= (others => '0');  -- read-only
  ibus_req_o.rw    <= '0';              -- read-only
  ibus_req_o.src   <= '1';              -- always "instruction fetch" access
  ibus_req_o.priv  <= fetch.priv;       -- current effective privilege level
  ibus_req_o.debug <= ctrl_i.cpu_debug; -- CPU is in debug mode
  ibus_req_o.amo   <= '0';              -- cannot be an atomic memory operation
  ibus_req_o.amoop <= (others => '0');  -- cannot be an atomic memory operation
  ibus_req_o.fence <= ctrl_i.if_fence;  -- fence request, valid without STB being set ("out-of-band" signal)


  -- Instruction Prefetch Buffer (FIFO) -----------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  prefetch_buffer:
  for i in 0 to 1 generate -- low half-word + high half-word (incl. status bits)
    prefetch_buffer_inst: entity neorv32.neorv32_fifo
    generic map (
      FIFO_DEPTH => 2,     -- number of IPB entries; has to be a power of two, min 2
      FIFO_WIDTH => 17,    -- size of data elements in FIFO
      FIFO_RSYNC => false, -- we NEED to read data asynchronously
      FIFO_SAFE  => false, -- no safe access required (ensured by FIFO-external logic)
      FULL_RESET => false  -- no need for a full hardware reset
    )
    port map (
      -- control and status --
      clk_i   => clk_i,         -- clock, rising edge
      rstn_i  => rstn_i,        -- async reset, low-active
      clear_i => fetch.restart, -- sync reset, high-active
      half_o  => open,          -- at least half full
      level_o => open,          -- fill level, zero-extended
      -- write port --
      wdata_i => ipb.wdata(i),  -- write data
      we_i    => ipb.we(i),     -- write enable
      free_o  => ipb.free(i),   -- at least one entry is free when set
      -- read port --
      re_i    => ipb.re(i),     -- read enable
      rdata_o => ipb.rdata(i),  -- read data
      avail_o => ipb.avail(i)   -- data available when set
    );
  end generate;

  -- read access --
  ipb.re(0) <= issue.valid(0) and ctrl_i.if_ack;
  ipb.re(1) <= issue.valid(1) and ctrl_i.if_ack;


  -- ******************************************************************************************************************
  -- Instruction Issue (decompress 16-bit instruction and/or assemble a 32-bit instruction word)
  -- ******************************************************************************************************************

  issue_enabled:
  if RVC_EN generate

    -- Compressed Instructions Decoder --------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    neorv32_cpu_decompressor_inst: entity neorv32.neorv32_cpu_decompressor
    port map (
      instr_i => issue.cmd16,
      instr_o => issue.cmd32
    );

    -- half-word select --
    issue.cmd16 <= ipb.rdata(0)(15 downto 0) when (issue.align = '0') else ipb.rdata(1)(15 downto 0);


    -- Issue Engine FSM -----------------------------------------------------------------------
    -- -------------------------------------------------------------------------------------------
    issue_fsm_sync: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        issue.align <= '0'; -- start aligned after reset
      elsif rising_edge(clk_i) then
        if (fetch.restart = '1') then
          issue.align <= ctrl_i.pc_nxt(1); -- branch to unaligned address?
        elsif (ctrl_i.if_ack = '1') then
          issue.align <= (issue.align and (not issue.alclr)) or issue.alset; -- "rs flip-flop"
        end if;
      end if;
    end process issue_fsm_sync;

    issue_fsm_comb: process(issue, ipb)
    begin
      -- defaults --
      issue.alset <= '0';
      issue.alclr <= '0';
      issue.valid <= "00";
      -- start with LOW half-word --
      if (issue.align = '0')  then
        issue.error <= ipb.rdata(0)(16);
        if (ipb.rdata(0)(1 downto 0) /= "11") then -- compressed, use IPB(0) entry
          issue.alset <= ipb.avail(0); -- start of next instruction word is NOT 32-bit-aligned
          issue.valid <= '0' & ipb.avail(0);
          issue.instr <= issue.cmd32;
          issue.compr <= '1';
        else -- aligned uncompressed
          issue.valid <= (others => (ipb.avail(0) and ipb.avail(1)));
          issue.instr <= ipb.rdata(1)(15 downto 0) & ipb.rdata(0)(15 downto 0);
          issue.compr <= '0';
        end if;
      -- start with HIGH half-word --
      else
        issue.error <= ipb.rdata(1)(16);
        if (ipb.rdata(1)(1 downto 0) /= "11") then -- compressed, use IPB(1) entry
          issue.alclr <= ipb.avail(1); -- start of next instruction word is 32-bit-aligned again
          issue.valid <= ipb.avail(1) & '0';
          issue.instr <= issue.cmd32;
          issue.compr <= '1';
        else -- unaligned uncompressed
          issue.valid <= (others => (ipb.avail(0) and ipb.avail(1)));
          issue.instr <= ipb.rdata(0)(15 downto 0) & ipb.rdata(1)(15 downto 0);
          issue.compr <= '0';
        end if;
      end if;
    end process issue_fsm_comb;

  end generate; -- /issue_enabled


  -- issue engine disabled --
  issue_disabled:
  if not RVC_EN generate
    issue.align <= '0';
    issue.alset <= '0';
    issue.alclr <= '0';
    issue.cmd16 <= (others => '0');
    issue.cmd32 <= (others => '0');
    issue.valid <= (others => ipb.avail(0)); -- use IPB(0) status flags only
    issue.instr <= ipb.rdata(1)(15 downto 0) & ipb.rdata(0)(15 downto 0);
    issue.compr <= '0';
    issue.error <= ipb.rdata(0)(16);
  end generate;


  -- Instruction Interface to CPU Back-End (Execution) --------------------------------------
  -- -------------------------------------------------------------------------------------------
  frontend_o.valid  <= issue.valid(1) or issue.valid(0);
  frontend_o.instr  <= issue.instr;
  frontend_o.compr  <= issue.compr;
  frontend_o.error  <= issue.error;
  frontend_o.halted <= fetch.halted;


end neorv32_cpu_frontend_rtl;
