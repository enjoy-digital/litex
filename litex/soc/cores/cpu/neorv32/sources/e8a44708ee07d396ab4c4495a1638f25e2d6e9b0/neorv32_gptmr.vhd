-- ================================================================================ --
-- NEORV32 SoC - General Purpose Timer (GPTMR)                                      --
-- -------------------------------------------------------------------------------- --
-- Up to 16 individual timer slices providing 32-bit count and threshold registers. --
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
  generic (
    NUM_SLICES : natural range 0 to 16 -- number of timer slices
  );
  port (
    clk_i     : in  std_ulogic;                    -- global clock line
    rstn_i    : in  std_ulogic;                    -- global reset line, low-active
    bus_req_i : in  bus_req_t;                     -- bus request
    bus_rsp_o : out bus_rsp_t;                     -- bus response
    clkgen_i  : in  std_ulogic_vector(7 downto 0); -- prescaled clocks
    irq_o     : out std_ulogic                     -- timer match interrupt
  );
end neorv32_gptmr;

architecture neorv32_gptmr_rtl of neorv32_gptmr is

  -- counter slice --
  component neorv32_gptmr_slice
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    clken_i : in  std_ulogic;
    en_i    : in  std_ulogic;
    mode_i  : in  std_ulogic;
    cs_i    : in  std_ulogic;
    we_i    : in  std_ulogic;
    addr_i  : in  std_ulogic;
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0);
    irq_o   : out std_ulogic
  );
  end component;

  -- slice configuration --
  signal acc_addr : std_ulogic_vector(1 downto 0);
  signal clkprsc : std_ulogic_vector(2 downto 0);
  signal enable, mode, irq : std_ulogic_vector(NUM_SLICES-1 downto 0);

  -- slice wiring --
  type rdata_t is array (0 to NUM_SLICES-1) of std_ulogic_vector(31 downto 0);
  signal rdata : rdata_t;
  signal rdata_sum : std_ulogic_vector(31 downto 0);
  signal cs, trig : std_ulogic_vector(NUM_SLICES-1 downto 0);
  signal clken : std_ulogic;

begin

  -- Configuration Registers ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  control_regs: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      enable  <= (others => '0');
      mode    <= (others => '0');
      clkprsc <= (others => '0');
    elsif rising_edge(clk_i) then
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') then -- write access
        -- control and status register 0 (CSR0) --
        if (acc_addr = "00") then
          if (bus_req_i.ben(1 downto 0) = "11") then -- low half: per-slice enable
            enable <= bus_req_i.data((NUM_SLICES-1)+0 downto 0);
          end if;
          if (bus_req_i.ben(3 downto 2) = "11") then -- high half: per-slice mode
            mode <= bus_req_i.data((NUM_SLICES-1)+16 downto 16);
          end if;
        end if;
        -- control and status register 1 (CSR1) --
        if (acc_addr = "01") then
          if (bus_req_i.ben(3 downto 2) = "11") then -- high half: clock prescaler
            clkprsc <= bus_req_i.data(2 downto 0);
          end if;
        end if;
      end if;
    end if;
  end process control_regs;

  -- access helper --
  acc_addr <= bus_req_i.addr(7) & bus_req_i.addr(2);

  -- clock generator --
  clk_gen: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      clken <= '0';
    elsif rising_edge(clk_i) then
      clken <= clkgen_i(to_integer(unsigned(clkprsc)));
    end if;
  end process clk_gen;


  -- Bus (Read) Access ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o <= rsp_terminate_c;
    elsif rising_edge(clk_i) then
      bus_rsp_o.ack  <= bus_req_i.stb;
      bus_rsp_o.err  <= '0';
      bus_rsp_o.data <= (others => '0');
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '0') then -- read access
        case acc_addr is
          when "00" => -- CSR0
            bus_rsp_o.data((NUM_SLICES-1)+0 downto 0)   <= enable;
            bus_rsp_o.data((NUM_SLICES-1)+16 downto 16) <= mode;
          when "01" => -- CSR1
            bus_rsp_o.data((NUM_SLICES-1)+0 downto  0) <= irq;
            bus_rsp_o.data(18 downto 16)               <= clkprsc;
          when others => -- slice registers
            bus_rsp_o.data <= rdata_sum;
        end case;
      end if;
    end if;
  end process bus_access;


  -- Timer Slices ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  timer_slice_gen:
  for i in 0 to NUM_SLICES-1 generate
    neorv32_gptmr_slice_inst: neorv32_gptmr_slice
    port map (
      -- global control --
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      clken_i => clken,
      en_i    => enable(i),
      mode_i  => mode(i),
      -- register access --
      cs_i    => cs(i),
      we_i    => bus_req_i.rw,
      addr_i  => bus_req_i.addr(2),
      wdata_i => bus_req_i.data,
      rdata_o => rdata(i),
      -- IRQ output --
      irq_o   => trig(i)
    );
    cs(i) <= bus_req_i.stb when (bus_req_i.addr(7) = '1') and
                                (bus_req_i.addr(6 downto 3) = std_ulogic_vector(to_unsigned(i, 4))) else '0';
  end generate;

  -- channel read-back --
  read_back: process(rdata)
    variable tmp_v : std_ulogic_vector(31 downto 0);
  begin
    tmp_v := (others => '0');
    for i in 0 to NUM_SLICES-1 loop
      tmp_v := tmp_v or rdata(i);
    end loop;
    rdata_sum <= tmp_v;
  end process read_back;


  -- Interrupt Generator --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  irq_generator: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      irq <= (others => '0');
    elsif rising_edge(clk_i) then
      for i in 0 to NUM_SLICES-1 loop
        if (trig(i) = '1') and (enable(i) = '1') then
          irq(i) <= '1';
        elsif (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (acc_addr = "01") and
              (bus_req_i.data(i) = '0') then -- write 0 to clear/ACK
          irq(i) <= '0';
        end if;
      end loop;
    end if;
  end process irq_generator;

  -- CPU interrupt --
  irq_o <= or_reduce_f(irq and enable);

end neorv32_gptmr_rtl;


-- ================================================================================ --
-- NEORV32 SoC - General Purpose Timer (GPTMR) - Timer Slice                        --
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

entity neorv32_gptmr_slice is
  port (
    -- global control --
    clk_i   : in  std_ulogic;                     -- global clock line
    rstn_i  : in  std_ulogic;                     -- global reset line, low-active, async
    clken_i : in  std_ulogic;                     -- counter clock-enable
    en_i    : in  std_ulogic;                     -- slice enable
    mode_i  : in  std_ulogic;                     -- operation mode
    -- register access --
    cs_i    : in  std_ulogic;                     -- access enable
    we_i    : in  std_ulogic;                     -- write-enable
    addr_i  : in  std_ulogic;                     -- register select
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0); -- read data
    -- IRQ output --
    irq_o   : out std_ulogic                      -- counter reached zero
  );
end neorv32_gptmr_slice;

architecture neorv32_gptmr_slice_rtl of neorv32_gptmr_slice is

  signal thr, cnt : std_ulogic_vector(31 downto 0);
  signal match, trig : std_ulogic;

begin

  -- Counter Core ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cnt_core: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      thr  <= (others => '0');
      cnt  <= (others => '0');
      trig <= '0';
    elsif rising_edge(clk_i) then
      -- threshold value --
      if (cs_i = '1') and (we_i = '1') and (addr_i = '1') then
        thr <= wdata_i;
      end if;
      -- cycle counter --
      if (cs_i = '1') and (we_i = '1') and (addr_i = '0') then
        cnt <= wdata_i;
      elsif (en_i = '1') and (clken_i = '1') then
        if (match = '0') then
          cnt <= std_ulogic_vector(unsigned(cnt) + 1);
        elsif (mode_i = '1') then -- continuous mode
          cnt <= (others => '0');
        end if;
      end if;
      -- interrupt --
      trig <= match;
    end if;
  end process cnt_core;

  -- read-back --
  rdata_o <= (others => '0') when (cs_i = '0') else cnt when (addr_i = '0') else thr;

  -- match detector --
  match <= '1' when (cnt = thr) else '0';

  -- match interrupt --
  irq_o <= match and (not trig);

end neorv32_gptmr_slice_rtl;
