-- ================================================================================ --
-- NEORV32 SoC - Smart LED "NeoPixel(TM)" Interface (NEOLED)                        --
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
    FIFO_DEPTH : natural range 1 to 2**15 -- FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i     : in  std_ulogic;                    -- global clock line
    rstn_i    : in  std_ulogic;                    -- global reset line, low-active
    bus_req_i : in  bus_req_t;                     -- bus request
    bus_rsp_o : out bus_rsp_t;                     -- bus response
    clkgen_i  : in  std_ulogic_vector(7 downto 0); -- prescaled clock enables
    irq_o     : out std_ulogic;                    -- interrupt request
    neoled_o  : out std_ulogic                     -- serial async data line
  );
end neorv32_neoled;

architecture neorv32_neoled_rtl of neorv32_neoled is

  -- control register bits --
  constant ctrl_en_c       : natural :=  0; -- r/w: module enable
  constant ctrl_clksel0_c  : natural :=  1; -- r/w: prescaler select bit 0
  constant ctrl_clksel2_c  : natural :=  3; -- r/w: prescaler select bit 2
  constant ctrl_t_tot0_c   : natural :=  4; -- r/w: pulse-clock ticks per total period bit 0
  constant ctrl_t_tot4_c   : natural :=  8; -- r/w: pulse-clock ticks per total period bit 4
  constant ctrl_t_0h0_c    : natural :=  9; -- r/w: pulse-clock ticks per ZERO high-time bit 0
  constant ctrl_t_0h4_c    : natural := 13; -- r/w: pulse-clock ticks per ZERO high-time bit 4
  constant ctrl_t_1h0_c    : natural := 14; -- r/w: pulse-clock ticks per ONE high-time bit 0
  constant ctrl_t_1h4_c    : natural := 18; -- r/w: pulse-clock ticks per ONE high-time bit 4
  --
  constant ctrl_fifo0_c    : natural := 25; -- r/-: log2(FIFO_DEPTH) bit 0
  constant ctrl_fifo3_c    : natural := 28; -- r/-: log2(FIFO_DEPTH) bit 3
  constant ctrl_tx_empty_c : natural := 29; -- r/-: TX FIFO is empty
  constant ctrl_tx_full_c  : natural := 30; -- r/-: TX FIFO is full
  constant ctrl_tx_busy_c  : natural := 31; -- r/-: serial PHY busy or TX FIFO not empty yet

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(FIFO_DEPTH);

  -- control register --
  type ctrl_t is record
    enable   : std_ulogic;
    clk_prsc : std_ulogic_vector(2 downto 0);
    t_total  : std_ulogic_vector(4 downto 0);
    t0_high  : std_ulogic_vector(4 downto 0);
    t1_high  : std_ulogic_vector(4 downto 0);
  end record;
  signal ctrl : ctrl_t;

  -- transmission buffer --
  type tx_fifo_t is record
    we, re, clr  : std_ulogic;
    wdata, rdata : std_ulogic_vector(33 downto 0);
    avail, free  : std_ulogic;
  end record;
  signal tx_fifo : tx_fifo_t;

  -- serial transmission engine --
  type serial_t is record
    state : std_ulogic_vector(2 downto 0); -- FSM state
    mode  : std_ulogic; -- 24-bit / 32-bit mode
    busy  : std_ulogic; -- serial engine busy
    bcnt  : std_ulogic_vector(5 downto 0); -- bit counter
    sreg  : std_ulogic_vector(31 downto 0); -- data shift register
    sbit  : std_ulogic; -- next data bit to send
    clken : std_ulogic; -- serial clock-enable
    pcnt  : std_ulogic_vector(4 downto 0); -- pulse counter
    thigh : std_ulogic_vector(4 downto 0); -- number of clock pulses for high-time
    scnt  : std_ulogic_vector(6 downto 0); -- strobe counter
  end record;
  signal serial : serial_t;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o     <= rsp_terminate_c;
      ctrl.enable   <= '0';
      ctrl.clk_prsc <= (others => '0');
      ctrl.t_total  <= (others => '0');
      ctrl.t0_high  <= (others => '0');
      ctrl.t1_high  <= (others => '0');
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
            ctrl.clk_prsc <= bus_req_i.data(ctrl_clksel2_c downto ctrl_clksel0_c);
            ctrl.t_total  <= bus_req_i.data(ctrl_t_tot4_c downto ctrl_t_tot0_c);
            ctrl.t0_high  <= bus_req_i.data(ctrl_t_0h4_c downto ctrl_t_0h0_c);
            ctrl.t1_high  <= bus_req_i.data(ctrl_t_1h4_c downto ctrl_t_1h0_c);
          end if;
        else -- read access
          bus_rsp_o.data(ctrl_en_c)                            <= ctrl.enable;
          bus_rsp_o.data(ctrl_clksel2_c downto ctrl_clksel0_c) <= ctrl.clk_prsc;
          bus_rsp_o.data(ctrl_t_tot4_c downto ctrl_t_tot0_c)   <= ctrl.t_total;
          bus_rsp_o.data(ctrl_t_0h4_c downto ctrl_t_0h0_c)     <= ctrl.t0_high;
          bus_rsp_o.data(ctrl_t_1h4_c downto ctrl_t_1h0_c)     <= ctrl.t1_high;
          --
          bus_rsp_o.data(ctrl_fifo3_c downto ctrl_fifo0_c) <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
          bus_rsp_o.data(ctrl_tx_empty_c)                  <= not tx_fifo.avail;
          bus_rsp_o.data(ctrl_tx_full_c)                   <= not tx_fifo.free;
          bus_rsp_o.data(ctrl_tx_busy_c)                   <= serial.busy or tx_fifo.avail;
        end if;
      end if;
    end if;
  end process bus_access;


  -- TX Buffer (FIFO) -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  data_buffer: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_fifo_size_c,
    DWIDTH  => 34,
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

  tx_fifo.re    <= '1' when (serial.state = "100") else '0';
  tx_fifo.we    <= bus_req_i.stb and bus_req_i.rw and or_reduce_f(bus_req_i.addr(3 downto 2));
  tx_fifo.wdata <= (bus_req_i.addr(3) and bus_req_i.addr(2)) & bus_req_i.addr(3) & bus_req_i.data;
  tx_fifo.clr   <= not ctrl.enable;

  -- IRQ generator --
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (not tx_fifo.avail); -- IRQ if FIFO is empty
    end if;
  end process irq_generator;


  -- Serial TX Engine -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  serial_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      serial.clken <= '0';
      serial.state <= (others => '0');
      serial.pcnt  <= (others => '0');
      serial.scnt  <= (others => '0');
      serial.sreg  <= (others => '0');
      serial.mode  <= '0';
      serial.bcnt  <= (others => '0');
      serial.thigh <= (others => '0');
      neoled_o     <= '0';
    elsif rising_edge(clk_i) then
      -- clock generator --
      serial.clken <= clkgen_i(to_integer(unsigned(ctrl.clk_prsc)));

      -- FSM --
      serial.state(2) <= ctrl.enable;
      case serial.state is

        when "100" => -- IDLE: waiting for new TX data, prepare transmission
        -- ------------------------------------------------------------
          neoled_o    <= '0';
          serial.pcnt <= (others => '0');
          serial.scnt <= (others => '0');
          if (tx_fifo.rdata(32) = '0') then -- "RGB" mode (24-bit)
            serial.mode <= '0';
            serial.bcnt <= "011000";
          else -- "RGBW" mode (32-bit)
            serial.mode <= '1';
            serial.bcnt <= "100000";
          end if;
          if (tx_fifo.avail = '1') then
            serial.sreg <= tx_fifo.rdata(31 downto 0);
            if (tx_fifo.rdata(33) = '0') then -- send data
              serial.state(1 downto 0) <= "01";
            else -- send RESET command
              serial.state(1 downto 0) <= "11";
            end if;
          end if;

        when "101" => -- GETBIT: get next TX bit
        -- ------------------------------------------------------------
          serial.sreg <= serial.sreg(serial.sreg'left-1 downto 0) & '0';
          serial.bcnt <= std_ulogic_vector(unsigned(serial.bcnt) - 1);
          serial.pcnt <= (others => '0');
          if (serial.sbit = '0') then -- send zero-bit
            serial.thigh <= ctrl.t0_high;
          else -- send one-bit
            serial.thigh <= ctrl.t1_high;
          end if;
          if (serial.bcnt = "000000") then -- all done?
            serial.state(1 downto 0) <= "00";
          else -- send next bit
            neoled_o                 <= '1';
            serial.state(1 downto 0) <= "10";
          end if;

        when "110" => -- PULSE: send pulse with specific duty cycle
        -- ------------------------------------------------------------
          -- total pulse length = ctrl.t_total
          -- pulse high length  = serial.thigh
          if (serial.clken = '1') then
            serial.pcnt <= std_ulogic_vector(unsigned(serial.pcnt) + 1);
            if (serial.pcnt = serial.thigh) then -- thigh reached?
              neoled_o <= '0';
            end if;
            if (serial.pcnt = ctrl.t_total) then -- T_total reached?
              serial.state(1 downto 0) <= "01"; -- get next bit to send
            end if;
          end if;

        when "111" => -- STROBE: strobe LED data ("RESET" command)
        -- ------------------------------------------------------------
          -- wait for 127 * ctrl.t_total to ensure RESET
          if (serial.clken = '1') then
            if (serial.pcnt = ctrl.t_total) then -- T_total reached?
              serial.pcnt <= (others => '0');
              serial.scnt <= std_ulogic_vector(unsigned(serial.scnt) + 1);
            else
              serial.pcnt <= std_ulogic_vector(unsigned(serial.pcnt) + 1);
            end if;
          end if;
          -- number of LOW periods reached for RESET? --
          if (and_reduce_f(serial.scnt) = '1') then
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
  serial.sbit <= serial.sreg(23) when (serial.mode = '0') else serial.sreg(31);

  -- TX engine status --
  serial.busy <= '0' when (serial.state(1 downto 0) = "00") else '1';


end neorv32_neoled_rtl;
