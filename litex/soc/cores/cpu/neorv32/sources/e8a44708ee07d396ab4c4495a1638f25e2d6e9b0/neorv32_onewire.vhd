-- ================================================================================ --
-- NEORV32 SoC - 1-Wire Interface Host Controller (ONEWIRE)                         --
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

entity neorv32_onewire is
  generic (
    ONEWIRE_FIFO : natural range 1 to 2**15 -- RTX FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i     : in  std_ulogic;                    -- global clock line
    rstn_i    : in  std_ulogic;                    -- global reset line, low-active
    bus_req_i : in  bus_req_t;                     -- bus request
    bus_rsp_o : out bus_rsp_t;                     -- bus response
    clkgen_i  : in  std_ulogic_vector(7 downto 0); -- prescaled clock enables
    onewire_i : in  std_ulogic;                    -- 1-wire line state
    onewire_o : out std_ulogic;                    -- 1-wire line pull-down
    irq_o     : out std_ulogic                     -- transfer done IRQ
  );
end neorv32_onewire;

architecture neorv32_onewire_rtl of neorv32_onewire is

  -- timing configuration (known-good, no need to change) --
  -- absolute time in multiples of the base tick time t_base; see data sheet for more information about the t* timing values
  constant t_write_one_c       : unsigned(6 downto 0) := to_unsigned( 1, 7); -- t0
  constant t_read_sample_c     : unsigned(6 downto 0) := to_unsigned( 2, 7); -- t1
  constant t_slot_end_c        : unsigned(6 downto 0) := to_unsigned( 7, 7); -- t2
  constant t_pause_end_c       : unsigned(6 downto 0) := to_unsigned( 9, 7); -- t3
  constant t_reset_end_c       : unsigned(6 downto 0) := to_unsigned(48, 7); -- t4
  constant t_presence_sample_c : unsigned(6 downto 0) := to_unsigned(55, 7); -- t5
  constant t_presence_end_c    : unsigned(6 downto 0) := to_unsigned(96, 7); -- t6

  -- control register --
  constant ctrl_en_c         : natural :=  0; -- r/w: TWI enable
  constant ctrl_clear_c      : natural :=  1; -- -/w: clear FIFO, bit auto-clears
  constant ctrl_prsc0_c      : natural :=  2; -- r/w: prescaler select bit 0
  constant ctrl_prsc1_c      : natural :=  3; -- r/w: prescaler select bit 1
  constant ctrl_clkdiv0_c    : natural :=  4; -- r/w: clock divider bit 0
  constant ctrl_clkdiv7_c    : natural := 11; -- r/w: clock divider bit 7
  --
  constant ctrl_fifo_size0_c : natural := 15; -- r/-: log2(FIFO size), bit 0 (LSB)
  constant ctrl_fifo_size3_c : natural := 18; -- r/-: log2(FIFO size), bit 3 (MSB)
  --
  constant ctrl_tx_full_c    : natural := 28; -- r/-: TX FIFO full
  constant ctrl_rx_avail_c   : natural := 29; -- r/-: RX FIFO data available
  constant ctrl_sense_c      : natural := 30; -- r/-: current state of the bus line
  constant ctrl_busy_c       : natural := 31; -- r/-: set while operation in progress

  -- data/command register --
  constant dcmd_lsb_c    : natural :=  0; -- r/w: RX/TX data MSB
  constant dcmd_msb_c    : natural :=  7; -- r/w: RX/TX data MSB
  constant dcmd_cmd_lo_c : natural :=  8; -- -/w: operation command
  constant dcmd_cmd_hi_c : natural :=  9; -- -/w: operation command
  constant dcmd_pres_c   : natural := 10; -- r/-: bus presence detected

  -- commands --
  constant cmd_nop_c : std_ulogic_vector(1 downto 0) := "00"; -- do nothing
  constant cmd_bit_c : std_ulogic_vector(1 downto 0) := "01"; -- trigger single-bit transmission
  constant cmd_byt_c : std_ulogic_vector(1 downto 0) := "10"; -- trigger full-byte transmission
  constant cmd_rst_c : std_ulogic_vector(1 downto 0) := "11"; -- trigger reset pulse and sample presence

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(ONEWIRE_FIFO);

  -- control register --
  type ctrl_t is record
    enable    : std_ulogic;
    clear     : std_ulogic;
    clk_prsc  : std_ulogic_vector(1 downto 0);
    clk_div   : std_ulogic_vector(7 downto 0);
  end record;
  signal ctrl : ctrl_t;

  -- FIFO interface --
  type fifo_t is record
    rx_clr,   tx_clr   : std_ulogic;
    rx_we,    tx_we    : std_ulogic;
    rx_re,    tx_re    : std_ulogic;
    rx_rdata, rx_wdata : std_ulogic_vector(8 downto 0);
    tx_rdata, tx_wdata : std_ulogic_vector(9 downto 0);
    rx_avail, tx_avail : std_ulogic;
    rx_free,  tx_free  : std_ulogic;
  end record;
  signal fifo : fifo_t;

  -- clock generator --
  signal clk_src   : std_ulogic_vector(3 downto 0);
  signal clk_cnt   : unsigned(7 downto 0);
  signal clk_tick  : std_ulogic;
  signal clk_tick2 : std_ulogic;

  -- serial engine --
  type serial_t is record
    state    : std_ulogic_vector(2 downto 0);
    busy     : std_ulogic;
    bit_cnt  : unsigned(2 downto 0);
    tick_cnt : unsigned(6 downto 0);
    sreg     : std_ulogic_vector(7 downto 0);
    wire_in  : std_ulogic_vector(1 downto 0);
    wire_lo  : std_ulogic;
    wire_hi  : std_ulogic;
    sample   : std_ulogic;
    presence : std_ulogic;
    done     : std_ulogic;
  end record;
  signal serial : serial_t;

begin

  -- Bus Access ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o     <= rsp_terminate_c;
      ctrl.enable   <= '0';
      ctrl.clk_prsc <= (others => '0');
      ctrl.clk_div  <= (others => '0');
      ctrl.clear    <= '0';
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      -- control register write access --
      ctrl.clear <= '0';
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '0') then -- control register
        ctrl.enable   <= bus_req_i.data(ctrl_en_c);
        ctrl.clear    <= bus_req_i.data(ctrl_clear_c);
        ctrl.clk_prsc <= bus_req_i.data(ctrl_prsc1_c downto ctrl_prsc0_c);
        ctrl.clk_div  <= bus_req_i.data(ctrl_clkdiv7_c downto ctrl_clkdiv0_c);
      end if;
      -- read access --
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '0') then
        if (bus_req_i.addr(2) = '0') then -- control register
          bus_rsp_o.data(ctrl_en_c)                                  <= ctrl.enable;
          bus_rsp_o.data(ctrl_prsc1_c downto ctrl_prsc0_c)           <= ctrl.clk_prsc;
          bus_rsp_o.data(ctrl_clkdiv7_c downto ctrl_clkdiv0_c)       <= ctrl.clk_div;
          bus_rsp_o.data(ctrl_fifo_size3_c downto ctrl_fifo_size0_c) <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
          bus_rsp_o.data(ctrl_tx_full_c)                             <= not fifo.tx_free;
          bus_rsp_o.data(ctrl_rx_avail_c)                            <= fifo.rx_avail;
          bus_rsp_o.data(ctrl_sense_c)                               <= serial.wire_in(1);
          bus_rsp_o.data(ctrl_busy_c)                                <= fifo.tx_avail or serial.busy;
        else -- data register
          bus_rsp_o.data(dcmd_msb_c downto dcmd_lsb_c) <= fifo.rx_rdata(7 downto 0);
          bus_rsp_o.data(dcmd_pres_c)                  <= fifo.rx_rdata(8);
        end if;
      end if;

    end if;
  end process bus_access;


  -- Data FIFO ("Ring Buffer") --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- TX FIFO --
  tx_fifo_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_fifo_size_c,
    DWIDTH  => 10, -- 2-bit command + 8-bit data
    OUTGATE => false
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => fifo.tx_clr,
    -- write port --
    wdata_i => fifo.tx_wdata,
    we_i    => fifo.tx_we,
    free_o  => fifo.tx_free,
    -- read port --
    re_i    => fifo.tx_re,
    rdata_o => fifo.tx_rdata,
    avail_o => fifo.tx_avail
  );

  fifo.tx_clr   <= '1' when (ctrl.enable = '0') or (ctrl.clear = '1') else '0';
  fifo.tx_we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  fifo.tx_wdata <= bus_req_i.data(dcmd_cmd_hi_c downto dcmd_cmd_lo_c) & bus_req_i.data(dcmd_msb_c downto dcmd_lsb_c);
  fifo.tx_re    <= '1' when (serial.state = "101") and (clk_tick = '1') else '0';


  -- RX FIFO --
  rx_fifo_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_fifo_size_c,
    DWIDTH  => 9, -- 1-bit presence status + 8-bit data
    OUTGATE => false
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => fifo.rx_clr,
    -- write port --
    wdata_i => fifo.rx_wdata,
    we_i    => fifo.rx_we,
    free_o  => fifo.rx_free,
    -- read port --
    re_i    => fifo.rx_re,
    rdata_o => fifo.rx_rdata,
    avail_o => fifo.rx_avail
  );

  fifo.rx_clr   <= '1' when (ctrl.enable = '0') or (ctrl.clear = '1') else '0';
  fifo.rx_wdata <= serial.presence & serial.sreg;
  fifo.rx_we    <= serial.done;
  fifo.rx_re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';


  -- IRQ if enabled and TX FIFO is empty and serial engine is idle --
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (not fifo.tx_avail) and (not serial.busy);
    end if;
  end process irq_generator;


  -- Clock Generator ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  clock_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      clk_cnt   <= (others => '0');
      clk_tick  <= '0';
      clk_tick2 <= '0';
    elsif rising_edge(clk_i) then
      clk_tick <= '0'; -- default
      if (ctrl.enable = '0') then
        clk_cnt <= (others => '0');
      elsif (clk_src(to_integer(unsigned(ctrl.clk_prsc))) = '1') then
        if (clk_cnt = unsigned(ctrl.clk_div)) then
          clk_cnt  <= (others => '0');
          clk_tick <= '1'; -- signal is high for 1 clk_i cycle every 't_base'
        else
          clk_cnt <= clk_cnt + 1;
        end if;
      end if;
      clk_tick2 <= clk_tick; -- tick delayed by one clock cycle (for precise bus state sampling)
    end if;
  end process clock_generator;

  -- only use the lowest 4 clocks of the system clock generator --
  clk_src <= clkgen_i(3 downto 0);


  -- Serial Engine (1-Wire PHY) -------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  serial_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      serial.wire_in  <= (others => '0');
      serial.wire_lo  <= '0';
      serial.wire_hi  <= '0';
      serial.state    <= (others => '0');
      serial.tick_cnt <= (others => '0');
      serial.bit_cnt  <= (others => '0');
      serial.sreg     <= (others => '0');
      serial.sample   <= '0';
      serial.done     <= '0';
      onewire_o       <= '0';
    elsif rising_edge(clk_i) then
      -- input synchronizer --
      serial.wire_in <= serial.wire_in(0) & to_stdulogic(to_bit(onewire_i)); -- "to_bit" to avoid hardware-vs-simulation mismatch

      -- bus control --
      if (serial.busy = '0') or (serial.wire_hi = '1') then -- disabled/idle or active tristate request
        onewire_o <= '1'; -- release bus (tristate), high (by pull-up resistor) or actively pulled low by device(s)
      elsif (serial.wire_lo = '1') then
        onewire_o <= '0'; -- pull bus actively low
      end if;

      -- defaults --
      serial.wire_lo <= '0';
      serial.wire_hi <= '0';
      serial.done    <= '0';

      -- FSM --
      serial.state(2) <= ctrl.enable; -- module enabled? force reset state otherwise
      case serial.state is

        when "100" => -- enabled, but IDLE: wait for new request
        -- ------------------------------------------------------------
          serial.tick_cnt <= (others => '0');
          if (fifo.tx_avail = '1') then -- new command/data available?
            serial.state(1 downto 0) <= "01"; -- SYNC
          end if;

        when "101" => -- SYNC: start operation with next base tick
        -- ------------------------------------------------------------
          if (fifo.tx_rdata(dcmd_cmd_hi_c downto dcmd_cmd_lo_c) = cmd_bit_c) then
            serial.bit_cnt <= "000"; -- single bit
          else
            serial.bit_cnt <= "111"; -- full byte
          end if;
          serial.sreg <= fifo.tx_rdata(dcmd_msb_c downto dcmd_lsb_c);
          if (clk_tick = '1') then -- synchronize
            serial.wire_lo <= '1'; -- force bus to low
            case fifo.tx_rdata(dcmd_cmd_hi_c downto dcmd_cmd_lo_c) is -- operation command
              when cmd_bit_c => serial.state(1 downto 0) <= "10"; -- RTX (single bit)
              when cmd_byt_c => serial.state(1 downto 0) <= "10"; -- RTX (full byte)
              when cmd_rst_c => serial.state(1 downto 0) <= "11"; -- RESET
              when others    => serial.state(1 downto 0) <= "00"; -- IDLE (NOP)
            end case;
          end if;

        when "110" => -- RTX: read/write 'serial.bit_cnt-1' bits
        -- ------------------------------------------------------------
          -- go high to write 1 or to read OR time slot completed --
          if ((serial.tick_cnt = t_write_one_c) and (serial.sreg(0) = '1')) or (serial.tick_cnt = t_slot_end_c) then
            serial.wire_hi <= '1'; -- release bus
          end if;
          -- sample input (precisely / just once!) --
          if (serial.tick_cnt = t_read_sample_c) and (clk_tick2 = '1') then
            serial.sample <= serial.wire_in(1);
          end if;
          -- inter-slot pause (end of bit) and iteration control --
          if (serial.tick_cnt = t_pause_end_c) then -- bit done
            serial.tick_cnt <= (others => '0');
            serial.sreg     <= serial.sample & serial.sreg(7 downto 1); -- new bit; LSB first
            serial.bit_cnt  <= serial.bit_cnt - 1;
            if (serial.bit_cnt = "000") then -- all done
              serial.done              <= '1';
              serial.state(1 downto 0) <= "00"; -- IDLE
            else -- next bit
              serial.wire_lo <= '1'; -- force bus to low again
            end if;
          elsif (clk_tick = '1') then
            serial.tick_cnt <= serial.tick_cnt + 1;
          end if;

        when "111" => -- RESET: generate reset pulse and check for bus presence
        -- ------------------------------------------------------------
          if (clk_tick = '1') then
            serial.tick_cnt <= serial.tick_cnt + 1;
          end if;
          -- end of reset pulse --
          if (serial.tick_cnt = t_reset_end_c) then
            serial.wire_hi <= '1'; -- release bus
          end if;
          -- sample device presence (precisely / just once!) --
          if (serial.tick_cnt = t_presence_sample_c) and (clk_tick2 = '1') then
            serial.presence <= not serial.wire_in(1); -- set if bus is pulled low by any device
          end if;
          -- end of presence phase --
          if (serial.tick_cnt = t_presence_end_c) then
            serial.done              <= '1';
            serial.state(1 downto 0) <= "00"; -- IDLE
          end if;

        when others => -- "0--" OFFLINE: deactivated, reset externally-readable signals
        -- ------------------------------------------------------------
          serial.sreg              <= (others => '0');
          serial.presence          <= '0';
          serial.state(1 downto 0) <= "00"; -- stay here, go to IDLE when module is enabled

      end case;
    end if;
  end process serial_engine;

  -- serial engine busy? --
  serial.busy <= '0' when (serial.state(1 downto 0) = "00") else '1';


end neorv32_onewire_rtl;
