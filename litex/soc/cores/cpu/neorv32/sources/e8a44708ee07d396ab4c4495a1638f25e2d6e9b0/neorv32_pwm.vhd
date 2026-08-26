-- ================================================================================ --
-- NEORV32 SoC - Pulse Width Modulation Controller (PWM)                            --
-- -------------------------------------------------------------------------------- --
-- Provides up to 32 individual fast-PWM / phase-correct channels with a resolution --
-- of 16-bit and programmable polarity. All counters use a global clock-prescaler.  --
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

entity neorv32_pwm is
  generic (
    NUM_CHANNELS : natural range 0 to 32 -- number of PWM channels (0..16)
  );
  port (
    clk_i     : in  std_ulogic;                    -- global clock line
    rstn_i    : in  std_ulogic;                    -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;                     -- bus request
    bus_rsp_o : out bus_rsp_t;                     -- bus response
    clkgen_i  : in  std_ulogic_vector(7 downto 0); -- clock divider input
    pwm_o     : out std_ulogic_vector(31 downto 0) -- PWM output
  );
end neorv32_pwm;

architecture neorv32_pwm_rtl of neorv32_pwm is

  -- PWM channel controller --
  component neorv32_pwm_channel
  port (
    clk_i   : in  std_ulogic;
    rstn_i  : in  std_ulogic;
    clken_i : in  std_ulogic;
    en_i    : in  std_ulogic;
    pol_i   : in  std_ulogic;
    mode_i  : in  std_ulogic;
    cs_i    : in  std_ulogic;
    we_i    : in  std_ulogic;
    ben_i   : in  std_ulogic_vector(3 downto 0);
    wdata_i : in  std_ulogic_vector(31 downto 0);
    rdata_o : out std_ulogic_vector(31 downto 0);
    wrap_o  : out std_ulogic;
    pwm_o   : out std_ulogic
  );
  end component;

  -- global control --
  signal enable, polarity, mode : std_ulogic_vector(NUM_CHANNELS-1 downto 0);
  signal clkprsc, addr : std_ulogic_vector(2 downto 0);

  -- wiring --
  type rdata_t is array (0 to NUM_CHANNELS-1) of std_ulogic_vector(31 downto 0);
  signal rdata : rdata_t;
  signal rdata_sum : std_ulogic_vector(31 downto 0);
  signal cs, pwm : std_ulogic_vector(NUM_CHANNELS-1 downto 0);
  signal clken : std_ulogic;

begin

  -- Bus Access -----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o <= rsp_terminate_c;
      enable    <= (others => '0');
      polarity  <= (others => '0');
      clkprsc   <= (others => '0');
      mode      <= (others => '0');
    elsif rising_edge(clk_i) then
      -- handshake --
      bus_rsp_o.ack <= bus_req_i.stb;
      bus_rsp_o.err <= '0';
      -- write access --
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') then
        if (addr = "000") then
          enable <= bus_req_i.data(NUM_CHANNELS-1 downto 0);
        end if;
        if (addr = "001") then
          polarity <= bus_req_i.data(NUM_CHANNELS-1 downto 0);
        end if;
        if (addr = "010") then
          clkprsc <= bus_req_i.data(2 downto 0);
        end if;
        if (addr = "011") then
          mode <= bus_req_i.data(NUM_CHANNELS-1 downto 0);
        end if;
      end if;
      -- read access --
      bus_rsp_o.data <= (others => '0');
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '0') then
        case addr is
          when "000"  => bus_rsp_o.data(NUM_CHANNELS-1 downto 0) <= enable;
          when "001"  => bus_rsp_o.data(NUM_CHANNELS-1 downto 0) <= polarity;
          when "010"  => bus_rsp_o.data(2 downto 0) <= clkprsc;
          when "011"  => bus_rsp_o.data(NUM_CHANNELS-1 downto 0) <= mode;
          when others => bus_rsp_o.data <= rdata_sum;
        end case;
      end if;
    end if;
  end process bus_access;

  -- access address helper --
  addr <= bus_req_i.addr(7) & bus_req_i.addr(3 downto 2);

  -- Channel Controllers --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  pwm_channel_gen:
  for i in 0 to NUM_CHANNELS-1 generate
    neorv32_pwm_channel_inst: neorv32_pwm_channel
    port map (
      -- global control --
      clk_i   => clk_i,
      rstn_i  => rstn_i,
      clken_i => clken,
      en_i    => enable(i),
      pol_i   => polarity(i),
      mode_i  => mode(i),
      -- register access --
      cs_i    => cs(i),
      we_i    => bus_req_i.rw,
      ben_i   => bus_req_i.ben,
      wdata_i => bus_req_i.data,
      rdata_o => rdata(i),
      -- PWM output --
      wrap_o  => open, -- [TODO] use this as interrupt trigger?
      pwm_o   => pwm(i)
    );
    cs(i) <= bus_req_i.stb when (bus_req_i.addr(7) = '1') and
                                (bus_req_i.addr(6 downto 2) = std_ulogic_vector(to_unsigned(i, 5))) else '0';
  end generate;

  -- clock generator --
  clk_gen: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      clken <= '0';
    elsif rising_edge(clk_i) then
      clken <= clkgen_i(to_integer(unsigned(clkprsc)));
    end if;
  end process clk_gen;

  -- channel read-back --
  read_back: process(rdata)
    variable tmp_v : std_ulogic_vector(31 downto 0);
  begin
    tmp_v := (others => '0');
    for i in 0 to NUM_CHANNELS-1 loop
      tmp_v := tmp_v or rdata(i);
    end loop;
    rdata_sum <= tmp_v;
  end process read_back;

  -- PWM output --
  channel_output: process(pwm)
  begin
    pwm_o <= (others => '0');
    pwm_o(NUM_CHANNELS-1 downto 0) <= pwm;
  end process channel_output;

end neorv32_pwm_rtl;


-- ================================================================================ --
-- NEORV32 SoC - Pulse Width Modulation Controller (PWM) - Channel Controller       --
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

entity neorv32_pwm_channel is
  port (
    -- global control --
    clk_i   : in  std_ulogic;                     -- global clock line
    rstn_i  : in  std_ulogic;                     -- global reset line, low-active, async
    clken_i : in  std_ulogic;                     -- clock divider input
    en_i    : in  std_ulogic;                     -- channel enable
    pol_i   : in  std_ulogic;                     -- output polarity
    mode_i  : in  std_ulogic;                     -- operation mode
    -- register access --
    cs_i    : in  std_ulogic;                     -- access enable
    we_i    : in  std_ulogic;                     -- write-enable
    ben_i   : in  std_ulogic_vector(3 downto 0);  -- byte-enable
    wdata_i : in  std_ulogic_vector(31 downto 0); -- write data
    rdata_o : out std_ulogic_vector(31 downto 0); -- read data
    -- PWM output --
    wrap_o  : out std_ulogic;                     -- counter wrap
    pwm_o   : out std_ulogic                      -- PWM output
  );
end neorv32_pwm_channel;

architecture neorv32_pwm_channel_rtl of neorv32_pwm_channel is

  signal cnt, cmp, top : std_ulogic_vector(15 downto 0);
  signal dir, cmp_zero, cmp_top : std_ulogic;

begin

  -- Register Interface ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      cmp <= (others => '0');
      top <= (others => '0');
    elsif rising_edge(clk_i) then
      if (cs_i = '1') and (we_i = '1') then
        if (ben_i(1 downto 0) = "11") then
          cmp <= wdata_i(15 downto 0);
        end if;
        if (ben_i(3 downto 2) = "11") then
          top <= wdata_i(31 downto 16);
        end if;
      end if;
    end if;
  end process write_access;

  -- read-back --
  rdata_o <= (top & cmp) when (cs_i = '1') else (others => '0');

  -- PWM Counter ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  pwm_counter: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      dir <= '0';
      cnt <= (others => '0');
    elsif rising_edge(clk_i) then
      if (en_i = '0') then
        dir <= '0';
        cnt <= (others => '0');
      else
        dir <= (dir or cmp_top) and (not cmp_zero) and mode_i; -- boolean magic
        if (clken_i = '1') then
          if (mode_i = '0') and (cmp_top = '1') then -- fast-PWM wrap
            cnt <= (others => '0');
          elsif (dir = '0') then
            cnt <= std_ulogic_vector(unsigned(cnt) + 1);
          else
            cnt <= std_ulogic_vector(unsigned(cnt) - 1);
          end if;
        end if;
      end if;
    end if;
  end process pwm_counter;

  -- comparators --
  cmp_zero <= '1' when (cnt = x"0000") else '0';
  cmp_top  <= '1' when (cnt = top)     else '0';
  wrap_o   <= cmp_top;

  -- Output / Duty Cycle Control ------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  pwm_drive: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      pwm_o <= '0';
    elsif rising_edge(clk_i) then
      if (en_i = '0') then
        pwm_o <= '0';
      elsif (unsigned(cnt) < unsigned(cmp)) then
        pwm_o <= not pol_i;
      else
        pwm_o <= pol_i;
      end if;
    end if;
  end process pwm_drive;

end neorv32_pwm_channel_rtl;
