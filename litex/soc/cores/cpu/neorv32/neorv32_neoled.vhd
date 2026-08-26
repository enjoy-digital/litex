-- ================================================================================ --
-- NEORV32 SoC - Smart LED / NeoPixel(C)TM (WS2811/WS2812) Interface (NEOLED)       --
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

entity neorv32_neoled is
  generic (
    FIFO_DEPTH : natural range 1 to 2**15 -- NEOLED FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i       : in  std_ulogic; -- global clock line
    rstn_i      : in  std_ulogic; -- global reset line, low-active
    bus_req_i   : in  bus_req_t;  -- bus request
    bus_rsp_o   : out bus_rsp_t;  -- bus response
    clkgen_en_o : out std_ulogic; -- enable clock generator
    clkgen_i    : in  std_ulogic_vector(7 downto 0);
    irq_o       : out std_ulogic; -- interrupt request
    neoled_o    : out std_ulogic -- serial async data line
  );
end neorv32_neoled;

architecture neorv32_neoled_rtl of neorv32_neoled is

  -- Control register bits --
  constant ctrl_en_c       : natural :=  0; -- r/w: module enable
  constant ctrl_mode_c     : natural :=  1; -- r/w: 0 = 24-bit RGB mode, 1 = 32-bit RGBW mode
  constant ctrl_strobe_c   : natural :=  2; -- r/w: 0 = send normal data, 1 = send LED strobe command (RESET) on data write
  constant ctrl_clksel0_c  : natural :=  3; -- r/w: prescaler select bit 0
  constant ctrl_clksel2_c  : natural :=  5; -- r/w: prescaler select bit 2
  constant ctrl_bufs_0_c   : natural :=  6; -- r/-: log2(FIFO_DEPTH) bit 0
  constant ctrl_bufs_3_c   : natural :=  9; -- r/-: log2(FIFO_DEPTH) bit 3
  constant ctrl_t_tot_0_c  : natural := 10; -- r/w: pulse-clock ticks per total period bit 0
  constant ctrl_t_tot_4_c  : natural := 14; -- r/w: pulse-clock ticks per total period bit 4
  constant ctrl_t_0h_0_c   : natural := 15; -- r/w: pulse-clock ticks per ZERO high-time bit 0
  constant ctrl_t_0h_4_c   : natural := 19; -- r/w: pulse-clock ticks per ZERO high-time bit 4
  constant ctrl_t_1h_0_c   : natural := 20; -- r/w: pulse-clock ticks per ONE high-time bit 0
  constant ctrl_t_1h_4_c   : natural := 24; -- r/w: pulse-clock ticks per ONE high-time bit 4
  --
  constant ctrl_irq_conf_c : natural := 27; -- r/w: interrupt condition: 0=IRQ when buffer less than half full, 1=IRQ when buffer is empty
  constant ctrl_tx_empty_c : natural := 28; -- r/-: TX FIFO is empty
  constant ctrl_tx_half_c  : natural := 29; -- r/-: TX FIFO is at least half-full
  constant ctrl_tx_full_c  : natural := 30; -- r/-: TX FIFO is full
  constant ctrl_tx_busy_c  : natural := 31; -- r/-: serial TX engine busy when set

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(FIFO_DEPTH);

  -- control register --
  type ctrl_t is record
    enable   : std_ulogic;
    mode     : std_ulogic;
    strobe   : std_ulogic;
    clk_prsc : std_ulogic_vector(2 downto 0);
    irq_conf : std_ulogic;
    t_total  : std_ulogic_vector(4 downto 0);
    t0_high  : std_ulogic_vector(4 downto 0);
    t1_high  : std_ulogic_vector(4 downto 0);
  end record;
  signal ctrl : ctrl_t;

  -- transmission buffer --
  type tx_fifo_t is record
    we    : std_ulogic; -- write enable
    re    : std_ulogic; -- read enable
    clear : std_ulogic; -- sync reset, high-active
    wdata : std_ulogic_vector(31+2 downto 0); -- write data (excluding mode)
    rdata : std_ulogic_vector(31+2 downto 0); -- read data (including mode)
    avail : std_ulogic; -- data available?
    free  : std_ulogic; -- free entry available?
    half  : std_ulogic; -- half full
  end record;
  signal tx_fifo : tx_fifo_t;

  -- serial transmission engine --
  type serial_t is record
    -- state control --
    state      : std_ulogic_vector(2 downto 0);
    mode       : std_ulogic;
    done       : std_ulogic;
    busy       : std_ulogic;
    bit_cnt    : std_ulogic_vector(5 downto 0);
    -- shift register --
    sreg       : std_ulogic_vector(31 downto 0);
    next_bit   : std_ulogic; -- next bit to send
    -- pulse generator --
    pulse_clk  : std_ulogic; -- pulse cycle "clock"
    pulse_cnt  : std_ulogic_vector(4 downto 0);
    t_high     : std_ulogic_vector(4 downto 0);
    strobe_cnt : std_ulogic_vector(6 downto 0);
  end record;
  signal serial : serial_t;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl.enable   <= '0';
      ctrl.mode     <= '0';
      ctrl.strobe   <= '0';
      ctrl.clk_prsc <= (others => '0');
      ctrl.irq_conf <= '0';
      ctrl.t_total  <= (others => '0');
      ctrl.t0_high  <= (others => '0');
      ctrl.t1_high  <= (others => '0');
      bus_rsp_o     <= rsp_terminate_c;
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      -- bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then
            ctrl.enable   <= bus_req_i.data(ctrl_en_c);
            ctrl.mode     <= bus_req_i.data(ctrl_mode_c);
            ctrl.strobe   <= bus_req_i.data(ctrl_strobe_c);
            ctrl.clk_prsc <= bus_req_i.data(ctrl_clksel2_c downto ctrl_clksel0_c);
            ctrl.irq_conf <= bus_req_i.data(ctrl_irq_conf_c);
            ctrl.t_total  <= bus_req_i.data(ctrl_t_tot_4_c downto ctrl_t_tot_0_c);
            ctrl.t0_high  <= bus_req_i.data(ctrl_t_0h_4_c  downto ctrl_t_0h_0_c);
            ctrl.t1_high  <= bus_req_i.data(ctrl_t_1h_4_c  downto ctrl_t_1h_0_c);
          end if;
        else -- read access
          bus_rsp_o.data(ctrl_en_c)                            <= ctrl.enable;
          bus_rsp_o.data(ctrl_mode_c)                          <= ctrl.mode;
          bus_rsp_o.data(ctrl_strobe_c)                        <= ctrl.strobe;
          bus_rsp_o.data(ctrl_clksel2_c downto ctrl_clksel0_c) <= ctrl.clk_prsc;
          bus_rsp_o.data(ctrl_irq_conf_c)                      <= ctrl.irq_conf or bool_to_ulogic_f(boolean(FIFO_DEPTH = 1)); -- tie to one if FIFO_DEPTH is 1
          bus_rsp_o.data(ctrl_bufs_3_c  downto ctrl_bufs_0_c)  <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
          bus_rsp_o.data(ctrl_t_tot_4_c downto ctrl_t_tot_0_c) <= ctrl.t_total;
          bus_rsp_o.data(ctrl_t_0h_4_c  downto ctrl_t_0h_0_c)  <= ctrl.t0_high;
          bus_rsp_o.data(ctrl_t_1h_4_c  downto ctrl_t_1h_0_c)  <= ctrl.t1_high;
          --
          bus_rsp_o.data(ctrl_tx_empty_c)                      <= not tx_fifo.avail;
          bus_rsp_o.data(ctrl_tx_half_c)                       <= tx_fifo.half;
          bus_rsp_o.data(ctrl_tx_full_c)                       <= not tx_fifo.free;
          bus_rsp_o.data(ctrl_tx_busy_c)                       <= serial.busy;
        end if;
      end if;
    end if;
  end process bus_access;

  -- enable external clock generator --
  clkgen_en_o <= ctrl.enable;


  -- TX Buffer (FIFO) -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  data_buffer: entity neorv32.neorv32_fifo
  generic map (
    FIFO_DEPTH => FIFO_DEPTH, -- number of fifo entries; has to be a power of two; min 1
    FIFO_WIDTH => 32+2,       -- size of data elements in fifo
    FIFO_RSYNC => true,       -- sync read
    FIFO_SAFE  => true,       -- safe access
    FULL_RESET => false       -- no HW reset, try to infer BRAM
  )
  port map (
    -- control and status --
    clk_i   => clk_i,         -- clock, rising edge
    rstn_i  => rstn_i,        -- async reset, low-active
    clear_i => tx_fifo.clear, -- sync reset, high-active
    half_o  => tx_fifo.half,  -- FIFO is at least half full
    level_o => open,          -- fill level, zero-extended
    -- write port --
    wdata_i => tx_fifo.wdata, -- write data
    we_i    => tx_fifo.we,    -- write enable
    free_o  => tx_fifo.free,  -- at least one entry is free when set
    -- read port --
    re_i    => tx_fifo.re,    -- read enable
    rdata_o => tx_fifo.rdata, -- read data
    avail_o => tx_fifo.avail  -- data available when set
  );

  tx_fifo.re    <= '1' when (serial.state = "100") else '0';
  tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  tx_fifo.wdata <= ctrl.strobe & ctrl.mode & bus_req_i.data;
  tx_fifo.clear <= not ctrl.enable;

  -- IRQ generator --
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (
               ((not ctrl.irq_conf) and (not tx_fifo.avail)) or -- fire IRQ if FIFO is empty
               ((    ctrl.irq_conf) and (not tx_fifo.half)));   -- fire IRQ if FIFO is less than half full
    end if;
  end process irq_generator;


  -- Serial TX Engine -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  serial_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      serial.pulse_clk  <= '0';
      serial.done       <= '0';
      serial.state      <= (others => '0');
      serial.pulse_cnt  <= (others => '0');
      serial.strobe_cnt <= (others => '0');
      serial.sreg       <= (others => '0');
      serial.mode       <= '0';
      serial.bit_cnt    <= (others => '0');
      serial.t_high     <= (others => '0');
      neoled_o          <= '0';
    elsif rising_edge(clk_i) then
      -- clock generator --
      serial.pulse_clk <= clkgen_i(to_integer(unsigned(ctrl.clk_prsc)));

      -- defaults --
      serial.done <= '0';

      -- FSM --
      serial.state(2) <= ctrl.enable;
      case serial.state is

        when "100" => -- IDLE: waiting for new TX data, prepare transmission
        -- ------------------------------------------------------------
          neoled_o          <= '0';
          serial.pulse_cnt  <= (others => '0');
          serial.strobe_cnt <= (others => '0');
          serial.sreg       <= tx_fifo.rdata(31 downto 0);
          if (tx_fifo.rdata(32) = '0') then -- "RGB" mode
            serial.mode    <= '0';
            serial.bit_cnt <= "011000"; -- total number of bits to send: 3x8=24
          else -- "RGBW" mode
            serial.mode    <= '1';
            serial.bit_cnt <= "100000"; -- total number of bits to send: 4x8=32
          end if;
          if (tx_fifo.avail = '1') then
            if (tx_fifo.rdata(33) = '0') then -- send data
              serial.state(1 downto 0) <= "01";
            else -- send RESET command
              serial.state(1 downto 0) <= "11";
            end if;
          end if;

        when "101" => -- GETBIT: get next TX bit
        -- ------------------------------------------------------------
          serial.sreg      <= serial.sreg(serial.sreg'left-1 downto 0) & '0'; -- shift left by one position (MSB-first)
          serial.bit_cnt   <= std_ulogic_vector(unsigned(serial.bit_cnt) - 1);
          serial.pulse_cnt <= (others => '0');
          if (serial.next_bit = '0') then -- send zero-bit
            serial.t_high <= ctrl.t0_high;
          else -- send one-bit
            serial.t_high <= ctrl.t1_high;
          end if;
          if (serial.bit_cnt = "000000") then -- all done?
            neoled_o                 <= '0';
            serial.done              <= '1'; -- done sending data
            serial.state(1 downto 0) <= "00";
          else -- send current data MSB
            neoled_o                 <= '1';
            serial.state(1 downto 0) <= "10"; -- transmit single pulse
          end if;

        when "110" => -- PULSE: send pulse with specific duty cycle
        -- ------------------------------------------------------------
          -- total pulse length = ctrl.t_total
          -- pulse high time    = serial.t_high
          if (serial.pulse_clk = '1') then
            serial.pulse_cnt <= std_ulogic_vector(unsigned(serial.pulse_cnt) + 1);
            -- T_high reached? --
            if (serial.pulse_cnt = serial.t_high) then
              neoled_o <= '0';
            end if;
            -- T_total reached? --
            if (serial.pulse_cnt = ctrl.t_total) then
              serial.state(1 downto 0) <= "01"; -- get next bit to send
            end if;
          end if;

        when "111" => -- STROBE: strobe LED data ("RESET" command)
        -- ------------------------------------------------------------
          -- wait for 127 * ctrl.t_total to ensure RESET
          if (serial.pulse_clk = '1') then
            -- T_total reached? --
            if (serial.pulse_cnt = ctrl.t_total) then
              serial.pulse_cnt  <= (others => '0');
              serial.strobe_cnt <= std_ulogic_vector(unsigned(serial.strobe_cnt) + 1);
            else
              serial.pulse_cnt <= std_ulogic_vector(unsigned(serial.pulse_cnt) + 1);
            end if;
          end if;
          -- number of LOW periods reached for RESET? --
          if (and_reduce_f(serial.strobe_cnt) = '1') then
            serial.done              <= '1'; -- done sending RESET
            serial.state(1 downto 0) <= "00";
          end if;

        when others => -- "0--": disabled
        -- ------------------------------------------------------------
          neoled_o                 <= '0';
          serial.state(1 downto 0) <= "00";

      end case;
    end if;
  end process serial_engine;

  -- SREG's TX data: bit 23 for RGB mode (24-bit), bit 31 for RGBW mode (32-bit) --
  serial.next_bit <= serial.sreg(23) when (serial.mode = '0') else serial.sreg(31);

  -- TX engine status --
  serial.busy <= '0' when (serial.state(1 downto 0) = "00") else '1';


end neorv32_neoled_rtl;
