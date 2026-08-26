-- ================================================================================ --
-- NEORV32 SoC - General Purpose Timer (GPTMR)                                      --
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

entity neorv32_gptmr is
  port (
    clk_i       : in  std_ulogic; -- global clock line
    rstn_i      : in  std_ulogic; -- global reset line, low-active
    bus_req_i   : in  bus_req_t;  -- bus request
    bus_rsp_o   : out bus_rsp_t;  -- bus response
    clkgen_en_o : out std_ulogic; -- enable clock generator
    clkgen_i    : in  std_ulogic_vector(7 downto 0);
    irq_o       : out std_ulogic -- timer match interrupt
  );
end neorv32_gptmr;

architecture neorv32_gptmr_rtl of neorv32_gptmr is

  -- control register --
  constant ctrl_en_c      : natural := 0; -- r/w: global enable
  constant ctrl_prsc0_c   : natural := 1; -- r/w: clock prescaler select bit 0
  constant ctrl_prsc1_c   : natural := 2; -- r/w: clock prescaler select bit 1
  constant ctrl_prsc2_c   : natural := 3; -- r/w: clock prescaler select bit 2
  --
  constant ctrl_irq_clr_c : natural := 30; -- -/w: set to clear timer-match interrupt
  constant ctrl_irq_c     : natural := 31; -- r/-: timer-match interrupt pending
  --
  signal ctrl : std_ulogic_vector(3 downto 0);

  -- timer core --
  type timer_t is record
    tick  : std_ulogic; -- clock generator tick
    thres : std_ulogic_vector(31 downto 0); -- threshold register
    count : std_ulogic_vector(31 downto 0); -- counter register
    match : std_ulogic; -- counter register == threshold register
  end record;
  signal timer : timer_t;

  -- interrupt generator --
  signal irq_pnd, irq_clr : std_ulogic;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o   <= rsp_terminate_c;
      ctrl        <= (others => '0');
      timer.thres <= (others => '0');
      irq_clr     <= '0';
    elsif rising_edge(clk_i) then
      -- defaults --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0'; -- no access error possible
      bus_rsp_o.data <= (others => '0');
      irq_clr        <= '0';
      -- actual bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          if (bus_req_i.addr(3 downto 2) = "00") then -- control register
            ctrl(ctrl_en_c)    <= bus_req_i.data(ctrl_en_c);
            ctrl(ctrl_prsc0_c) <= bus_req_i.data(ctrl_prsc0_c);
            ctrl(ctrl_prsc1_c) <= bus_req_i.data(ctrl_prsc1_c);
            ctrl(ctrl_prsc2_c) <= bus_req_i.data(ctrl_prsc2_c);
            --
            irq_clr <= bus_req_i.data(ctrl_irq_clr_c);
          end if;
          if (bus_req_i.addr(3 downto 2) = "01") then -- threshold register
            timer.thres <= bus_req_i.data;
          end if;
        else -- read access
          case bus_req_i.addr(3 downto 2) is
            when "00" => -- control register
              bus_rsp_o.data(ctrl_en_c)    <= ctrl(ctrl_en_c);
              bus_rsp_o.data(ctrl_prsc0_c) <= ctrl(ctrl_prsc0_c);
              bus_rsp_o.data(ctrl_prsc1_c) <= ctrl(ctrl_prsc1_c);
              bus_rsp_o.data(ctrl_prsc2_c) <= ctrl(ctrl_prsc2_c);
              --
              bus_rsp_o.data(ctrl_irq_c) <= irq_pnd;
            when "01" => -- threshold register
              bus_rsp_o.data <= timer.thres;
            when others => -- counter register
              bus_rsp_o.data <= timer.count;
          end case;
        end if;
      end if;
    end if;
  end process bus_access;

  -- clock generator enable --
  clkgen_en_o <= ctrl(ctrl_en_c);


  -- Timer Core -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  timer_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      timer.tick  <= '0';
      timer.count <= (others => '0');
    elsif rising_edge(clk_i) then
      timer.tick <= clkgen_i(to_integer(unsigned(ctrl(ctrl_prsc2_c downto ctrl_prsc0_c)))); -- prescaler clock tick
      if (ctrl(ctrl_en_c) = '0') then -- timer disabled
        timer.count <= (others => '0');
      elsif (timer.tick = '1') then -- timer enabled and clock tick
        if (timer.match = '1') then
          timer.count <= (others => '0');
        else
          timer.count <= std_ulogic_vector(unsigned(timer.count) + 1);
        end if;
      end if;
    end if;
  end process timer_core;

  -- counter = threshold? --
  timer.match <= '1' when (timer.count = timer.thres) else '0';


  -- Interrupt Generator --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_pnd <= '0';
    elsif rising_edge(clk_i) then
      if (ctrl(ctrl_en_c) = '1') then
        if (timer.match = '1') then
          irq_pnd <= '1';
        elsif (irq_clr = '1') then
          irq_pnd <= '0';
        end if;
      else
        irq_pnd <= '0';
      end if;
    end if;
  end process irq_generator;

  -- interrupt request --
  irq_o <= irq_pnd;


end neorv32_gptmr_rtl;
