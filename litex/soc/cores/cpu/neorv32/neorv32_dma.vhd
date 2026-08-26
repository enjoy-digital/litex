-- ================================================================================ --
-- NEORV32 SoC - Direct Memory Access Controller (DMA)                              --
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

entity neorv32_dma is
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;  -- bus request
    bus_rsp_o : out bus_rsp_t;  -- bus response
    dma_req_o : out bus_req_t;  -- DMA request
    dma_rsp_i : in  bus_rsp_t;  -- DMA response
    irq_o     : out std_ulogic  -- transfer done interrupt
  );
end neorv32_dma;

architecture neorv32_dma_rtl of neorv32_dma is

  -- transfer type register bits --
  constant type_num_lo_c  : natural :=  0; -- r/w: Number of elements to transfer, LSB
  constant type_num_hi_c  : natural := 23; -- r/w: Number of elements to transfer, MSB
  --
  constant type_qsel_lo_c : natural := 27; -- r/w: Data quantity select, LSB, see below
  constant type_qsel_hi_c : natural := 28; -- r/w: Data quantity select, MSB, see below
  constant type_src_inc_c : natural := 29; -- r/w: SRC constant (0) or incrementing (1) address
  constant type_dst_inc_c : natural := 30; -- r/w: DST constant (0) or incrementing (1) address
  constant type_endian_c  : natural := 31; -- r/w: Convert Endianness when set

  -- control and status register bits --
  constant ctrl_en_c       : natural :=  0; -- r/w: DMA enable
  constant ctrl_start_c    : natural :=  1; -- -/s: start DMA operation
  --
  constant ctrl_error_rd_c : natural := 28; -- r/-: error during read transfer
  constant ctrl_error_wr_c : natural := 29; -- r/-: error during write transfer
  constant ctrl_done_c     : natural := 30; -- r/c: transfer has completed
  constant ctrl_busy_c     : natural := 31; -- r/-: DMA transfer in progress

  -- transfer quantities --
  constant qsel_b2b_c  : std_ulogic_vector(1 downto 0) := "00"; -- byte to byte
  constant qsel_b2uw_c : std_ulogic_vector(1 downto 0) := "01"; -- byte to unsigned word
  constant qsel_b2sw_c : std_ulogic_vector(1 downto 0) := "10"; -- byte to signed word
  constant qsel_w2w_c  : std_ulogic_vector(1 downto 0) := "11"; -- word to word

  -- configuration registers --
  type cfg_t is record
    enable   : std_ulogic; -- DMA enabled when set
    start    : std_ulogic; -- transfer start trigger
    done     : std_ulogic; -- transfer was executed (but might have failed)
    src_base : std_ulogic_vector(31 downto 0); -- source base address
    dst_base : std_ulogic_vector(31 downto 0); -- destination base address
    num      : std_ulogic_vector(23 downto 0); -- number of elements
    qsel     : std_ulogic_vector(1 downto 0);  -- data quantity select
    src_inc  : std_ulogic; -- constant (0) or incrementing (1) source address
    dst_inc  : std_ulogic; -- constant (0) or incrementing (1) destination address
    endian   : std_ulogic; -- convert endianness when set
  end record;
  signal cfg : cfg_t;

  -- bus access engine --
  type state_t is (S_IDLE, S_READ, S_WRITE, S_NEXT);
  type engine_t is record
    state    : state_t;
    stb      : std_ulogic;
    rw       : std_ulogic;
    src_addr : std_ulogic_vector(31 downto 0);
    dst_addr : std_ulogic_vector(31 downto 0);
    num      : std_ulogic_vector(23 downto 0);
    err_rd   : std_ulogic;
    err_wr   : std_ulogic;
    src_add  : unsigned(31 downto 0);
    dst_add  : unsigned(31 downto 0);
    busy     : std_ulogic;
    done     : std_ulogic;
  end record;
  signal engine : engine_t;

  -- data alignment --
  signal align_buf, align_end : std_ulogic_vector(31 downto 0);

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o    <= rsp_terminate_c;
      cfg.enable   <= '0';
      cfg.start    <= '0';
      cfg.done     <= '0';
      cfg.src_base <= (others => '0');
      cfg.dst_base <= (others => '0');
      cfg.num      <= (others => '0');
      cfg.qsel     <= (others => '0');
      cfg.src_inc  <= '0';
      cfg.dst_inc  <= '0';
      cfg.endian   <= '0';
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');

      -- defaults --
      cfg.start <= '0'; -- default
      cfg.done  <= cfg.enable and (cfg.done or engine.done); -- set if enabled and transfer done

      -- bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(3 downto 2) = "00") then -- control and status register
            cfg.enable <= bus_req_i.data(ctrl_en_c);
            cfg.start  <= bus_req_i.data(ctrl_start_c); -- start transfer
            cfg.done   <= '0'; -- clear on write access
          end if;
          if (bus_req_i.addr(3 downto 2) = "01") then -- source base address
            cfg.src_base <= bus_req_i.data;
          end if;
          if (bus_req_i.addr(3 downto 2) = "10") then -- destination base address
            cfg.dst_base <= bus_req_i.data;
          end if;
          if (bus_req_i.addr(3 downto 2) = "11") then -- transfer type register
            cfg.num     <= bus_req_i.data(type_num_hi_c downto type_num_lo_c);
            cfg.qsel    <= bus_req_i.data(type_qsel_hi_c downto type_qsel_lo_c);
            cfg.src_inc <= bus_req_i.data(type_src_inc_c);
            cfg.dst_inc <= bus_req_i.data(type_dst_inc_c);
            cfg.endian  <= bus_req_i.data(type_endian_c);
          end if;
        else -- read access
          case bus_req_i.addr(3 downto 2) is
            when "00" => -- control and status register
              bus_rsp_o.data(ctrl_en_c)       <= cfg.enable;
              bus_rsp_o.data(ctrl_error_rd_c) <= engine.err_rd;
              bus_rsp_o.data(ctrl_error_wr_c) <= engine.err_wr;
              bus_rsp_o.data(ctrl_done_c)     <= cfg.done;
              bus_rsp_o.data(ctrl_busy_c)     <= engine.busy;
            when "01" => -- address of last read access
              bus_rsp_o.data <= engine.src_addr;
            when "10" => -- address of last write access
              bus_rsp_o.data <= engine.dst_addr;
            when others => -- transfer type register
              bus_rsp_o.data(type_num_hi_c downto type_num_lo_c)   <= engine.num;
              bus_rsp_o.data(type_qsel_hi_c downto type_qsel_lo_c) <= cfg.qsel;
              bus_rsp_o.data(type_src_inc_c)                       <= cfg.src_inc;
              bus_rsp_o.data(type_dst_inc_c)                       <= cfg.dst_inc;
              bus_rsp_o.data(type_endian_c)                        <= cfg.endian;
          end case;
        end if;
      end if;
    end if;
  end process bus_access;

  -- transfer-done interrupt --
  irq_o <= cfg.done;


  -- Bus Access Engine ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      engine.state    <= S_IDLE;
      engine.stb      <= '0';
      engine.rw       <= '0';
      engine.src_addr <= (others => '0');
      engine.dst_addr <= (others => '0');
      engine.num      <= (others => '0');
      engine.err_rd   <= '0';
      engine.err_wr   <= '0';
      engine.done     <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      engine.done <= '0';
      engine.stb  <= '0';

      -- state machine --
      case engine.state is

        when S_IDLE => -- idle, waiting for trigger
        -- ------------------------------------------------------------
          engine.src_addr <= cfg.src_base;
          engine.dst_addr <= cfg.dst_base;
          engine.num      <= cfg.num;
          engine.rw       <= '0';
          if (cfg.enable = '0') and (cfg.start = '1') then -- disabled or start
            engine.err_rd <= '0';
            engine.err_wr <= '0';
          end if;
          if (cfg.enable = '1') and (cfg.start = '1') then -- start
            engine.stb    <= '1';
            engine.state  <= S_READ;
          end if;

        when S_READ => -- pending read access
        -- ------------------------------------------------------------
          if (dma_rsp_i.err = '1') then
            engine.done   <= '1';
            engine.err_rd <= '1';
            engine.state  <= S_IDLE;
          elsif (dma_rsp_i.ack = '1') then
            engine.rw    <= '1'; -- write
            engine.stb   <= '1'; -- issue write request
            engine.state <= S_WRITE;
          end if;

        when S_WRITE => -- pending write access
        -- ------------------------------------------------------------
          if (dma_rsp_i.err = '1') then
            engine.done   <= '1';
            engine.err_wr <= '1';
            engine.state  <= S_IDLE;
          elsif (dma_rsp_i.ack = '1') then
            engine.num   <= std_ulogic_vector(unsigned(engine.num) - 1);
            engine.state <= S_NEXT;
          end if;

        when S_NEXT => -- check if done; prepare next access
        -- ------------------------------------------------------------
          if (or_reduce_f(engine.num) = '0') or (cfg.enable = '0') then -- transfer done or aborted?
            engine.done  <= '1';
            engine.state <= S_IDLE;
          else
            if (cfg.src_inc = '1') then -- incrementing source address
              engine.src_addr <= std_ulogic_vector(unsigned(engine.src_addr) + engine.src_add);
            end if;
            if (cfg.dst_inc = '1') then -- incrementing destination address
              engine.dst_addr <= std_ulogic_vector(unsigned(engine.dst_addr) + engine.dst_add);
            end if;
            engine.rw    <= '0';
            engine.stb   <= '1'; -- issue read request
            engine.state <= S_READ;
          end if;

        when others => -- undefined
        -- ------------------------------------------------------------
          engine.state <= S_IDLE;

      end case;
    end if;
  end process bus_engine;

  -- transfer in progress? --
  engine.busy <= '0' when (engine.state = S_IDLE) else '1';

  -- bus output --
  dma_req_o.stb   <= engine.stb;
  dma_req_o.rw    <= engine.rw;
  dma_req_o.addr  <= engine.dst_addr when (engine.state = S_WRITE) else engine.src_addr;
  dma_req_o.src   <= '0'; -- source = data access
  dma_req_o.priv  <= priv_mode_m_c; -- DMA accesses are always privileged
  dma_req_o.debug <= '0'; -- can never ever be in debug mode
  dma_req_o.amo   <= '0'; -- no atomic memory operation possible
  dma_req_o.amoop <= (others => '0'); -- no atomic memory operation possible
  dma_req_o.fence <= '0';

  -- address increment --
  address_inc: process(cfg.qsel)
  begin
    case cfg.qsel is
      when qsel_b2b_c => -- byte -> byte
        engine.src_add <= to_unsigned(1, 32);
        engine.dst_add <= to_unsigned(1, 32);
      when qsel_w2w_c => -- word -> word
        engine.src_add <= to_unsigned(4, 32);
        engine.dst_add <= to_unsigned(4, 32);
      when others => -- byte -> word
        engine.src_add <= to_unsigned(1, 32);
        engine.dst_add <= to_unsigned(4, 32);
    end case;
  end process address_inc;


  -- Data Transformer -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- endianness conversion --
  align_end <= dma_rsp_i.data when (cfg.endian = '0') else bswap_f(dma_rsp_i.data);

  -- source data alignment --
  src_align: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      align_buf <= (others => '0');
    elsif rising_edge(clk_i) then
      if (engine.state = S_READ) then
        if (cfg.qsel = qsel_w2w_c) then -- word
          align_buf <= align_end;
        else -- byte
          case engine.src_addr(1 downto 0) is
            when "00"   => align_buf <= replicate_f(cfg.qsel(1) and align_end(7),  24) & align_end(7 downto 0);
            when "01"   => align_buf <= replicate_f(cfg.qsel(1) and align_end(15), 24) & align_end(15 downto 8);
            when "10"   => align_buf <= replicate_f(cfg.qsel(1) and align_end(23), 24) & align_end(23 downto 16);
            when others => align_buf <= replicate_f(cfg.qsel(1) and align_end(31), 24) & align_end(31 downto 24);
          end case;
        end if;
      end if;
    end if;
  end process src_align;

  -- destination data alignment --
  dst_align: process(cfg.qsel, align_buf, engine.dst_addr)
  begin
    dma_req_o.ben <= (others => '0'); -- default
    if (cfg.qsel = qsel_b2b_c) then -- byte
      dma_req_o.data <= align_buf(7 downto 0) & align_buf(7 downto 0) & align_buf(7 downto 0) & align_buf(7 downto 0);
      dma_req_o.ben(to_integer(unsigned(engine.dst_addr(1 downto 0)))) <= '1';
    else -- word
      dma_req_o.data <= align_buf;
      dma_req_o.ben  <= (others => '1');
    end if;
  end process dst_align;


end neorv32_dma_rtl;
