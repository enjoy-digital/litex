-- ================================================================================ --
-- NEORV32 SoC - Serial Data Interface (SDI)                                        --
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

entity neorv32_sdi is
  generic (
    RTX_FIFO : natural range 1 to 2**15 -- RTX FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;  -- bus request
    bus_rsp_o : out bus_rsp_t;  -- bus response
    sdi_csn_i : in  std_ulogic; -- low-active chip-select
    sdi_clk_i : in  std_ulogic; -- serial clock
    sdi_dat_i : in  std_ulogic; -- serial data input
    sdi_dat_o : out std_ulogic; -- serial data output
    irq_o     : out std_ulogic  -- CPU interrupt
  );
end neorv32_sdi;

architecture neorv32_sdi_rtl of neorv32_sdi is

  -- control register --
  constant ctrl_en_c            : natural :=  0; -- r/w: SDI enable
  constant ctrl_clr_rx_c        : natural :=  1; -- -/w: clear RX FIFO (flag auto-clears)
  constant ctrl_clr_tx_c        : natural :=  2; -- -/w: clear TX FIFO (flag auto-clears)
  --
  constant ctrl_fifo0_c         : natural :=  4; -- r/-: log2(FIFO size), bit 0 (LSB)
  constant ctrl_fifo3_c         : natural :=  7; -- r/-: log2(FIFO size), bit 3 (MSB)
  --
  constant ctrl_irq_rx_nempty_c : natural := 16; -- r/w: interrupt if RX FIFO not empty
  constant ctrl_irq_rx_full_c   : natural := 17; -- r/w: interrupt if RX FIFO full
  constant ctrl_irq_tx_empty_c  : natural := 18; -- r/w: interrupt if TX FIFO empty
  --
  constant ctrl_rx_empty_c      : natural := 24; -- r/-: RX FIFO empty
  constant ctrl_rx_full_c       : natural := 25; -- r/-: RX FIFO full
  constant ctrl_tx_empty_c      : natural := 26; -- r/-: TX FIFO empty
  constant ctrl_tx_full_c       : natural := 27; -- r/-: TX FIFO full
  --
  constant ctrl_cs_active_c     : natural := 31; -- r/-: chip-select is active when set

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(RTX_FIFO);

  -- control register (see bit definitions above) --
  type ctrl_t is record
    enable, clr_rx, clr_tx, irq_rx_nempty, irq_rx_full, irq_tx_empty : std_ulogic;
  end record;
  signal ctrl : ctrl_t;

  -- input synchronizer --
  type sync_t is record
    sck_ff : std_ulogic_vector(2 downto 0);
    csn_ff : std_ulogic_vector(1 downto 0);
    sdi_ff : std_ulogic_vector(1 downto 0);
    sck    : std_ulogic;
    csn    : std_ulogic;
    sdi    : std_ulogic;
  end record;
  signal sync : sync_t;

  -- serial engine --
  type serial_t is record
    state  : std_ulogic_vector(2 downto 0);
    cnt    : std_ulogic_vector(3 downto 0);
    sreg   : std_ulogic_vector(7 downto 0);
    sdi_ff : std_ulogic;
    done   : std_ulogic;
  end record;
  signal serial : serial_t;

  -- RX/TX FIFO interface --
  type fifo_t is record
    we, re, clr  : std_ulogic;
    wdata, rdata : std_ulogic_vector(7 downto 0);
    avail, free  : std_ulogic;
  end record;
  signal tx_fifo, rx_fifo : fifo_t;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o          <= rsp_terminate_c;
      ctrl.enable        <= '0';
      ctrl.clr_rx        <= '0';
      ctrl.clr_tx        <= '0';
      ctrl.irq_rx_nempty <= '0';
      ctrl.irq_rx_full   <= '0';
      ctrl.irq_tx_empty  <= '0';
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      -- read/write access --
      ctrl.clr_rx <= '0';
      ctrl.clr_tx <= '0';
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then -- control register
            ctrl.enable        <= bus_req_i.data(ctrl_en_c);
            ctrl.clr_rx        <= bus_req_i.data(ctrl_clr_rx_c);
            ctrl.clr_tx        <= bus_req_i.data(ctrl_clr_tx_c);
            ctrl.irq_rx_nempty <= bus_req_i.data(ctrl_irq_rx_nempty_c);
            ctrl.irq_rx_full   <= bus_req_i.data(ctrl_irq_rx_full_c);
            ctrl.irq_tx_empty  <= bus_req_i.data(ctrl_irq_tx_empty_c);
          end if;
        else -- read access
          if (bus_req_i.addr(2) = '0') then -- control register
            bus_rsp_o.data(ctrl_en_c)                        <= ctrl.enable;
            bus_rsp_o.data(ctrl_fifo3_c downto ctrl_fifo0_c) <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
            bus_rsp_o.data(ctrl_irq_rx_nempty_c)             <= ctrl.irq_rx_nempty;
            bus_rsp_o.data(ctrl_irq_rx_full_c)               <= ctrl.irq_rx_full;
            bus_rsp_o.data(ctrl_irq_tx_empty_c)              <= ctrl.irq_tx_empty;
            bus_rsp_o.data(ctrl_rx_empty_c)                  <= not rx_fifo.avail;
            bus_rsp_o.data(ctrl_rx_full_c)                   <= not rx_fifo.free;
            bus_rsp_o.data(ctrl_tx_empty_c)                  <= not tx_fifo.avail;
            bus_rsp_o.data(ctrl_tx_full_c)                   <= not tx_fifo.free;
            bus_rsp_o.data(ctrl_cs_active_c)                 <= not sync.csn;
          else -- data register
            bus_rsp_o.data(7 downto 0) <= rx_fifo.rdata;
          end if;
        end if;
      end if;
    end if;
  end process bus_access;


  -- Data FIFO ("Ring Buffer") --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- TX --
  tx_fifo_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_fifo_size_c,
    DWIDTH  => 8,
    OUTGATE => true -- send zero if no TX data available
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

  tx_fifo.clr   <= (not ctrl.enable) or ctrl.clr_tx;
  tx_fifo.wdata <= bus_req_i.data(7 downto 0);
  tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  tx_fifo.re    <= serial.done;


  -- RX --
  rx_fifo_inst: entity neorv32.neorv32_prim_fifo
  generic map (
    AWIDTH  => log2_fifo_size_c,
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

  rx_fifo.clr   <= (not ctrl.enable) or ctrl.clr_rx;
  rx_fifo.wdata <= serial.sreg;
  rx_fifo.we    <= serial.done;
  rx_fifo.re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';


  -- interrupt generator --
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (
               (ctrl.irq_rx_nempty and      rx_fifo.avail) or -- RX FIFO not empty
               (ctrl.irq_rx_full   and (not rx_fifo.free)) or -- RX FIFO full
               (ctrl.irq_tx_empty  and (not tx_fifo.avail))); -- TX FIFO empty
    end if;
  end process irq_generator;


  -- Input Synchronizer ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  synchronizer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      sync.sck_ff <= (others => '0');
      sync.csn_ff <= (others => '0');
      sync.sdi_ff <= (others => '0');
    elsif rising_edge(clk_i) then
      sync.sck_ff <= sync.sck_ff(1 downto 0) & sdi_clk_i;
      sync.csn_ff <= sync.csn_ff(0) & sdi_csn_i;
      sync.sdi_ff <= sync.sdi_ff(0) & sdi_dat_i;
    end if;
  end process synchronizer;

  sync.sck <= sync.sck_ff(1) xor sync.sck_ff(2); -- edge detect (rising or falling)
  sync.csn <= sync.csn_ff(1);
  sync.sdi <= sync.sdi_ff(1);


  -- Serial Engine --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  serial_engine: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      serial.done   <= '0';
      serial.state  <= (others => '0');
      serial.cnt    <= (others => '0');
      serial.sreg   <= (others => '0');
      serial.sdi_ff <= '0';
    elsif rising_edge(clk_i) then
      serial.done     <= '0'; -- default
      serial.state(2) <= ctrl.enable;
      case serial.state is

        when "100" => -- enabled but idle, waiting for new transmission trigger
        -- ------------------------------------------------------------
          serial.cnt <= (others => '0');
          if (sync.csn = '0') and (serial.done = '0') then -- start new transmission on falling edge of CS
            serial.state(1 downto 0) <= "01";
          end if;

        when "101" => -- get TX data
        -- ------------------------------------------------------------
          serial.cnt  <= (others => '0');
          serial.sreg <= tx_fifo.rdata;
          serial.state(1 downto 0) <= "10";

        when "110" => -- bit phase A: sample
        -- ------------------------------------------------------------
          serial.sdi_ff <= sync.sdi;
          if (sync.csn = '1') then -- transmission aborted?
            serial.state(1 downto 0) <= "00";
          elsif (sync.sck = '1') then
            serial.cnt               <= std_ulogic_vector(unsigned(serial.cnt) + 1);
            serial.state(1 downto 0) <= "11";
          end if;

        when "111" => -- bit phase B: shift
        -- ------------------------------------------------------------
          if (sync.csn = '1') then -- transmission aborted?
            serial.state(1 downto 0) <= "00";
          elsif (sync.sck = '1') then
            serial.sreg <= serial.sreg(serial.sreg'left-1 downto 0) & serial.sdi_ff;
            if (serial.cnt(3) = '1') then -- done?
              serial.done              <= '1'; -- push RX byte to FIFO and get next TX byte
              serial.state(1 downto 0) <= "00";
            else
              serial.state(1 downto 0) <= "10";
            end if;
          end if;

        when others => -- "0--": disabled
        -- ------------------------------------------------------------
          serial.state(1 downto 0) <= "00";

      end case;
    end if;
  end process serial_engine;

  -- serial data output --
  sdi_dat_o <= serial.sreg(serial.sreg'left);


end neorv32_sdi_rtl;
