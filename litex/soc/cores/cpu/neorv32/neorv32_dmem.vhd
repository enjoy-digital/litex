-- ================================================================================ --
-- NEORV32 SoC - Processor-Internal Data Memory (DMEM)                              --
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

entity neorv32_dmem is
  generic (
    MEM_SIZE  : natural; -- memory size in bytes, has to be a power of 2, min 4
    OUTREG_EN : boolean  -- implement output register stage
  );
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- async reset, low-active
    bus_req_i : in  bus_req_t;  -- bus request
    bus_rsp_o : out bus_rsp_t   -- bus response
  );
end neorv32_dmem;

architecture neorv32_dmem_rtl of neorv32_dmem is

  -- auto-configuration --
  constant awidth_c  : natural := index_size_f(MEM_SIZE/4); -- word address width
  constant latency_c : natural := cond_sel_natural_f(OUTREG_EN, 2, 1); -- memory latency

  -- local signals --
  signal rdata : std_ulogic_vector(31 downto 0);
  signal wack  : std_ulogic;
  signal rden  : std_ulogic_vector(1 downto 0);
  signal en    : std_ulogic_vector(3 downto 0);

begin

  -- Memory Core ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  dmem_ram_gen:
  for i in 0 to 3 generate -- four individual byte-wide RAMs
    ram_inst: entity neorv32.neorv32_prim_spram
    generic map (
      AWIDTH => awidth_c,
      DWIDTH => 8,
      OUTREG => OUTREG_EN
    )
    port map (
      clk_i  => clk_i,
      en_i   => en(i),
      rw_i   => bus_req_i.rw,
      addr_i => bus_req_i.addr(awidth_c+1 downto 2),
      data_i => bus_req_i.data(i*8+7 downto i*8),
      data_o => rdata(i*8+7 downto i*8)
    );
  end generate;

  -- byte-wise enable --
  en <= bus_req_i.ben when (bus_req_i.stb = '1') else (others => '0');


  -- Bus Handshake --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_handshake: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      wack <= '0';
      rden <= (others => '0');
    elsif rising_edge(clk_i) then
      wack <= bus_req_i.stb and bus_req_i.rw;
      rden <= rden(0) & (bus_req_i.stb and (not bus_req_i.rw));
    end if;
  end process bus_handshake;

  bus_rsp_o.data <= rdata when (rden(latency_c-1) = '1') else (others => '0'); -- output gate
  bus_rsp_o.err  <= '0'; -- no access error possible
  bus_rsp_o.ack  <= rden(latency_c-1) or wack;


end neorv32_dmem_rtl;
