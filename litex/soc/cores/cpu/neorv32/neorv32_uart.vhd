-- ================================================================================ --
-- NEORV32 SoC - Universal Asynchronous Receiver and Transmitter (UART)             --
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

-- pragma translate_off
-- RTL_SYNTHESIS OFF
use std.textio.all;
-- RTL_SYNTHESIS ON
-- pragma translate_on

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_uart is
  generic (
    SIM_MODE_EN  : boolean; -- enable simulation-mode option
    SIM_LOG_FILE : string;  -- name of SIM mode log file
    UART_RX_FIFO : natural range 1 to 2**15; -- RX fifo depth, has to be a power of two, min 1
    UART_TX_FIFO : natural range 1 to 2**15  -- TX fifo depth, has to be a power of two, min 1
  );
  port (
    clk_i       : in  std_ulogic; -- global clock line
    rstn_i      : in  std_ulogic; -- global reset line, low-active, async
    bus_req_i   : in  bus_req_t;  -- bus request
    bus_rsp_o   : out bus_rsp_t;  -- bus response
    clkgen_en_o : out std_ulogic; -- enable clock generator
    clkgen_i    : in  std_ulogic_vector(7 downto 0);
    uart_txd_o  : out std_ulogic; -- serial TX line
    uart_rxd_i  : in  std_ulogic; -- serial RX line
    uart_rtsn_o : out std_ulogic; -- ready to receive ("RTR"), low-active, optional
    uart_ctsn_i : in  std_ulogic; -- allowed to transmit, low-active, optional
    irq_rx_o    : out std_ulogic; -- RX interrupt
    irq_tx_o    : out std_ulogic  -- TX interrupt
  );
end neorv32_uart;

architecture neorv32_uart_rtl of neorv32_uart is

  -- simulation mode available? --
  constant sim_mode_en_c : boolean := SIM_MODE_EN and is_simulation_c;

  -- control register bits --
  constant ctrl_en_c            : natural :=  0; -- r/w: UART enable
  constant ctrl_sim_en_c        : natural :=  1; -- r/w: simulation-mode enable
  constant ctrl_hwfc_en_c       : natural :=  2; -- r/w: enable RTS/CTS hardware flow-control
  constant ctrl_prsc0_c         : natural :=  3; -- r/w: baud prescaler bit 0
  constant ctrl_prsc2_c         : natural :=  5; -- r/w: baud prescaler bit 2
  constant ctrl_baud0_c         : natural :=  6; -- r/w: baud divisor bit 0
  constant ctrl_baud9_c         : natural := 15; -- r/w: baud divisor bit 9
  --
  constant ctrl_rx_nempty_c     : natural := 16; -- r/-: RX FIFO not empty
  constant ctrl_rx_half_c       : natural := 17; -- r/-: RX FIFO at least half-full
  constant ctrl_rx_full_c       : natural := 18; -- r/-: RX FIFO full
  constant ctrl_tx_empty_c      : natural := 19; -- r/-: TX FIFO empty
  constant ctrl_tx_nhalf_c      : natural := 20; -- r/-: TX FIFO not at least half-full
  constant ctrl_tx_full_c       : natural := 21; -- r/-: TX FIFO full
  constant ctrl_irq_rx_nempty_c : natural := 22; -- r/w: RX FIFO not empty
  constant ctrl_irq_rx_half_c   : natural := 23; -- r/w: RX FIFO at least half-full
  constant ctrl_irq_rx_full_c   : natural := 24; -- r/w: RX FIFO full
  constant ctrl_irq_tx_empty_c  : natural := 25; -- r/w: TX FIFO empty
  constant ctrl_irq_tx_nhalf_c  : natural := 26; -- r/w: TX FIFO not at least half-full
  --
  constant ctrl_rx_clr_c        : natural := 28; -- r/w: Clear RX FIFO, flag auto-clears
  constant ctrl_tx_clr_c        : natural := 29; -- r/w: Clear TX FIFO, flag auto-clears
  constant ctrl_rx_over_c       : natural := 30; -- r/-: RX FIFO overflow
  constant ctrl_tx_busy_c       : natural := 31; -- r/-: UART transmitter is busy and TX FIFO not empty

  -- data register bits --
  constant data_rtx_lsb_c        : natural :=  0; -- r/w: RX/TX data LSB
  constant data_rtx_msb_c        : natural :=  7; -- r/w: RX/TX data MSB
  constant data_rx_fifo_size_lsb : natural :=  8; -- r/-: log2(RX fifo size) LSB
  constant data_rx_fifo_size_msb : natural := 11; -- r/-: log2(RX fifo size) MSB
  constant data_tx_fifo_size_lsb : natural := 12; -- r/-: log2(TX fifo size) LSB
  constant data_tx_fifo_size_msb : natural := 15; -- r/-: log2(TX fifo size) MSB

  -- helpers --
  constant log2_rx_fifo_c : natural := index_size_f(UART_RX_FIFO);
  constant log2_tx_fifo_c : natural := index_size_f(UART_TX_FIFO);

  -- clock generator --
  signal uart_clk : std_ulogic;

  -- control register --
  type ctrl_t is record
    enable        : std_ulogic;
    sim_mode      : std_ulogic;
    hwfc_en       : std_ulogic;
    prsc          : std_ulogic_vector(2 downto 0);
    baud          : std_ulogic_vector(9 downto 0);
    irq_rx_nempty : std_ulogic;
    irq_rx_half   : std_ulogic;
    irq_rx_full   : std_ulogic;
    irq_tx_empty  : std_ulogic;
    irq_tx_nhalf  : std_ulogic;
    clr_rx        : std_ulogic;
    clr_tx        : std_ulogic;
  end record;
  signal ctrl : ctrl_t;

  -- UART transmitter --
  type tx_engine_t is record
    state   : std_ulogic_vector(2 downto 0);
    sreg    : std_ulogic_vector(8 downto 0);
    bitcnt  : std_ulogic_vector(3 downto 0);
    baudcnt : std_ulogic_vector(9 downto 0);
    done    : std_ulogic;
    busy    : std_ulogic;
    cts     : std_ulogic_vector(1 downto 0);
    txd     : std_ulogic;
  end record;
  signal tx_engine : tx_engine_t;

  -- UART receiver --
  type rx_engine_t is record
    state   : std_ulogic_vector(1 downto 0);
    sreg    : std_ulogic_vector(8 downto 0);
    bitcnt  : std_ulogic_vector(3 downto 0);
    baudcnt : std_ulogic_vector(9 downto 0);
    done    : std_ulogic;
    sync    : std_ulogic_vector(2 downto 0);
    over    : std_ulogic;
  end record;
  signal rx_engine : rx_engine_t;

  -- FIFO interface --
  type fifo_t is record
    clear : std_ulogic; -- sync reset, high-active
    we    : std_ulogic; -- write enable
    re    : std_ulogic; -- read enable
    wdata : std_ulogic_vector(7 downto 0); -- write data
    rdata : std_ulogic_vector(7 downto 0); -- read data
    free  : std_ulogic; -- free entry available?
    avail : std_ulogic; -- data available?
    half  : std_ulogic; -- at least half full
  end record;
  signal rx_fifo, tx_fifo : fifo_t;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o          <= rsp_terminate_c;
      ctrl.enable        <= '0';
      ctrl.sim_mode      <= '0';
      ctrl.hwfc_en       <= '0';
      ctrl.prsc          <= (others => '0');
      ctrl.baud          <= (others => '0');
      ctrl.irq_rx_nempty <= '0';
      ctrl.irq_rx_half   <= '0';
      ctrl.irq_rx_full   <= '0';
      ctrl.irq_tx_empty  <= '0';
      ctrl.irq_tx_nhalf  <= '0';
      ctrl.clr_rx        <= '0';
      ctrl.clr_tx        <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      ctrl.clr_rx    <= '0'; -- auto-clear
      ctrl.clr_tx    <= '0'; -- auto-clear
      -- bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then -- control register
            ctrl.enable        <= bus_req_i.data(ctrl_en_c);
            ctrl.sim_mode      <= bus_req_i.data(ctrl_sim_en_c) and bool_to_ulogic_f(sim_mode_en_c);
            ctrl.hwfc_en       <= bus_req_i.data(ctrl_hwfc_en_c);
            ctrl.prsc          <= bus_req_i.data(ctrl_prsc2_c downto ctrl_prsc0_c);
            ctrl.baud          <= bus_req_i.data(ctrl_baud9_c downto ctrl_baud0_c);
            --
            ctrl.irq_rx_nempty <= bus_req_i.data(ctrl_irq_rx_nempty_c);
            ctrl.irq_rx_half   <= bus_req_i.data(ctrl_irq_rx_half_c);
            ctrl.irq_rx_full   <= bus_req_i.data(ctrl_irq_rx_full_c);
            ctrl.irq_tx_empty  <= bus_req_i.data(ctrl_irq_tx_empty_c);
            ctrl.irq_tx_nhalf  <= bus_req_i.data(ctrl_irq_tx_nhalf_c);
            ctrl.clr_rx        <= bus_req_i.data(ctrl_rx_clr_c);
            ctrl.clr_tx        <= bus_req_i.data(ctrl_tx_clr_c);
          end if;
        else -- read access
          if (bus_req_i.addr(2) = '0') then -- control register
            bus_rsp_o.data(ctrl_en_c)                        <= ctrl.enable;
            bus_rsp_o.data(ctrl_sim_en_c)                    <= ctrl.sim_mode and bool_to_ulogic_f(sim_mode_en_c);
            bus_rsp_o.data(ctrl_hwfc_en_c)                   <= ctrl.hwfc_en;
            bus_rsp_o.data(ctrl_prsc2_c downto ctrl_prsc0_c) <= ctrl.prsc;
            bus_rsp_o.data(ctrl_baud9_c downto ctrl_baud0_c) <= ctrl.baud;
            --
            bus_rsp_o.data(ctrl_rx_nempty_c)                 <= rx_fifo.avail;
            bus_rsp_o.data(ctrl_rx_half_c)                   <= rx_fifo.half;
            bus_rsp_o.data(ctrl_rx_full_c)                   <= not rx_fifo.free;
            bus_rsp_o.data(ctrl_tx_empty_c)                  <= not tx_fifo.avail;
            bus_rsp_o.data(ctrl_tx_nhalf_c)                  <= not tx_fifo.half;
            bus_rsp_o.data(ctrl_tx_full_c)                   <= not tx_fifo.free;
            --
            bus_rsp_o.data(ctrl_irq_rx_nempty_c)             <= ctrl.irq_rx_nempty;
            bus_rsp_o.data(ctrl_irq_rx_half_c)               <= ctrl.irq_rx_half;
            bus_rsp_o.data(ctrl_irq_rx_full_c)               <= ctrl.irq_rx_full;
            bus_rsp_o.data(ctrl_irq_tx_empty_c)              <= ctrl.irq_tx_empty;
            bus_rsp_o.data(ctrl_irq_tx_nhalf_c)              <= ctrl.irq_tx_nhalf;
            --
            bus_rsp_o.data(ctrl_rx_over_c)                   <= rx_engine.over;
            bus_rsp_o.data(ctrl_tx_busy_c)                   <= tx_engine.busy or tx_fifo.avail;
          else -- data register
            bus_rsp_o.data(data_rtx_msb_c        downto data_rtx_lsb_c)        <= rx_fifo.rdata;
            bus_rsp_o.data(data_rx_fifo_size_msb downto data_rx_fifo_size_lsb) <= std_ulogic_vector(to_unsigned(log2_rx_fifo_c, 4));
            bus_rsp_o.data(data_tx_fifo_size_msb downto data_tx_fifo_size_lsb) <= std_ulogic_vector(to_unsigned(log2_tx_fifo_c, 4));
          end if;
        end if;

      end if;
    end if;
  end process bus_access;

  -- UART clock enable --
  clkgen_en_o <= ctrl.enable;
  uart_clk    <= clkgen_i(to_integer(unsigned(ctrl.prsc)));


  -- TX FIFO --------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tx_engine_fifo_inst: entity neorv32.neorv32_fifo
  generic map (
    FIFO_DEPTH => UART_TX_FIFO,
    FIFO_WIDTH => 8,
    FIFO_RSYNC => true,
    FIFO_SAFE  => true,
    FULL_RESET => false
  )
  port map (
    -- control and status --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => tx_fifo.clear,
    half_o  => tx_fifo.half,
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

  tx_fifo.clear <= '1' when (ctrl.enable = '0') or (ctrl.sim_mode = '1') or (ctrl.clr_tx = '1') else '0';
  tx_fifo.wdata <= bus_req_i.data(data_rtx_msb_c downto data_rtx_lsb_c);
  tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  tx_fifo.re    <= '1' when (tx_engine.state = "100") else '0';

  -- TX interrupt generator --
  tx_irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_tx_o <= '0';
    elsif rising_edge(clk_i) then
      irq_tx_o <= ctrl.enable and (
                  (ctrl.irq_tx_empty and (not tx_fifo.avail)) or -- fire IRQ if TX FIFO empty
                  (ctrl.irq_tx_nhalf and (not tx_fifo.half)));   -- fire IRQ if TX FIFO not at least half full
    end if;
  end process tx_irq_generator;


  -- RX FIFO --------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  rx_engine_fifo_inst: entity neorv32.neorv32_fifo
  generic map (
    FIFO_DEPTH => UART_RX_FIFO,
    FIFO_WIDTH => 8,
    FIFO_RSYNC => true,
    FIFO_SAFE  => true,
    FULL_RESET => false
  )
  port map (
    -- control and status --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => rx_fifo.clear,
    half_o  => rx_fifo.half,
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

  rx_fifo.clear <= '1' when (ctrl.enable = '0') or (ctrl.sim_mode = '1') or (ctrl.clr_rx = '1') else '0';
  rx_fifo.wdata <= rx_engine.sreg(7 downto 0);
  rx_fifo.we    <= rx_engine.done;
  rx_fifo.re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';

  -- RX interrupt generator --
  rx_irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_rx_o <= '0';
    elsif rising_edge(clk_i) then
      irq_rx_o <= ctrl.enable and (
                  (ctrl.irq_rx_nempty and rx_fifo.avail) or     -- fire IRQ if RX FIFO not empty
                  (ctrl.irq_rx_half   and rx_fifo.half)  or     -- fire IRQ if RX FIFO at least half full
                  (ctrl.irq_rx_full   and (not rx_fifo.free))); -- fire IRQ if RX FIFO full
    end if;
  end process rx_irq_generator;


  -- Transmit Engine ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  transmitter: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tx_engine.cts     <= (others => '0');
      tx_engine.done    <= '0';
      tx_engine.state   <= (others => '0');
      tx_engine.baudcnt <= (others => '0');
      tx_engine.bitcnt  <= (others => '0');
      tx_engine.sreg    <= (others => '0');
      tx_engine.txd     <= '1';
    elsif rising_edge(clk_i) then
      -- synchronize clear-to-send --
      tx_engine.cts <= tx_engine.cts(0) & uart_ctsn_i;

      -- defaults --
      tx_engine.done <= '0';
      tx_engine.txd  <= '1';

      -- FSM --
      tx_engine.state(2) <= ctrl.enable;
      case tx_engine.state is

        when "100" => -- IDLE: wait for new data to send
        -- ------------------------------------------------------------
          tx_engine.baudcnt <= ctrl.baud;
          tx_engine.bitcnt  <= "1011"; -- 1 start-bit + 8 data-bits + 1 stop-bit + 1 pause-bit
          tx_engine.sreg    <= tx_fifo.rdata & '0'; -- data & start-bit
          if (tx_fifo.avail = '1') then
            tx_engine.state(1 downto 0) <= "01";
          end if;

        when "101" => -- WAIT: check if we can start sending
        -- ------------------------------------------------------------
          if (uart_clk = '1') and -- start with next clock tick
             ((tx_engine.cts(1) = '0') or (ctrl.hwfc_en = '0')) then -- allowed to send OR flow-control disabled
            tx_engine.state(1 downto 0) <= "11";
          end if;

        when "111" => -- SEND: transmit data
        -- ------------------------------------------------------------
          tx_engine.txd <= tx_engine.sreg(0);
          if (uart_clk = '1') then
            if (tx_engine.baudcnt = "0000000000") then -- bit done?
              tx_engine.baudcnt <= ctrl.baud;
              tx_engine.bitcnt  <= std_ulogic_vector(unsigned(tx_engine.bitcnt) - 1);
              tx_engine.sreg    <= '1' & tx_engine.sreg(tx_engine.sreg'left downto 1);
            else
              tx_engine.baudcnt <= std_ulogic_vector(unsigned(tx_engine.baudcnt) - 1);
            end if;
          end if;
          if (tx_engine.bitcnt = "0000") then -- all bits send?
            tx_engine.done              <= '1';
            tx_engine.state(1 downto 0) <= "00";
          end if;

        when others => -- "0--": disabled
        -- ------------------------------------------------------------
          tx_engine.state(1 downto 0) <= "00";

      end case;
    end if;
  end process transmitter;

  -- transmitter busy --
  tx_engine.busy <= '0' when (tx_engine.state(1 downto 0) = "00") else '1';

  -- serial data output --
  uart_txd_o <= tx_engine.txd;


  -- Receive Engine -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  receiver: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rx_engine.sync    <= (others => '0');
      rx_engine.done    <= '0';
      rx_engine.state   <= (others => '0');
      rx_engine.baudcnt <= (others => '0');
      rx_engine.bitcnt  <= (others => '0');
      rx_engine.sreg    <= (others => '0');
    elsif rising_edge(clk_i) then
      -- input synchronizer --
      rx_engine.sync(2) <= uart_rxd_i;
      if (uart_clk = '1') then
        rx_engine.sync(1 downto 0) <= rx_engine.sync(2 downto 1);
      end if;

      -- defaults --
      rx_engine.done <= '0';

      -- FSM --
      rx_engine.state(1) <= ctrl.enable;
      case rx_engine.state is

        when "10" => -- IDLE: wait for incoming transmission
        -- ------------------------------------------------------------
          rx_engine.baudcnt <= '0' & ctrl.baud(9 downto 1); -- half baud delay at the beginning to sample in the middle of each bit
          rx_engine.bitcnt  <= "1010"; -- 1 start-bit + 8 data-bits + 1 stop-bit
          if (rx_engine.sync(1 downto 0) = "01") then -- start bit detected (falling edge)?
            rx_engine.state(0) <= '1';
          end if;

        when "11" => -- RECEIVE: sample receive data
        -- ------------------------------------------------------------
          if (uart_clk = '1') then
            if (rx_engine.baudcnt = "0000000000") then -- bit done
              rx_engine.baudcnt <= ctrl.baud;
              rx_engine.bitcnt  <= std_ulogic_vector(unsigned(rx_engine.bitcnt) - 1);
              rx_engine.sreg    <= rx_engine.sync(2) & rx_engine.sreg(rx_engine.sreg'left downto 1);
            else
              rx_engine.baudcnt <= std_ulogic_vector(unsigned(rx_engine.baudcnt) - 1);
            end if;
          end if;
          if (rx_engine.bitcnt = "0000") then -- all bits received?
            rx_engine.done     <= '1'; -- receiving done
            rx_engine.state(0) <= '0';
          end if;

        when others => -- "0-": disabled
        -- ------------------------------------------------------------
          rx_engine.state(0) <= '0';

      end case;
    end if;
  end process receiver;

  -- RX overrun flag --
  fifo_overrun: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rx_engine.over <= '0';
    elsif rising_edge(clk_i) then
      if (ctrl.enable = '0') then -- clear when disabled
        rx_engine.over <= '0';
      elsif (rx_fifo.we = '1') and (rx_fifo.free = '0') then -- writing to full FIFO
        rx_engine.over <= '1';
      end if;
    end if;
  end process fifo_overrun;

  -- HW flow-control: ready to receive? --
  rtr_control: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      uart_rtsn_o <= '0';
    elsif rising_edge(clk_i) then
      if (ctrl.hwfc_en = '1') then
        if (ctrl.enable = '0') or -- UART disabled
           (rx_fifo.half = '1') then -- RX FIFO at least half-full: no "safe space" left in RX FIFO
          uart_rtsn_o <= '1'; -- NOT allowed to send
        else
          uart_rtsn_o <= '0'; -- ready to receive
        end if;
      else
        uart_rtsn_o <= '0'; -- always ready to receive when HW flow-control is disabled
      end if;
    end if;
  end process rtr_control;


  -- SIMULATION Transmitter -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
-- pragma translate_off
-- RTL_SYNTHESIS OFF
  simulation_transmitter:
  if sim_mode_en_c generate -- for simulation only!
    sim_tx: process(clk_i)
      file file_out          : text open write_mode is SIM_LOG_FILE;
      variable char_v        : integer;
      variable line_screen_v : line;
      variable line_file_v   : line;
    begin
      if rising_edge(clk_i) then -- no reset required
        if (ctrl.enable = '1') and (ctrl.sim_mode = '1') and (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') then
          -- convert lowest byte to ASCII char --
          char_v := to_integer(unsigned(bus_req_i.data(7 downto 0)));
          if (char_v >= 128) then -- out of printable range?
            char_v := 0;
          end if;
          -- ASCII output --
          if (char_v /= 10) and (char_v /= 13) then -- skip line breaks - they are issued via "writeline"
            write(line_screen_v, character'val(char_v)); -- console
            write(line_file_v, character'val(char_v)); -- log file
          elsif (char_v = 10) then -- line break: write to screen and text file
            writeline(output, line_screen_v); -- console
            writeline(file_out, line_file_v); -- log file
          end if;
        end if;
      end if;
    end process sim_tx;
  end generate;
-- RTL_SYNTHESIS ON
-- pragma translate_on


end neorv32_uart_rtl;
