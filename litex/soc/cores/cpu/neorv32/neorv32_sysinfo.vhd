-- ================================================================================ --
-- NEORV32 SoC - System Configuration Information Module (SYSINFO)                  --
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

entity neorv32_sysinfo is
  generic (
    BUS_TMO_INT       : natural; -- internal bus timeout value
    BUS_TMO_EXT       : natural; -- internal bus timeout value
    NUM_HARTS         : natural; -- number of physical CPU cores
    CLOCK_FREQUENCY   : natural; -- clock frequency of clk_i in Hz
    BOOT_MODE_SELECT  : natural; -- boot configuration select (default = 0 = bootloader)
    INT_BOOTLOADER_EN : boolean; -- boot configuration: true = boot explicit bootloader; false = boot from int/ext (I)MEM
    IMEM_EN           : boolean; -- implement processor-internal instruction memory
    IMEM_ROM          : boolean; -- implement processor-internal instruction memory as pre-initialized ROM
    IMEM_SIZE         : natural; -- size of processor-internal instruction memory in bytes
    DMEM_EN           : boolean; -- implement processor-internal data memory
    DMEM_SIZE         : natural; -- size of processor-internal data memory in bytes
    ICACHE_EN         : boolean; -- implement instruction cache
    ICACHE_NUM_BLOCKS : natural; -- i-cache: number of blocks (min 2), has to be a power of 2
    DCACHE_EN         : boolean; -- implement data cache
    DCACHE_NUM_BLOCKS : natural; -- d-cache: number of blocks (min 2), has to be a power of 2
    CACHE_BLOCK_SIZE  : natural; -- i-cache/d-cache: block size in bytes (min 4), has to be a power of 2
    CACHE_BURSTS_EN   : boolean; -- i-cache/d-cache: enable issuing of burst transfer for cache update
    XBUS_EN           : boolean; -- implement external memory bus interface
    OCD_EN            : boolean; -- implement OCD
    OCD_AUTH          : boolean; -- implement OCD authenticator
    IO_GPIO_EN        : boolean; -- implement general purpose IO port (GPIO)
    IO_CLINT_EN       : boolean; -- implement machine local interruptor (CLINT)
    IO_UART0_EN       : boolean; -- implement primary universal asynchronous receiver/transmitter (UART0)
    IO_UART1_EN       : boolean; -- implement secondary universal asynchronous receiver/transmitter (UART1)
    IO_SPI_EN         : boolean; -- implement serial peripheral interface (SPI)
    IO_SDI_EN         : boolean; -- implement serial data interface (SDI)
    IO_TWI_EN         : boolean; -- implement two-wire interface (TWI)
    IO_TWD_EN         : boolean; -- implement two-wire device (TWD)
    IO_PWM_EN         : boolean; -- implement pulse-width modulation controller (PWM)
    IO_WDT_EN         : boolean; -- implement watch dog timer (WDT)
    IO_TRNG_EN        : boolean; -- implement true random number generator (TRNG)
    IO_CFS_EN         : boolean; -- implement custom functions subsystem (CFS)
    IO_NEOLED_EN      : boolean; -- implement NeoPixel-compatible smart LED interface (NEOLED)
    IO_GPTMR_EN       : boolean; -- implement general purpose timer (GPTMR)
    IO_ONEWIRE_EN     : boolean; -- implement 1-wire interface (ONEWIRE)
    IO_DMA_EN         : boolean; -- implement direct memory access controller (DMA)
    IO_SLINK_EN       : boolean; -- implement stream link interface (SLINK)
    IO_TRACER_EN      : boolean  -- implement execution trace buffer (TRACER)
  );
  port (
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- global reset line, low-active, async
    bus_req_i : in  bus_req_t;  -- bus request
    bus_rsp_o : out bus_rsp_t   -- bus response
  );
end neorv32_sysinfo;

architecture neorv32_sysinfo_rtl of neorv32_sysinfo is

  -- helpers --
  constant int_imem_en_c    : boolean := IMEM_EN and boolean(IMEM_SIZE > 0);
  constant int_dmem_en_c    : boolean := DMEM_EN and boolean(DMEM_SIZE > 0);
  constant int_imem_rom_c   : boolean := int_imem_en_c and IMEM_ROM;
  constant log2_int_tmo_c   : natural := index_size_f(BUS_TMO_INT);
  constant log2_ext_tmo_c   : natural := index_size_f(BUS_TMO_EXT);
  constant log2_imem_size_c : natural := index_size_f(IMEM_SIZE);
  constant log2_dmem_size_c : natural := index_size_f(DMEM_SIZE);
  constant log2_ic_bnum_c   : natural := index_size_f(ICACHE_NUM_BLOCKS);
  constant log2_dc_bnum_c   : natural := index_size_f(DCACHE_NUM_BLOCKS);
  constant log2_c_bsize_c   : natural := index_size_f(CACHE_BLOCK_SIZE);

  -- system information memory --
  type sysinfo_t is array (0 to 3) of std_ulogic_vector(31 downto 0);
  signal sysinfo : sysinfo_t;

begin

  -- SYSINFO(0): Processor Clock Frequency --------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sysinfo_clk: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      sysinfo(0) <= std_ulogic_vector(to_unsigned(CLOCK_FREQUENCY, 32)); -- initialize from generic
    elsif rising_edge(clk_i) then
      if (bus_req_i.stb = '1') and (bus_req_i.rw = '1') and (bus_req_i.addr(3 downto 2) = "00") then
        sysinfo(0) <= bus_req_i.data;
      end if;
    end if;
  end process sysinfo_clk;

  -- SYSINFO(1): Misc -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sysinfo(1)(7  downto 0)  <= std_ulogic_vector(to_unsigned(log2_imem_size_c, 8)) when int_imem_en_c else (others => '0'); -- log2(IMEM size)
  sysinfo(1)(15 downto 8)  <= std_ulogic_vector(to_unsigned(log2_dmem_size_c, 8)) when int_dmem_en_c else (others => '0'); -- log2(DMEM size)
  sysinfo(1)(19 downto 16) <= std_ulogic_vector(to_unsigned(NUM_HARTS,        4)); -- number of physical CPU cores
  sysinfo(1)(21 downto 20) <= std_ulogic_vector(to_unsigned(BOOT_MODE_SELECT, 2)); -- boot configuration
  sysinfo(1)(26 downto 22) <= std_ulogic_vector(to_unsigned(log2_int_tmo_c,   5)); -- internal bus timeout
  sysinfo(1)(31 downto 27) <= std_ulogic_vector(to_unsigned(log2_ext_tmo_c,   5)); -- external bus timeout

  -- SYSINFO(2): SoC Configuration ----------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sysinfo(2)(0)  <= '1' when INT_BOOTLOADER_EN else '0'; -- processor-internal bootloader implemented
  sysinfo(2)(1)  <= '1' when XBUS_EN           else '0'; -- external bus interface implemented
  sysinfo(2)(2)  <= '1' when int_imem_en_c     else '0'; -- processor-internal instruction memory implemented
  sysinfo(2)(3)  <= '1' when int_dmem_en_c     else '0'; -- processor-internal data memory implemented
  sysinfo(2)(4)  <= '1' when OCD_EN            else '0'; -- on-chip debugger implemented
  sysinfo(2)(5)  <= '1' when ICACHE_EN         else '0'; -- processor-internal instruction cache implemented
  sysinfo(2)(6)  <= '1' when DCACHE_EN         else '0'; -- processor-internal data cache implemented
  sysinfo(2)(7)  <= '0';                                 -- reserved
  sysinfo(2)(8)  <= '0';                                 -- reserved
  sysinfo(2)(9)  <= '0';                                 -- reserved
  sysinfo(2)(10) <= '0';                                 -- reserved
  sysinfo(2)(11) <= '1' when OCD_AUTH          else '0'; -- on-chip debugger authentication implemented
  sysinfo(2)(12) <= '1' when int_imem_rom_c    else '0'; -- processor-internal instruction memory implemented as pre-initialized ROM
  sysinfo(2)(13) <= '1' when IO_TWD_EN         else '0'; -- two-wire device (TWD) implemented
  sysinfo(2)(14) <= '1' when IO_DMA_EN         else '0'; -- direct memory access controller (DMA) implemented
  sysinfo(2)(15) <= '1' when IO_GPIO_EN        else '0'; -- general purpose input/output port unit (GPIO) implemented
  sysinfo(2)(16) <= '1' when IO_CLINT_EN       else '0'; -- core local interruptor (CLINT) implemented
  sysinfo(2)(17) <= '1' when IO_UART0_EN       else '0'; -- primary universal asynchronous receiver/transmitter (UART0) implemented
  sysinfo(2)(18) <= '1' when IO_SPI_EN         else '0'; -- serial peripheral interface (SPI) implemented
  sysinfo(2)(19) <= '1' when IO_TWI_EN         else '0'; -- two-wire interface (TWI) implemented
  sysinfo(2)(20) <= '1' when IO_PWM_EN         else '0'; -- pulse-width modulation unit (PWM) implemented
  sysinfo(2)(21) <= '1' when IO_WDT_EN         else '0'; -- watch dog timer (WDT) implemented
  sysinfo(2)(22) <= '1' when IO_CFS_EN         else '0'; -- custom functions subsystem (CFS) implemented
  sysinfo(2)(23) <= '1' when IO_TRNG_EN        else '0'; -- true random number generator (TRNG) implemented
  sysinfo(2)(24) <= '1' when IO_SDI_EN         else '0'; -- serial data interface (SDI) implemented
  sysinfo(2)(25) <= '1' when IO_UART1_EN       else '0'; -- secondary universal asynchronous receiver/transmitter (UART1) implemented
  sysinfo(2)(26) <= '1' when IO_NEOLED_EN      else '0'; -- NeoPixel-compatible smart LED interface (NEOLED) implemented
  sysinfo(2)(27) <= '1' when IO_TRACER_EN      else '0'; -- execution trace buffer (TRACER) implemented
  sysinfo(2)(28) <= '1' when IO_GPTMR_EN       else '0'; -- general purpose timer (GPTMR) implemented
  sysinfo(2)(29) <= '1' when IO_SLINK_EN       else '0'; -- stream link interface (SLINK) implemented
  sysinfo(2)(30) <= '1' when IO_ONEWIRE_EN     else '0'; -- 1-wire interface (ONEWIRE) implemented
  sysinfo(2)(31) <= '1' when is_simulation_c   else '0'; -- You ever have that feeling where you're not sure if you're awake or still dreaming? - Neo, The Matrix

  -- SYSINFO(3): Cache Configuration --------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sysinfo(3)(3 downto 0)   <= std_ulogic_vector(to_unsigned(log2_c_bsize_c, 4)) when ICACHE_EN else (others => '0'); -- i-cache: log2(block_size_in_bytes)
  sysinfo(3)(7 downto 4)   <= std_ulogic_vector(to_unsigned(log2_ic_bnum_c, 4)) when ICACHE_EN else (others => '0'); -- i-cache: log2(number_of_block)
  --
  sysinfo(3)(11 downto 8)  <= std_ulogic_vector(to_unsigned(log2_c_bsize_c, 4)) when DCACHE_EN else (others => '0'); -- d-cache: log2(block_size)
  sysinfo(3)(15 downto 12) <= std_ulogic_vector(to_unsigned(log2_dc_bnum_c, 4)) when DCACHE_EN else (others => '0'); -- d-cache: log2(num_blocks)
  --
  sysinfo(3)(16) <= '1' when (ICACHE_EN and CACHE_BURSTS_EN) else '0'; -- i-cache: enable burst transfers
  sysinfo(3)(23 downto 17) <= (others => '0'); -- reserved
  --
  sysinfo(3)(24) <= '1' when (DCACHE_EN and CACHE_BURSTS_EN) else '0'; -- d-cache: enable burst transfers
  sysinfo(3)(31 downto 25) <= (others => '0'); -- reserved

  -- Bus Response ---------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  bus_response: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      bus_rsp_o <= rsp_terminate_c;
    elsif rising_edge(clk_i) then
      bus_rsp_o <= rsp_terminate_c; -- default
      if (bus_req_i.stb = '1') then
        bus_rsp_o.data <= sysinfo(to_integer(unsigned(bus_req_i.addr(3 downto 2))));
        bus_rsp_o.ack  <= '1';
        if (bus_req_i.rw = '1') and (bus_req_i.addr(3 downto 2) /= "00") then
          bus_rsp_o.err <= '1'; -- error if write access to any address other than zero
        end if;
      end if;
    end if;
  end process bus_response;

end neorv32_sysinfo_rtl;
