-- ================================================================================ --
-- NEORV32 SoC - Cyclic Redundancy Check Unit (CRC)                                 --
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

entity neorv32_crc is
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- global reset line, low-active
    bus_req_i : in  bus_req_t;  -- bus request
    bus_rsp_o : out bus_rsp_t   -- bus response
  );
end neorv32_crc;

architecture neorv32_crc_rtl of neorv32_crc is

  -- interface register addresses --
  constant mode_addr_c : std_ulogic_vector(1 downto 0) := "00"; -- r/w: mode register
  constant poly_addr_c : std_ulogic_vector(1 downto 0) := "01"; -- r/w: polynomial register
  constant data_addr_c : std_ulogic_vector(1 downto 0) := "10"; -- -/w: data register
  constant sreg_addr_c : std_ulogic_vector(1 downto 0) := "11"; -- r/w: CRC shift register

  -- CRC core --
  type crc_t is record
    mode : std_ulogic_vector(1 downto 0);
    poly : std_ulogic_vector(31 downto 0);
    data : std_ulogic_vector(7 downto 0);
    sreg : std_ulogic_vector(31 downto 0);
    --
    cnt  : std_ulogic_vector(3 downto 0);
    msb  : std_ulogic;
  end record;
  signal crc : crc_t;

  -- delayed ACK on write access --
  signal we_ack : std_ulogic_vector(4 downto 0); -- to wait for serial CRC processing

begin

  -- Bus Access- ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o <= rsp_terminate_c;
      crc.mode  <= (others => '0');
      crc.poly  <= (others => '0');
      crc.data  <= (others => '0');
      we_ack    <= (others => '0');
    elsif rising_edge(clk_i) then
      -- bus handshake --
      bus_rsp_o.data <= (others => '0');
      bus_rsp_o.err  <= '0';
      bus_rsp_o.ack  <= we_ack(we_ack'left) or (bus_req_i.stb and (not bus_req_i.rw));

      -- write access --
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') then
        if (bus_req_i.addr(3 downto 2) = mode_addr_c) then -- mode select
          crc.mode <= bus_req_i.data(1 downto 0);
        end if;
        if (bus_req_i.addr(3 downto 2) = poly_addr_c) then -- polynomial
          crc.poly <= bus_req_i.data(31 downto 0);
        end if;
        if (bus_req_i.addr(3 downto 2) = data_addr_c) then -- data
          crc.data <= bus_req_i.data(7 downto 0);
        end if;
      end if;

      -- delayed write ACK --
      we_ack <= we_ack(we_ack'left-1 downto 0) & (bus_req_i.stb and bus_req_i.rw);

      -- read access --
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '0') then
        case bus_req_i.addr(3 downto 2) is
          when mode_addr_c => bus_rsp_o.data(1 downto 0)  <= crc.mode; -- mode select
          when poly_addr_c => bus_rsp_o.data(31 downto 0) <= crc.poly; -- polynomial
          when others      => bus_rsp_o.data(31 downto 0) <= crc.sreg; -- CRC result
        end case;
      end if;

    end if;
  end process bus_access;


  -- Bit-Serial CRC Core --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  crc_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      crc.cnt  <= (others => '1');
      crc.sreg <= (others => '0');
    elsif rising_edge(clk_i) then
      -- arbitration --
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(3 downto 2) = data_addr_c) then -- writing new data
        crc.cnt <= "0111"; -- start with MSB
      elsif (crc.cnt(3) = '0') then -- not done yet?
        crc.cnt <= std_ulogic_vector(unsigned(crc.cnt) - 1);
      end if;
      -- computation --
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(3 downto 2) = sreg_addr_c) then -- set start value
        crc.sreg <= bus_req_i.data;
      elsif (crc.cnt(3) = '0') then
        if (crc.msb = crc.data(to_integer(unsigned(crc.cnt(2 downto 0))))) then
          crc.sreg <= (crc.sreg(30 downto 0) & '0');
        else
          crc.sreg <= (crc.sreg(30 downto 0) & '0') xor crc.poly;
        end if;
      end if;
    end if;
  end process crc_core;

  -- operation mode --
  with crc.mode select crc.msb <=
    crc.sreg(7)  when "00",   -- crc8
    crc.sreg(15) when "01",   -- crc16
    crc.sreg(31) when others; -- crc32


end neorv32_crc_rtl;
