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
    UART_RX_FIFO : natural range 1 to 2**15; -- RX FIFO depth, has to be a power of two, min 1
    UART_TX_FIFO : natural range 1 to 2**15  -- TX FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i       : in  std_ulogic;                    -- global clock line
    rstn_i      : in  std_ulogic;                    -- global reset line, low-active, async
    bus_req_i   : in  bus_req_t;                     -- bus request
    bus_rsp_o   : out bus_rsp_t;                     -- bus response
    clkgen_i    : in  std_ulogic_vector(7 downto 0); -- prescaled clock enables
    uart_txd_o  : out std_ulogic;                    -- serial TX line
    uart_rxd_i  : in  std_ulogic;                    -- serial RX line
    uart_rtsn_o : out std_ulogic;                    -- ready to receive ("RTR"), low-active, optional
    uart_ctsn_i : in  std_ulogic;                    -- allowed to transmit, low-active, optional
    irq_o       : out std_ulogic                     -- interrupt
  );
end neorv32_uart;

architecture neorv32_uart_rtl of neorv32_uart is

  -- control register bits --
  constant ctrl_en_c            : natural :=  0; -- r/w: UART enable
  constant ctrl_sim_en_c        : natural :=  1; -- r/w: simulation-mode enable
  constant ctrl_hwfc_en_c       : natural :=  2; -- r/w: enable RTS/CTS hardware flow-control
  constant ctrl_prsc0_c         : natural :=  3; -- r/w: baud prescaler, bit 0 (LSB)
  constant ctrl_prsc2_c         : natural :=  5; -- r/w: baud prescaler, bit 2 (MSB)
  constant ctrl_baud0_c         : natural :=  6; -- r/w: baud divisor, bit 0 (LSB)
  constant ctrl_baud9_c         : natural := 15; -- r/w: baud divisor, bit 9 (MSB)
  constant ctrl_rx_nempty_c     : natural := 16; -- r/-: RX FIFO not empty
  constant ctrl_rx_full_c       : natural := 17; -- r/-: RX FIFO full
  constant ctrl_tx_empty_c      : natural := 18; -- r/-: TX FIFO empty
  constant ctrl_tx_nfull_c      : natural := 19; -- r/-: TX FIFO not full
  constant ctrl_irq_rx_nempty_c : natural := 20; -- r/w: IRQ if RX FIFO not empty
  constant ctrl_irq_rx_full_c   : natural := 21; -- r/w: IRQ if RX FIFO full
  constant ctrl_irq_tx_empty_c  : natural := 22; -- r/w: IRQ if TX FIFO empty
  constant ctrl_irq_tx_nfull_c  : natural := 23; -- r/w: IRQ if TX FIFO not full
  --
  constant ctrl_rx_over_c       : natural := 30; -- r/-: RX FIFO overflow
  constant ctrl_tx_busy_c       : natural := 31; -- r/-: UART transmitter is busy and TX FIFO not empty

  -- data register bits --
  constant data_rtx_lsb_c   : natural :=  0; -- r/w: RX/TX data LSB
  constant data_rtx_msb_c   : natural :=  7; -- r/w: RX/TX data MSB
  constant data_rx_fifo_lsb : natural :=  8; -- r/-: log2(RX FIFO size) LSB
  constant data_rx_fifo_msb : natural := 11; -- r/-: log2(RX FIFO size) MSB
  constant data_tx_fifo_lsb : natural := 12; -- r/-: log2(TX FIFO size) LSB
  constant data_tx_fifo_msb : natural := 15; -- r/-: log2(TX FIFO size) MSB

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
    irq_rx_full   : std_ulogic;
    irq_tx_empty  : std_ulogic;
    irq_tx_nfull  : std_ulogic;
  end record;
  signal ctrl : ctrl_t;

  -- serial engines --
  type serial_engine_t is record
    state   : std_ulogic_vector(1 downto 0); -- FSM state
    sreg    : std_ulogic_vector(8 downto 0); -- data shift register
    bitcnt  : std_ulogic_vector(3 downto 0); -- frame bit counter
    baudcnt : std_ulogic_vector(9 downto 0); -- baud rate counter
    sync    : std_ulogic_vector(2 downto 0); -- input synchronizer
    done    : std_ulogic; -- operation done
  end record;
  signal tx_engine, rx_engine : serial_engine_t;
  signal rx_overrun : std_ulogic;

  -- FIFO interface --
  type fifo_t is record
    clr, we, re  : std_ulogic;
    wdata, rdata : std_ulogic_vector(7 downto 0);
    free, avail  : std_ulogic;
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
      ctrl.irq_rx_full   <= '0';
      ctrl.irq_tx_empty  <= '0';
      ctrl.irq_tx_nfull  <= '0';
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      -- bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then -- control register
            ctrl.enable        <= bus_req_i.data(ctrl_en_c);
            ctrl.sim_mode      <= bus_req_i.data(ctrl_sim_en_c) and bool_to_ulogic_f(is_simulation_c);
            ctrl.hwfc_en       <= bus_req_i.data(ctrl_hwfc_en_c);
            ctrl.prsc          <= bus_req_i.data(ctrl_prsc2_c downto ctrl_prsc0_c);
            ctrl.baud          <= bus_req_i.data(ctrl_baud9_c downto ctrl_baud0_c);
            ctrl.irq_rx_nempty <= bus_req_i.data(ctrl_irq_rx_nempty_c);
            ctrl.irq_rx_full   <= bus_req_i.data(ctrl_irq_rx_full_c);
            ctrl.irq_tx_empty  <= bus_req_i.data(ctrl_irq_tx_empty_c);
            ctrl.irq_tx_nfull  <= bus_req_i.data(ctrl_irq_tx_nfull_c);
          end if;
        else -- read access
          if (bus_req_i.addr(2) = '0') then -- control register
            bus_rsp_o.data(ctrl_en_c)                        <= ctrl.enable;
            bus_rsp_o.data(ctrl_sim_en_c)                    <= ctrl.sim_mode and bool_to_ulogic_f(is_simulation_c);
            bus_rsp_o.data(ctrl_hwfc_en_c)                   <= ctrl.hwfc_en;
            bus_rsp_o.data(ctrl_prsc2_c downto ctrl_prsc0_c) <= ctrl.prsc;
            bus_rsp_o.data(ctrl_baud9_c downto ctrl_baud0_c) <= ctrl.baud;
            bus_rsp_o.data(ctrl_rx_nempty_c)                 <= rx_fifo.avail;
            bus_rsp_o.data(ctrl_rx_full_c)                   <= not rx_fifo.free;
            bus_rsp_o.data(ctrl_tx_empty_c)                  <= not tx_fifo.avail;
            bus_rsp_o.data(ctrl_tx_nfull_c)                  <= tx_fifo.free;
            bus_rsp_o.data(ctrl_irq_rx_nempty_c)             <= ctrl.irq_rx_nempty;
            bus_rsp_o.data(ctrl_irq_rx_full_c)               <= ctrl.irq_rx_full;
            bus_rsp_o.data(ctrl_irq_tx_empty_c)              <= ctrl.irq_tx_empty;
            bus_rsp_o.data(ctrl_irq_tx_nfull_c)              <= ctrl.irq_tx_nfull;
            bus_rsp_o.data(ctrl_rx_over_c)                   <= rx_overrun;
            bus_rsp_o.data(ctrl_tx_busy_c)                   <= tx_engine.state(0) or tx_fifo.avail;
          else -- data register
            bus_rsp_o.data(data_rtx_msb_c   downto data_rtx_lsb_c)   <= rx_fifo.rdata;
            bus_rsp_o.data(data_rx_fifo_msb downto data_rx_fifo_lsb) <= std_ulogic_vector(to_unsigned(log2_rx_fifo_c, 4));
            bus_rsp_o.data(data_tx_fifo_msb downto data_tx_fifo_lsb) <= std_ulogic_vector(to_unsigned(log2_tx_fifo_c, 4));
          end if;
        end if;
      end if;
    end if;
  end process bus_access;

  -- UART clock enable --
  uart_clk <= clkgen_i(to_integer(unsigned(ctrl.prsc)));


  -- TX FIFO --------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tx_engine_fifo_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_tx_fifo_c,
    DWIDTH  => 8,
    OUTGATE => false
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => tx_fifo.clr,
    -- write port --
    wdata_i => tx_fifo.wdata,
    we_i    => tx_fifo.we,
    free_o  => tx_fifo.free,
    -- read port --
    re_i    => tx_fifo.re,
    rdata_o => tx_fifo.rdata,
    avail_o => tx_fifo.avail
  );

  tx_fifo.clr   <= '1' when (ctrl.enable = '0') or (ctrl.sim_mode = '1') else '0';
  tx_fifo.wdata <= bus_req_i.data(data_rtx_msb_c downto data_rtx_lsb_c);
  tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  tx_fifo.re    <= tx_engine.done;


  -- RX FIFO --------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  rx_engine_fifo_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_rx_fifo_c,
    DWIDTH  => 8,
    OUTGATE => false
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => rx_fifo.clr,
    -- write port --
    wdata_i => rx_fifo.wdata,
    we_i    => rx_fifo.we,
    free_o  => rx_fifo.free,
    -- read port --
    re_i    => rx_fifo.re,
    rdata_o => rx_fifo.rdata,
    avail_o => rx_fifo.avail
  );

  rx_fifo.clr   <= '1' when (ctrl.enable = '0') or (ctrl.sim_mode = '1') else '0';
  rx_fifo.wdata <= rx_engine.sreg(7 downto 0);
  rx_fifo.we    <= rx_engine.done;
  rx_fifo.re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';


  -- Interrupt Generator --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  irq_gen: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (
               (ctrl.irq_tx_empty  and (not tx_fifo.avail)) or -- TX FIFO empty
               (ctrl.irq_tx_nfull  and tx_fifo.free)        or -- TX FIFO not full
               (ctrl.irq_rx_nempty and rx_fifo.avail)       or -- RX FIFO not empty
               (ctrl.irq_rx_full   and (not rx_fifo.free)));   -- RX FIFO full
    end if;
  end process irq_gen;


  -- Transmit Engine ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  transmitter: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      tx_engine.state   <= (others => '0');
      tx_engine.sreg    <= (others => '0');
      tx_engine.bitcnt  <= (others => '0');
      tx_engine.baudcnt <= (others => '0');
      tx_engine.sync    <= (others => '0');
      tx_engine.done    <= '0';
      uart_txd_o        <= '1';
    elsif rising_edge(clk_i) then
      if (uart_clk = '1') then
        tx_engine.sync <= tx_engine.sync(1 downto 0) & uart_ctsn_i; -- CTS synchronizer
      end if;
      uart_txd_o         <= '1'; -- default
      tx_engine.done     <= '0'; -- default
      tx_engine.state(1) <= ctrl.enable; -- disable-override
      case tx_engine.state is

        when "10" => -- wait for new data to send
        -- ------------------------------------------------------------
          tx_engine.baudcnt <= ctrl.baud;
          tx_engine.bitcnt  <= "1011"; -- 1 start-bit + 8 data-bits + 1 stop-bit + 1 pause-bit
          tx_engine.sreg    <= tx_fifo.rdata & '0'; -- data & start-bit
          if (tx_fifo.avail = '1') and (tx_engine.done = '0') then -- data available and previous transfer done
            if (uart_clk = '1') and -- start with next clock tick
               ((tx_engine.sync(1) = '0') or (ctrl.hwfc_en = '0')) then -- allowed to send OR flow-control disabled
              tx_engine.state(0) <= '1';
            end if;
          end if;

        when "11" => -- transmit data
        -- ------------------------------------------------------------
          uart_txd_o <= tx_engine.sreg(0);
          if (uart_clk = '1') then
            if (tx_engine.baudcnt = "0000000000") then -- bit done
              tx_engine.baudcnt <= ctrl.baud;
              tx_engine.bitcnt  <= std_ulogic_vector(unsigned(tx_engine.bitcnt) - 1);
              tx_engine.sreg    <= '1' & tx_engine.sreg(tx_engine.sreg'left downto 1);
            else
              tx_engine.baudcnt <= std_ulogic_vector(unsigned(tx_engine.baudcnt) - 1);
            end if;
          end if;
          if (tx_engine.bitcnt = "0000") then -- all bits send
            tx_engine.done     <= '1';
            tx_engine.state(0) <= '0';
          end if;

        when others => -- "0-": disabled
        -- ------------------------------------------------------------
          tx_engine.state(0) <= '0';

      end case;
    end if;
  end process transmitter;


  -- Receive Engine -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  receiver: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rx_engine.state   <= (others => '0');
      rx_engine.sreg    <= (others => '0');
      rx_engine.bitcnt  <= (others => '0');
      rx_engine.baudcnt <= (others => '0');
      rx_engine.sync    <= (others => '0');
      rx_engine.done    <= '0';
    elsif rising_edge(clk_i) then
      if (uart_clk = '1') then
        rx_engine.sync <= rx_engine.sync(1 downto 0) & uart_rxd_i; -- RXD synchronizer
      end if;
      rx_engine.done     <= '0'; -- default
      rx_engine.state(1) <= ctrl.enable; -- disable-override
      case rx_engine.state is

        when "10" => -- wait for incoming transmission
        -- ------------------------------------------------------------
          rx_engine.baudcnt <= '0' & ctrl.baud(9 downto 1); -- half baud delay at the beginning to sample in the middle of each bit
          rx_engine.bitcnt  <= "1010"; -- 1 start-bit + 8 data-bits + 1 stop-bit
          if (rx_engine.sync(2 downto 1) = "10") then -- start bit detected (falling edge)?
            if (uart_clk = '1') then -- start with next clock tick
              rx_engine.state(0) <= '1';
            end if;
          end if;

        when "11" => -- receive data
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
          if (rx_engine.bitcnt = "0000") then -- all bits received
            rx_engine.done     <= '1';
            rx_engine.state(0) <= '0';
          end if;

        when others => -- "0-": disabled
        -- ------------------------------------------------------------
          rx_engine.state(0) <= '0';

      end case;
    end if;
  end process receiver;

  -- RX flow monitor --
  rx_flow: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      uart_rtsn_o <= '0';
      rx_overrun  <= '0';
    elsif rising_edge(clk_i) then
      uart_rtsn_o <= ctrl.hwfc_en and ((not ctrl.enable) or (not rx_fifo.free)); -- allowed to send?
      if (ctrl.enable = '0') then
        rx_overrun <= '0';
      elsif (rx_fifo.we = '1') and (rx_fifo.free = '0') then -- writing to full FIFO
        rx_overrun <= '1';
      end if;
    end if;
  end process rx_flow;


  -- UART Simulation-Mode: Print TX data to simulator console -------------------------------
  -- -------------------------------------------------------------------------------------------
-- pragma translate_off
-- RTL_SYNTHESIS OFF

  sim_enable:
  if is_simulation_c generate
    sim_log: process(clk_i)
      variable char_v : integer;
      variable line_v : line;
    begin
      if rising_edge(clk_i) then -- no reset required
        if ((ctrl.enable and ctrl.sim_mode and tx_fifo.we) = '1') then
          -- convert to printable ASCII char --
          char_v := to_integer(unsigned(bus_req_i.data(data_rtx_msb_c downto data_rtx_lsb_c)));
          if (char_v >= 128) then
            char_v := 0;
          end if;
          -- screen output --
          if (char_v /= 10) and (char_v /= 13) then -- skip line breaks
            write(line_v, character'val(char_v));
          elsif (char_v = 10) then -- flush line to screen
            writeline(output, line_v);
          end if;
        end if;
      end if;
    end process sim_log;
  end generate;

-- RTL_SYNTHESIS ON
-- pragma translate_on


end neorv32_uart_rtl;
