-- ================================================================================ --
-- NEORV32 SoC - Interrupt-Capable General Purpose Input/Output Port (GPIO)         --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_gpio is
  generic (
    GPIO_NUM : natural range 0 to 32 -- number of GPIO input/output pairs
  );
  port (
    clk_i     : in  std_ulogic;                     -- global clock line
    rstn_i    : in  std_ulogic;                     -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;                      -- bus request
    bus_rsp_o : out bus_rsp_t;                      -- bus response
    gpio_o    : out std_ulogic_vector(31 downto 0); -- input port
    gpio_i    : in  std_ulogic_vector(31 downto 0); -- output port
    irq_o     : out std_ulogic                      -- CPU interrupt
  );
end neorv32_gpio;

architecture neorv32_gpio_rtl of neorv32_gpio is

  -- register addresses --
  constant addr_in_c  : std_ulogic_vector(2 downto 0) := "000"; -- r/-: input port
  constant addr_out_c : std_ulogic_vector(2 downto 0) := "001"; -- r/w: output port
  constant addr_tt_c  : std_ulogic_vector(2 downto 0) := "100"; -- r/w: trigger type (level/edge)
  constant addr_tp_c  : std_ulogic_vector(2 downto 0) := "101"; -- r/w: trigger polarity (high/low or rising/falling)
  constant addr_ie_c  : std_ulogic_vector(2 downto 0) := "110"; -- r/w: interrupt enable
  constant addr_ip_c  : std_ulogic_vector(2 downto 0) := "111"; -- r/c: interrupt pending

  -- interface registers --
  signal port_in, port_out, irq_typ, irq_pol, irq_en, irq_clrn : std_ulogic_vector(GPIO_NUM-1 downto 0);

  -- interrupt generator --
  signal port_in2, irq_trig, irq_pend : std_ulogic_vector(GPIO_NUM-1 downto 0);

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o <= rsp_terminate_c;
      port_out  <= (others => '0');
      irq_typ   <= (others => '0');
      irq_pol   <= (others => '0');
      irq_en    <= (others => '0');
      irq_clrn  <= (others => '0');
    elsif rising_edge(clk_i) then
      -- defaults --
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      irq_clrn       <= (others => '1');
      -- bus access --
      if (bus_req_i.stb = '1') then
        if (bus_req_i.rw = '1') then -- write access
          case bus_req_i.addr(4 downto 2) is
            when addr_out_c => port_out <= bus_req_i.data(GPIO_NUM-1 downto 0); -- output port
            when addr_tt_c  => irq_typ  <= bus_req_i.data(GPIO_NUM-1 downto 0); -- trigger type
            when addr_tp_c  => irq_pol  <= bus_req_i.data(GPIO_NUM-1 downto 0); -- trigger polarity
            when addr_ie_c  => irq_en   <= bus_req_i.data(GPIO_NUM-1 downto 0); -- interrupt enable
            when addr_ip_c  => irq_clrn <= bus_req_i.data(GPIO_NUM-1 downto 0); -- interrupt pending (clear-only)
            when others     => NULL;
          end case;
        else -- read access
          case bus_req_i.addr(4 downto 2) is
            when addr_out_c => bus_rsp_o.data(GPIO_NUM-1 downto 0) <= port_out; -- output port
            when addr_tt_c  => bus_rsp_o.data(GPIO_NUM-1 downto 0) <= irq_typ;  -- trigger type
            when addr_tp_c  => bus_rsp_o.data(GPIO_NUM-1 downto 0) <= irq_pol;  -- trigger polarity
            when addr_ie_c  => bus_rsp_o.data(GPIO_NUM-1 downto 0) <= irq_en;   -- interrupt enable
            when addr_ip_c  => bus_rsp_o.data(GPIO_NUM-1 downto 0) <= irq_pend; -- interrupt pending
            when others     => bus_rsp_o.data(GPIO_NUM-1 downto 0) <= port_in;  -- input port
          end case;
        end if;
      end if;
    end if;
  end process bus_access;

  -- input sampling --
  input_stage: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      port_in  <= (others => '0');
      port_in2 <= (others => '0');
    elsif rising_edge(clk_i) then
      port_in  <= gpio_i(GPIO_NUM-1 downto 0);
      port_in2 <= port_in;
    end if;
  end process input_stage;

  -- direct output --
  output_stage: process(port_out)
  begin
    gpio_o <= (others => '0');
    gpio_o(GPIO_NUM-1 downto 0) <= port_out;
  end process output_stage;


  -- IRQ Generator --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  irq_trigger_gen:
  for i in 0 to GPIO_NUM-1 generate
    irq_trigger: process(port_in, port_in2, irq_typ, irq_pol)
      variable sel_v : std_ulogic_vector(1 downto 0);
    begin
      sel_v := irq_typ(i) & irq_pol(i);
      case sel_v is
        when "00"   => irq_trig(i) <= not port_in(i); -- low-level
        when "01"   => irq_trig(i) <= port_in(i); -- high-level
        when "10"   => irq_trig(i) <= (not port_in(i)) and port_in2(i); -- falling-edge
        when "11"   => irq_trig(i) <= port_in(i) and (not port_in2(i)); -- rising-edge
        when others => irq_trig(i) <= '0';
      end case;
    end process irq_trigger;
  end generate;

  -- buffer pending interrupts until cleared or disabled --
  irq_buffer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq_pend <= (others => '0');
    elsif rising_edge(clk_i) then
      irq_pend <= irq_en and ((irq_pend and irq_clrn) or irq_trig);
    end if;
  end process irq_buffer;

  -- CPU interrupt --
  irq_o <= or_reduce_f(irq_pend);

end neorv32_gpio_rtl;
