-- ================================================================================ --
-- NEORV32 CPU - Inter-Core Communication Unit (ICC)                                --
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

entity neorv32_cpu_icc is
  port (
    -- global control --
    clk_i       : in  std_ulogic; -- global clock, rising edge
    rstn_i      : in  std_ulogic; -- global reset, low-active, async
    -- CSR interface --
    csr_we_i    : in  std_ulogic; -- global write enable
    csr_re_i    : in  std_ulogic; -- global read enable
    csr_addr_i  : in  std_ulogic_vector(11 downto 0); -- address
    csr_wdata_i : in  std_ulogic_vector(XLEN-1 downto 0); -- write data
    csr_rdata_o : out std_ulogic_vector(XLEN-1 downto 0); -- read data
    -- ICC links --
    icc_tx_o    : out icc_t; -- TX link
    icc_rx_i    : in  icc_t  -- RX link
  );
end neorv32_cpu_icc;

architecture neorv32_cpu_icc_rtl of neorv32_cpu_icc is

  signal tx_fifo_we, tx_fifo_free : std_ulogic;

begin

  -- CSR Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_read: process(csr_addr_i, icc_rx_i, tx_fifo_free)
  begin
    csr_rdata_o <= (others => '0'); -- default
    if (csr_addr_i(11 downto 1) = csr_mxiccsreg_c(11 downto 1)) then -- ICC CSR base address
      if (csr_addr_i(0) = '0') then -- csr_mxiccsreg_c - control and status register
        csr_rdata_o(0) <= icc_rx_i.rdy;
        csr_rdata_o(1) <= tx_fifo_free;
      else -- csr_mxiccdata_c - data register
        if (icc_rx_i.rdy = '1') then -- "output gate": read zero if no RX data is available
          csr_rdata_o <= icc_rx_i.dat;
        end if;
      end if;
    end if;
  end process csr_read;

  -- link read/write --
  icc_tx_o.ack <= '1' when (csr_re_i = '1') and (csr_addr_i = csr_mxiccdata_c) else '0';
  tx_fifo_we   <= '1' when (csr_we_i = '1') and (csr_addr_i = csr_mxiccdata_c) else '0';


  -- Outgoing/TX Message Queue (FIFO) -------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  tx_queue_inst: entity neorv32.neorv32_fifo
  generic map (
    FIFO_DEPTH => 4, -- yes, this is fixed
    FIFO_WIDTH => XLEN,
    FIFO_RSYNC => true,
    FIFO_SAFE  => true,
    FULL_RESET => false -- no need for a full HW reset as we have an "output gate"
  )
  port map (
    -- control and status --
    clk_i   => clk_i,
    rstn_i  => rstn_i,
    clear_i => '0',
    half_o  => open,
    level_o => open,
    -- write port --
    wdata_i => csr_wdata_i,
    we_i    => tx_fifo_we,
    free_o  => tx_fifo_free,
    -- read port --
    re_i    => icc_rx_i.ack,
    rdata_o => icc_tx_o.dat,
    avail_o => icc_tx_o.rdy
  );


end neorv32_cpu_icc_rtl;
