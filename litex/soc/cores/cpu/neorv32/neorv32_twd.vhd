-- ================================================================================ --
-- NEORV32 SoC - Two-Wire Device (TWD)                                              --
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

entity neorv32_twd is
  generic (
    TWD_FIFO : natural range 1 to 2**15 -- RTX FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i       : in  std_ulogic; -- global clock line
    rstn_i      : in  std_ulogic; -- global reset line, low-active, async
    bus_req_i   : in  bus_req_t;  -- bus request
    bus_rsp_o   : out bus_rsp_t;  -- bus response
    clkgen_en_o : out std_ulogic; -- enable clock generator
    clkgen_i    : in  std_ulogic_vector(7 downto 0);
    twd_sda_i   : in  std_ulogic; -- serial data line input
    twd_sda_o   : out std_ulogic; -- serial data line output
    twd_scl_i   : in  std_ulogic; -- serial clock line input
    twd_scl_o   : out std_ulogic; -- serial clock line output
    irq_o       : out std_ulogic  -- interrupt
  );
end neorv32_twd;

architecture neorv32_twd_rtl of neorv32_twd is

  -- control register --
  constant ctrl_en_c           : natural :=  0; -- r/w: module enable (reset when zero)
  constant ctrl_clr_rx_c       : natural :=  1; -- -/w: clear RX FIFO (flag auto-clears)
  constant ctrl_clr_tx_c       : natural :=  2; -- -/w: clear TX FIFO (flag auto-clears)
  constant ctrl_fsel_c         : natural :=  3; -- r/w: input filter / sample clock select
  constant ctrl_dev_addr0_c    : natural :=  4; -- r/w: device address, bit 0 (LSB)
  constant ctrl_dev_addr6_c    : natural := 10; -- r/w: device address, bit 6 (MSB)
  constant ctrl_irq_rx_avail_c : natural := 11; -- r/w: IRQ if RX FIFO data available
  constant ctrl_irq_rx_full_c  : natural := 12; -- r/w: IRQ if RX FIFO full
  constant ctrl_irq_tx_empty_c : natural := 13; -- r/w: IRQ if TX FIFO empty
  --
  constant ctrl_fifo_size0_c   : natural := 15; -- r/-: log2(FIFO size), bit 0 (LSB)
  constant ctrl_fifo_size3_c   : natural := 18; -- r/-: log2(FIFO size), bit 3 (MSB)
  --
  constant ctrl_rx_avail_c     : natural := 25; -- r/-: RX FIFO data available
  constant ctrl_rx_full_c      : natural := 26; -- r/-: RX FIFO full
  constant ctrl_tx_empty_c     : natural := 27; -- r/-: TX FIFO empty
  constant ctrl_tx_full_c      : natural := 28; -- r/-: TX FIFO full
  constant ctrl_sense_scl_c    : natural := 29; -- r/-: current state of the SCL bus line
  constant ctrl_sense_sda_c    : natural := 30; -- r/-: current state of the SDA bus line
  constant ctrl_busy_c         : natural := 31; -- r/-: bus engine is busy (transaction in progress)

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(TWD_FIFO);

  -- control register --
  type ctrl_t is record
    enable       : std_ulogic;
    clr_rx       : std_ulogic;
    clr_tx       : std_ulogic;
    fsel         : std_ulogic;
    device_addr  : std_ulogic_vector(6 downto 0);
    irq_rx_avail : std_ulogic;
    irq_rx_full  : std_ulogic;
    irq_tx_empty : std_ulogic;
  end record;
  signal ctrl : ctrl_t;

  -- bus sample logic --
  type smp_t is record
    clk_en   : std_ulogic; -- sample clock
    valid    : std_ulogic; -- valid sample
    sda_sreg : std_ulogic_vector(2 downto 0); -- synchronizer
    scl_sreg : std_ulogic_vector(2 downto 0); -- synchronizer
    sda      : std_ulogic; -- current SDA state
    scl      : std_ulogic; -- current SCL state
    scl_rise : std_ulogic; -- SCL rising edge
    scl_fall : std_ulogic; -- SCL falling edge
    start    : std_ulogic; -- start condition
    stop     : std_ulogic; -- stop condition
  end record;
  signal smp : smp_t;

  -- FIFO interface --
  type fifo_t is record
    clr   : std_ulogic; -- sync reset, high-active
    we    : std_ulogic; -- write enable
    re    : std_ulogic; -- read enable
    wdata : std_ulogic_vector(7 downto 0); -- write data
    rdata : std_ulogic_vector(7 downto 0); -- read data
    avail : std_ulogic; -- data available?
    free  : std_ulogic; -- free entry available?
  end record;
  signal rx_fifo, tx_fifo : fifo_t;

  -- bus engine --
  type state_t is (S_IDLE, S_INIT, S_ADDR, S_RESP, S_RTX, S_ACK);
  type engine_t is record
    state : state_t; -- FSM state
    cnt   : unsigned(3 downto 0); -- bit counter
    sreg  : std_ulogic_vector(7 downto 0); -- shift register
    cmd   : std_ulogic; -- 0 = write, 1 = read
    rdata : std_ulogic_vector(7 downto 0); -- read-access data
    dout  : std_ulogic; -- output bit
    ack   : std_ulogic; -- ACK/NACK after transmission
    busy  : std_ulogic; -- bus operation in progress
    wr_we : std_ulogic; -- write write-enable
    rd_re : std_ulogic; -- read read-enable
  end record;
  signal engine : engine_t;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o         <= rsp_terminate_c;
      ctrl.enable       <= '0';
      ctrl.clr_rx       <= '0';
      ctrl.clr_tx       <= '0';
      ctrl.fsel         <= '0';
      ctrl.device_addr  <= (others => '0');
      ctrl.irq_rx_avail <= '0';
      ctrl.irq_rx_full  <= '0';
      ctrl.irq_tx_empty <= '0';
    elsif rising_edge(clk_i) then
      -- bus handshake defaults --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      -- read/write access --
      ctrl.clr_rx <= '0'; -- auto-clear
      ctrl.clr_tx <= '0'; -- auto-clear
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then -- control register
            ctrl.enable       <= bus_req_i.data(ctrl_en_c);
            ctrl.clr_rx       <= bus_req_i.data(ctrl_clr_rx_c);
            ctrl.clr_tx       <= bus_req_i.data(ctrl_clr_tx_c);
            ctrl.fsel         <= bus_req_i.data(ctrl_fsel_c);
            ctrl.device_addr  <= bus_req_i.data(ctrl_dev_addr6_c downto ctrl_dev_addr0_c);
            ctrl.irq_rx_avail <= bus_req_i.data(ctrl_irq_rx_avail_c);
            ctrl.irq_rx_full  <= bus_req_i.data(ctrl_irq_rx_full_c);
            ctrl.irq_tx_empty <= bus_req_i.data(ctrl_irq_tx_empty_c);
          end if;
        else -- read access
          if (bus_req_i.addr(2) = '0') then -- control register
            bus_rsp_o.data(ctrl_en_c)                                  <= ctrl.enable;
            bus_rsp_o.data(ctrl_fsel_c)                                <= ctrl.fsel;
            bus_rsp_o.data(ctrl_dev_addr6_c downto ctrl_dev_addr0_c)   <= ctrl.device_addr;
            bus_rsp_o.data(ctrl_irq_rx_avail_c)                        <= ctrl.irq_rx_avail;
            bus_rsp_o.data(ctrl_irq_rx_full_c)                         <= ctrl.irq_rx_full;
            bus_rsp_o.data(ctrl_irq_tx_empty_c)                        <= ctrl.irq_tx_empty;
            --
            bus_rsp_o.data(ctrl_fifo_size3_c downto ctrl_fifo_size0_c) <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
            bus_rsp_o.data(ctrl_rx_avail_c)                            <= rx_fifo.avail;
            bus_rsp_o.data(ctrl_rx_full_c)                             <= not rx_fifo.free;
            bus_rsp_o.data(ctrl_tx_empty_c)                            <= not tx_fifo.avail;
            bus_rsp_o.data(ctrl_tx_full_c)                             <= not tx_fifo.free;
            bus_rsp_o.data(ctrl_sense_scl_c)                           <= smp.scl;
            bus_rsp_o.data(ctrl_sense_sda_c)                           <= smp.sda;
            bus_rsp_o.data(ctrl_busy_c)                                <= engine.busy;
          else -- RX FIFO
            bus_rsp_o.data(7 downto 0) <= rx_fifo.rdata;
          end if;
        end if;
      end if;
    end if;
  end process bus_access;

  -- enable SoC clock generator --
  clkgen_en_o <= ctrl.enable;


  -- Data FIFO ("Ring Buffer") --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- TX FIFO --
  tx_fifo_inst: entity neorv32.neorv32_fifo
  generic map (
    FIFO_DEPTH => TWD_FIFO,
    FIFO_WIDTH => 8,
    FIFO_RSYNC => true,
    FIFO_SAFE  => true,
    FULL_RESET => false
  )
  port map (
    -- control and status --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => tx_fifo.clr,
    half_o  => open,
    level_o => open,
    -- write port --
    wdata_i => tx_fifo.wdata,
    we_i    => tx_fifo.we,
    free_o  => tx_fifo.free,
    -- read port --
    re_i    => tx_fifo.re,
    rdata_o => tx_fifo.rdata,
    avail_o => tx_fifo.avail
  );

  tx_fifo.clr   <= '1' when (ctrl.enable = '0') or (ctrl.clr_tx = '1') else '0';
  tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  tx_fifo.wdata <= bus_req_i.data(7 downto 0);
  tx_fifo.re    <= engine.rd_re;
  engine.rdata  <= tx_fifo.rdata when (tx_fifo.avail = '1') else (others => '1'); -- read ones when TX FIFO is drained


  -- RX FIFO --
  rx_fifo_inst: entity neorv32.neorv32_fifo
  generic map (
    FIFO_DEPTH => TWD_FIFO,
    FIFO_WIDTH => 8,
    FIFO_RSYNC => true,
    FIFO_SAFE  => true,
    FULL_RESET => false
  )
  port map (
    -- control and status --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => rx_fifo.clr,
    half_o  => open,
    level_o => open,
    -- write port --
    wdata_i => rx_fifo.wdata,
    we_i    => rx_fifo.we,
    free_o  => rx_fifo.free,
    -- read port --
    re_i    => rx_fifo.re,
    rdata_o => rx_fifo.rdata,
    avail_o => rx_fifo.avail
  );

  rx_fifo.clr   <= '1' when (ctrl.enable = '0') or (ctrl.clr_rx = '1') else '0';
  rx_fifo.wdata <= engine.sreg;
  rx_fifo.we    <= engine.wr_we;
  rx_fifo.re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';


  -- Interrupt Generator --
  irq_trigger: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (
               (ctrl.irq_rx_avail and      rx_fifo.avail) or -- RX FIFO data available
               (ctrl.irq_rx_full  and (not rx_fifo.free)) or -- RX FIFO full
               (ctrl.irq_tx_empty and (not tx_fifo.avail))); -- TX FIFO empty
    end if;
  end process irq_trigger;


  -- Bus Sample Logic -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  synchronizer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      smp.sda_sreg <= (others => '1');
      smp.scl_sreg <= (others => '1');
      smp.valid    <= '0';
    elsif rising_edge(clk_i) then
      -- input register --
      smp.sda_sreg(0) <= to_stdulogic(to_bit(twd_sda_i)); -- "to_bit" to avoid hardware-vs-simulation mismatch
      smp.scl_sreg(0) <= to_stdulogic(to_bit(twd_scl_i));
      -- sample register --
      smp.valid <= '0';
      if (ctrl.enable = '1') then
        if (smp.clk_en = '1') then
          smp.valid <= '1'; -- valid sample
          smp.sda_sreg(2 downto 1) <= smp.sda_sreg(1 downto 0);
          smp.scl_sreg(2 downto 1) <= smp.scl_sreg(1 downto 0);
        end if;
      else
        smp.sda_sreg(2 downto 1) <= (others => '1');
        smp.scl_sreg(2 downto 1) <= (others => '1');
      end if;
    end if;
  end process synchronizer;

  -- sample clock for input "filtering" --
  smp.clk_en <= clkgen_i(clk_div64_c) when (ctrl.fsel = '1') else clkgen_i(clk_div8_c);

  -- bus event detector (event signals are "single-shot") --
  bus_event: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      smp.sda      <= '1';
      smp.scl      <= '1';
      smp.scl_rise <= '0';
      smp.scl_fall <= '0';
      smp.start    <= '0';
      smp.stop     <= '0';
    elsif rising_edge(clk_i) then
      smp.sda      <= smp.sda_sreg(2) or smp.sda_sreg(1);
      smp.scl      <= smp.sda_sreg(2) or smp.sda_sreg(1);
      smp.scl_rise <= smp.valid and (not smp.scl_sreg(2)) and (    smp.scl_sreg(1)); -- rising edge
      smp.scl_fall <= smp.valid and (    smp.scl_sreg(2)) and (not smp.scl_sreg(1)); -- falling edge
      smp.start    <= smp.valid and smp.scl_sreg(2) and smp.scl_sreg(1) and (    smp.sda_sreg(2)) and (not smp.sda_sreg(1));
      smp.stop     <= smp.valid and smp.scl_sreg(2) and smp.scl_sreg(1) and (not smp.sda_sreg(2)) and (    smp.sda_sreg(1));
    end if;
  end process bus_event;


  -- Bus Engine -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      twd_sda_o    <= '1';
      twd_scl_o    <= '1';
      engine.state <= S_IDLE;
      engine.cnt   <= (others => '0');
      engine.sreg  <= (others => '1');
      engine.cmd   <= '0';
      engine.dout  <= '0';
      engine.ack   <= '0';
      engine.wr_we <= '0';
      engine.rd_re <= '0';
    elsif rising_edge(clk_i) then
      -- keep bus idle by default --
      twd_sda_o <= '1';
      twd_scl_o <= '1';

      -- defaults --
      engine.wr_we <= '0';
      engine.rd_re <= '0';

      -- fsm --
      case engine.state is

        when S_IDLE => -- idle, wait for start condition
        -- ------------------------------------------------------------
          if (ctrl.enable = '1') and (smp.start = '1') then
            engine.state <= S_INIT;
          end if;

        when S_INIT => -- (re-)initialize new transaction
        -- ------------------------------------------------------------
          engine.cnt  <= (others => '0');
          engine.sreg <= (others => '0');
          if (ctrl.enable = '0') or (smp.stop = '1') then -- disabled or stop-condition received?
            engine.state <= S_IDLE;
          else
            engine.state <= S_ADDR;
          end if;

        when S_ADDR => -- sample address + R/W bit and check if address match
        -- ------------------------------------------------------------
          if (ctrl.enable = '0') or (smp.stop = '1') then -- disabled or stop-condition received?
            engine.state <= S_IDLE;
          elsif (smp.start = '1') then -- start-condition received?
            engine.state <= S_INIT;
          elsif (engine.cnt(3) = '1') and (smp.scl_fall = '1') then -- 8 bits received?
            if (ctrl.device_addr = engine.sreg(7 downto 1)) then -- address match?
              engine.state <= S_RESP; -- access device
            else
              engine.state <= S_IDLE; -- no match, go back to idle
            end if;
          end if;
          -- sample bus on rising edge --
          if (smp.scl_rise = '1') then
            engine.sreg <= engine.sreg(6 downto 0) & smp.sda;
            engine.cnt  <= engine.cnt + 1;
          end if;

        when S_RESP => -- send device address match ACK
        -- ------------------------------------------------------------
          twd_sda_o  <= '0'; -- ACK
          engine.cnt <= (others => '0');
          engine.cmd <= engine.sreg(0);
          if (ctrl.enable = '0') then -- disabled?
            engine.state <= S_IDLE;
          elsif (smp.scl_fall = '1') then
            engine.state <= S_RTX;
          end if;
          -- get FIFO TX data (required for read access only) --
          if (smp.scl_fall = '1') then
            engine.sreg <= engine.rdata; -- FIFO TX data
            engine.dout <= engine.rdata(7); -- FIFO TX data (first bit)
          end if;

        when S_RTX => -- receive/transmit 8 data bits
        -- ------------------------------------------------------------
          if (ctrl.enable = '0') or (smp.stop = '1') then -- disabled or stop-condition
            engine.state <= S_IDLE;
          elsif (smp.start = '1') then -- start-condition
            engine.state <= S_INIT; -- restart transaction
          elsif (engine.cnt(3) = '1') and (smp.scl_fall = '1') then -- 8 bits received?
            engine.wr_we <= not engine.cmd; -- write byte to RX FIFO (only if WRITE command)
            engine.state <= S_ACK;
          end if;
          -- sample bus on rising edge --
          if (smp.scl_rise = '1') then
            engine.sreg <= engine.sreg(6 downto 0) & smp.sda;
            engine.cnt  <= engine.cnt + 1;
          end if;
          -- set bus output only if READ operation --
          if (engine.cmd = '1') then
            twd_sda_o <= engine.dout;
            if (smp.scl_fall = '1') then -- get next bit
              engine.dout <= engine.sreg(7);
            end if;
          end if;

        when S_ACK => -- receive/transmit ACK/NACK
        -- ------------------------------------------------------------
          engine.cnt  <= (others => '0');
          engine.sreg <= engine.rdata; -- FIFO TX data
          engine.dout <= engine.rdata(7); -- FIFO TX data (first bit)
          if (ctrl.enable = '0') or (smp.stop = '1') then -- disabled or stop-condition
            engine.state <= S_IDLE;
          elsif (smp.scl_fall = '1') then -- end of this time slot
            if (engine.cmd = '0') or ((engine.cmd = '1') and (engine.ack = '0')) then -- WRITE or READ-with-ACK
              engine.state <= S_RTX;
            end if;
          end if;
          -- sample bus on rising edge --
          if (smp.scl_rise = '1') then
            engine.ack <= smp.sda;
          end if;
          -- [READ] advance to next data byte if ACK is send by host --
          if (engine.cmd = '1') and (smp.scl_rise = '1') and (smp.sda = '0') then
            engine.rd_re <= '1'; -- get next TX data byte
          end if;
          -- [WRITE] transmit ACK --
          if (engine.cmd = '0') then
            twd_sda_o <= '0';
          end if;

        when others => -- undefined
        -- ------------------------------------------------------------
          engine.state <= S_IDLE;

      end case;
    end if;
  end process bus_engine;

  -- transaction in progress --
  engine.busy <= '0' when (engine.state = S_IDLE) else '1';


end neorv32_twd_rtl;
