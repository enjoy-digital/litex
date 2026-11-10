-- ================================================================================ --
-- NEORV32 SoC - Serial Peripheral Interface Controller (SPI)                       --
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

entity neorv32_spi is
  generic (
    IO_SPI_FIFO : natural range 1 to 2**15 -- RTX FIFO depth, has to be a power of two, min 1
  );
  port (
    clk_i     : in  std_ulogic;                    -- global clock line
    rstn_i    : in  std_ulogic;                    -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;                     -- bus request
    bus_rsp_o : out bus_rsp_t;                     -- bus response
    clkgen_i  : in  std_ulogic_vector(7 downto 0); -- prescaled clock enables
    spi_clk_o : out std_ulogic;                    -- serial clock
    spi_dat_o : out std_ulogic;                    -- controller data out, peripheral data in
    spi_dat_i : in  std_ulogic;                    -- controller data in, peripheral data out
    spi_csn_o : out std_ulogic_vector(7 downto 0); -- chip-select, low-active
    irq_o     : out std_ulogic                     -- CPU interrupt
  );
end neorv32_spi;

architecture neorv32_spi_rtl of neorv32_spi is

  -- control register --
  constant ctrl_en_c       : natural :=  0; -- r/w: module enable
  constant ctrl_cpha_c     : natural :=  1; -- r/w: clock phase
  constant ctrl_cpol_c     : natural :=  2; -- r/w: clock polarity
  constant ctrl_prsc0_c    : natural :=  3; -- r/w: prescaler select, bit 0 (LSB)
  constant ctrl_prsc2_c    : natural :=  5; -- r/w: prescaler select, bit 2 (MSB)
  constant ctrl_cdiv0_c    : natural :=  6; -- r/w: clock divider, bit 0 (LSB)
  constant ctrl_cdiv3_c    : natural :=  9; -- r/w: clock divider, bit 3 (MSB)
  --
  constant ctrl_rx_avail_c : natural := 16; -- r/-: RX FIFO data available (FIFO not empty)
  constant ctrl_tx_empty_c : natural := 17; -- r/-: TX FIFO empty
  constant ctrl_tx_full_c  : natural := 18; -- r/-: TX FIFO full
  --
  constant ctrl_fifo0_c    : natural := 24; -- r/-: log2(FIFO size), bit 0 (LSB)
  constant ctrl_fifo3_c    : natural := 27; -- r/-: log2(FIFO size), bit 3 (MSB)
  --
  constant ctrl_cs_en_c    : natural := 30; -- r/-: a chip-select line is active when set
  constant ctrl_busy_c     : natural := 31; -- r/-: SPI PHY busy or TX FIFO not empty yet

  -- helpers --
  constant log2_fifo_size_c : natural := index_size_f(IO_SPI_FIFO);

  -- control register --
  type ctrl_t is record
    enable : std_ulogic;
    cpha   : std_ulogic;
    cpol   : std_ulogic;
    prsc   : std_ulogic_vector(2 downto 0);
    cdiv   : std_ulogic_vector(3 downto 0);
  end record;
  signal ctrl : ctrl_t;

  -- clock generator --
  signal cdiv_cnt   : std_ulogic_vector(3 downto 0);
  signal spi_clk_en : std_ulogic;

  -- SPI engine --
  type rtx_engine_t is record
    state    : std_ulogic_vector(2 downto 0);
    busy     : std_ulogic;
    sreg     : std_ulogic_vector(7 downto 0);
    bitcnt   : std_ulogic_vector(3 downto 0);
    sdi_sync : std_ulogic;
    sck      : std_ulogic;
    cs_ctrl  : std_ulogic_vector(3 downto 0);
    done     : std_ulogic;
  end record;
  signal rtx_engine : rtx_engine_t;

  -- FIFO interfaces --
  type tx_fifo_t is record
    we,    re    : std_ulogic;
    wdata, rdata : std_ulogic_vector(8 downto 0);
    avail, free  : std_ulogic;
    clear        : std_ulogic;
  end record;
  type rx_fifo_t is record
    we,    re    : std_ulogic;
    wdata, rdata : std_ulogic_vector(7 downto 0);
    avail, free  : std_ulogic;
    clear        : std_ulogic;
  end record;
  signal tx_fifo : tx_fifo_t;
  signal rx_fifo : rx_fifo_t;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o   <= rsp_terminate_c;
      ctrl.enable <= '0';
      ctrl.cpha   <= '0';
      ctrl.cpol   <= '0';
      ctrl.prsc   <= (others => '0');
      ctrl.cdiv   <= (others => '0');
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');

      -- read/write access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(2) = '0') then -- control register
            ctrl.enable <= bus_req_i.data(ctrl_en_c);
            ctrl.cpha   <= bus_req_i.data(ctrl_cpha_c);
            ctrl.cpol   <= bus_req_i.data(ctrl_cpol_c);
            ctrl.prsc   <= bus_req_i.data(ctrl_prsc2_c downto ctrl_prsc0_c);
            ctrl.cdiv   <= bus_req_i.data(ctrl_cdiv3_c downto ctrl_cdiv0_c);
          end if;
        else -- read access
          if (bus_req_i.addr(2) = '0') then -- control register
            bus_rsp_o.data(ctrl_en_c)                        <= ctrl.enable;
            bus_rsp_o.data(ctrl_cpha_c)                      <= ctrl.cpha;
            bus_rsp_o.data(ctrl_cpol_c)                      <= ctrl.cpol;
            bus_rsp_o.data(ctrl_prsc2_c downto ctrl_prsc0_c) <= ctrl.prsc;
            bus_rsp_o.data(ctrl_cdiv3_c downto ctrl_cdiv0_c) <= ctrl.cdiv;
            bus_rsp_o.data(ctrl_rx_avail_c)                  <= rx_fifo.avail;
            bus_rsp_o.data(ctrl_tx_empty_c)                  <= not tx_fifo.avail;
            bus_rsp_o.data(ctrl_tx_full_c)                   <= not tx_fifo.free;
            bus_rsp_o.data(ctrl_fifo3_c downto ctrl_fifo0_c) <= std_ulogic_vector(to_unsigned(log2_fifo_size_c, 4));
            bus_rsp_o.data(ctrl_cs_en_c)                     <= rtx_engine.cs_ctrl(3);
            bus_rsp_o.data(ctrl_busy_c)                      <= rtx_engine.busy or tx_fifo.avail;
          else -- RX data
            bus_rsp_o.data(7 downto 0) <= rx_fifo.rdata;
          end if;
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
    DWIDTH  => 9,
    OUTGATE => false
  )
  port map (
    -- global control --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => tx_fifo.clear,
    -- write port --
    wdata_i => tx_fifo.wdata,
    we_i    => tx_fifo.we,
    free_o  => tx_fifo.free,
    -- read port --
    re_i    => tx_fifo.re,
    rdata_o => tx_fifo.rdata,
    avail_o => tx_fifo.avail
  );

  tx_fifo.clear <= not ctrl.enable;
  tx_fifo.we    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(2) = '1') else '0';
  tx_fifo.wdata <= bus_req_i.data(31) & bus_req_i.data(7 downto 0); -- command/data select & command/data byte
  tx_fifo.re    <= '1' when (rtx_engine.state = "100") else '0';


  -- RX FIFO --
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
    clear_i => rx_fifo.clear,
    -- write port --
    wdata_i => rx_fifo.wdata,
    we_i    => rx_fifo.we,
    free_o  => rx_fifo.free,
    -- read port --
    re_i    => rx_fifo.re,
    rdata_o => rx_fifo.rdata,
    avail_o => rx_fifo.avail
  );

  rx_fifo.clear <= not ctrl.enable;
  rx_fifo.wdata <= rtx_engine.sreg;
  rx_fifo.we    <= rtx_engine.done;
  rx_fifo.re    <= '1' when (bus_req_i.stb = '1') and (bus_req_i.rw = '0') and (bus_req_i.addr(2) = '1') else '0';


  -- IRQ generator: IRQ if TX FIFO is empty and serial engine is idle --
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_o <= '0';
    elsif rising_edge(clk_i) then
      irq_o <= ctrl.enable and (not tx_fifo.avail) and (not rtx_engine.busy);
    end if;
  end process irq_generator;


  -- SPI Transceiver ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  transceiver: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      rtx_engine.done     <= '0';
      rtx_engine.state    <= (others => '0');
      rtx_engine.bitcnt   <= (others => '0');
      rtx_engine.sreg     <= (others => '0');
      rtx_engine.sdi_sync <= '0';
      rtx_engine.sck      <= '0';
      rtx_engine.cs_ctrl  <= (others => '0');
    elsif rising_edge(clk_i) then
      rtx_engine.done     <= '0';
      rtx_engine.state(2) <= ctrl.enable;
      case rtx_engine.state is

        when "100" => -- enabled but idle, waiting for new transmission trigger
        -- ------------------------------------------------------------
          rtx_engine.sck    <= ctrl.cpol;
          rtx_engine.bitcnt <= (others => '0');
          if (tx_fifo.avail = '1') then -- trigger new transmission
            if (tx_fifo.rdata(8) = '1') then -- command
              rtx_engine.cs_ctrl <= tx_fifo.rdata(3 downto 0); -- CS enable + CS select
            else -- data
              rtx_engine.sreg              <= tx_fifo.rdata(7 downto 0);
              rtx_engine.state(1 downto 0) <= "01";
            end if;
          end if;

        when "101" => -- start with next new clock pulse
        -- ------------------------------------------------------------
          if (spi_clk_en = '1') then
            if (ctrl.cpha = '1') then -- clock phase shift
              rtx_engine.sck <= not ctrl.cpol;
            end if;
            rtx_engine.state(1 downto 0) <= "10";
          end if;

        when "110" => -- first phase of bit transmission
        -- ------------------------------------------------------------
          if (spi_clk_en = '1') then
            rtx_engine.sck               <= not (ctrl.cpha xor ctrl.cpol);
            rtx_engine.sdi_sync          <= spi_dat_i; -- sample data input
            rtx_engine.bitcnt            <= std_ulogic_vector(unsigned(rtx_engine.bitcnt) + 1);
            rtx_engine.state(1 downto 0) <= "11";
          end if;

        when "111" => -- second phase of bit transmission
        -- ------------------------------------------------------------
          if (spi_clk_en = '1') then
            rtx_engine.sreg <= rtx_engine.sreg(6 downto 0) & rtx_engine.sdi_sync; -- shift and set output
            if (rtx_engine.bitcnt(3) = '1') then -- all bits transferred?
              rtx_engine.sck               <= ctrl.cpol;
              rtx_engine.done              <= '1'; -- done!
              rtx_engine.state(1 downto 0) <= "00"; -- transmission done
            else
              rtx_engine.sck               <= ctrl.cpha xor ctrl.cpol;
              rtx_engine.state(1 downto 0) <= "10";
            end if;
          end if;

        when others => -- "0--": deactivated
        -- ------------------------------------------------------------
          rtx_engine.sck               <= ctrl.cpol;
          rtx_engine.cs_ctrl           <= (others => '0');
          rtx_engine.state(1 downto 0) <= "00";

      end case;
    end if;
  end process transceiver;

  -- PHY busy flag --
  rtx_engine.busy <= '0' when (rtx_engine.state(1 downto 0) = "00") else '1';

  -- SPI output --
  spi_dat_o <= rtx_engine.sreg(7); -- MSB first
  spi_clk_o <= rtx_engine.sck;

  -- chip-select --
  chip_select: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      spi_csn_o <= (others => '1');
    elsif rising_edge(clk_i) then
      spi_csn_o <= (others => '1'); -- default: all disabled (low-active!)
      if (rtx_engine.cs_ctrl(3) = '1') then
        spi_csn_o(to_integer(unsigned(rtx_engine.cs_ctrl(2 downto 0)))) <= '0';
      end if;
    end if;
  end process chip_select;


  -- SPI Clock Generator --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  clock_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      spi_clk_en <= '0';
      cdiv_cnt   <= (others => '0');
    elsif rising_edge(clk_i) then
      spi_clk_en <= '0'; -- default
      if (ctrl.enable = '0') then -- reset/disabled
        cdiv_cnt <= (others => '0');
      elsif (clkgen_i(to_integer(unsigned(ctrl.prsc))) = '1') then -- pre-scaled clock
        if (cdiv_cnt = ctrl.cdiv) then -- clock divider for fine-tuning
          spi_clk_en <= '1';
          cdiv_cnt   <= (others => '0');
        else
          cdiv_cnt <= std_ulogic_vector(unsigned(cdiv_cnt) + 1);
        end if;
      end if;
    end if;
  end process clock_generator;


end neorv32_spi_rtl;
