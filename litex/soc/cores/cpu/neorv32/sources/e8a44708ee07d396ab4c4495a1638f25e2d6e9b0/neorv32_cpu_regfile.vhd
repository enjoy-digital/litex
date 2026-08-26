-- ================================================================================ --
-- NEORV32 CPU - Data Register File                                                 --
-- -------------------------------------------------------------------------------- --
-- The architecture style of the register file is selected by the ARCH_SEL generic: --
-- 0: Register-based SRAM with sync. read (e.g. to map to FPGA block RAM)           --
-- 1: Register-based SRAM with async. read (e.g. to map to FPGA distributed RAM)    --
-- 2: Register-based with full hardware reset                                       --
-- 3: Latch-based (e.g. for ASIC implementation)                                    --
--                                                                                  --
-- [NOTE] Read-during-write behavior of the register file's memory core is          --
--        irrelevant as read and write accesses are mutually exclusive and          --
--        will never occur at the same time.                                        --
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

entity neorv32_cpu_regfile is
  generic (
    DWIDTH   : natural;             -- data width
    AWIDTH   : natural;             -- address width
    ARCH_SEL : natural range 0 to 3 -- architecture style select
  );
  port (
    -- global control --
    clk_i  : in  std_ulogic; -- global clock, rising edge
    rstn_i : in  std_ulogic; -- global reset, low-active, async
    ctrl_i : in  ctrl_bus_t; -- main control bus
    -- operands --
    rd_i   : in  std_ulogic_vector(DWIDTH-1 downto 0); -- destination data rd
    rs1_o  : out std_ulogic_vector(DWIDTH-1 downto 0); -- source data rs1
    rs2_o  : out std_ulogic_vector(DWIDTH-1 downto 0)  -- source data rs2
  );
end neorv32_cpu_regfile;

architecture neorv32_cpu_regfile_rtl of neorv32_cpu_regfile is

  -- access logic --
  signal rf_we  : std_ulogic;
  signal addr   : std_ulogic_vector(4 downto 0);
  signal wdata  : std_ulogic_vector(DWIDTH-1 downto 0);
  signal onehot : std_ulogic_vector((2**AWIDTH)-1 downto 0);

  -- memory core --
  type   regfile_t is array ((2**AWIDTH)-1 downto 0) of std_ulogic_vector(DWIDTH-1 downto 0);
  signal regfile : regfile_t;

begin

  -- Architecture Style 0: Register-Based SRAM with Synchronous Read ------------------------
  -- -------------------------------------------------------------------------------------------
  arch_sram_sync:
  if (ARCH_SEL = 0) generate

    -- Register zero (x0) is just another physical register that has to be initialized by the CPU control.
    -- Writes to x0 are inhibited unless the control forces a write (writing zero) to re-initialize x0.
    rf_we <= (ctrl_i.rf_wb_en and or_reduce_f(ctrl_i.rf_rd(AWIDTH-1 downto 0))) or ctrl_i.rf_zero;
    addr  <= (others => '0') when (ctrl_i.rf_zero  = '1') else -- force rd = zero
             ctrl_i.rf_rd    when (ctrl_i.rf_wb_en = '1') else ctrl_i.rf_rs1; -- multiplexed rd/rs1

    -- synchronous write & read (SDPRAM) --
    rf_access: process(clk_i)
    begin
      if rising_edge(clk_i) then
        if (rf_we = '1') then
          regfile(to_integer(unsigned(addr(AWIDTH-1 downto 0)))) <= rd_i;
        else
          rs1_o <= regfile(to_integer(unsigned(addr(AWIDTH-1 downto 0))));
        end if;
        rs2_o <= regfile(to_integer(unsigned(ctrl_i.rf_rs2(AWIDTH-1 downto 0))));
      end if;
    end process rf_access;

    -- unused --
    wdata  <= (others => '0');
    onehot <= (others => '0');

  end generate;


  -- Architecture Style 1: Register-Based SRAM with Asynchronous Read -----------------------
  -- -------------------------------------------------------------------------------------------
  arch_sram_async:
  if (ARCH_SEL = 1) generate

    -- multiplexed rd/rs1 address to map to SDPRAM --
    addr <= ctrl_i.rf_rd when (ctrl_i.rf_wb_en = '1') else ctrl_i.rf_rs1;

    -- synchronous write --
    rf_write: process(clk_i)
    begin
      if rising_edge(clk_i) then
        if (ctrl_i.rf_wb_en = '1') then
          regfile(to_integer(unsigned(addr(AWIDTH-1 downto 0)))) <= rd_i;
        end if;
      end if;
    end process rf_write;

    -- asynchronous read + zero-insertion + output-register --
    rf_read: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        rs1_o <= (others => '0');
        rs2_o <= (others => '0');
      elsif rising_edge(clk_i) then
        if (ctrl_i.rf_rs1 = "00000") then -- reading x0
          rs1_o <= (others => '0');
        else
          rs1_o <= regfile(to_integer(unsigned(addr(AWIDTH-1 downto 0))));
        end if;
        if (ctrl_i.rf_rs2 = "00000") then -- reading x0
          rs2_o <= (others => '0');
        else
          rs2_o <= regfile(to_integer(unsigned(ctrl_i.rf_rs2(AWIDTH-1 downto 0))));
        end if;
      end if;
    end process rf_read;

    -- unused --
    rf_we  <= '0';
    wdata  <= (others => '0');
    onehot <= (others => '0');

  end generate;


  -- Architecture Style 2: Register-Based with Hardware Reset -------------------------------
  -- -------------------------------------------------------------------------------------------
  arch_reg:
  if (ARCH_SEL = 2) generate

    -- write select --
    onehot_gen:
    for i in 0 to (2**AWIDTH)-1 generate
      onehot(i) <= ctrl_i.rf_wb_en when (unsigned(ctrl_i.rf_rd(AWIDTH-1 downto 0)) = to_unsigned(i, AWIDTH)) else '0';
    end generate;

    -- individual registers --
    regfile_gen:
    for i in 1 to (2**AWIDTH)-1 generate
      rf_write: process(rstn_i, clk_i)
      begin
        if (rstn_i = '0') then
          regfile(i) <= (others => '0');
        elsif rising_edge(clk_i) then
          if (onehot(i) = '1') then
            regfile(i) <= rd_i;
          end if;
        end if;
      end process rf_write;
    end generate;
    regfile(0) <= (others => '0'); -- x0 is hardwired to zero

    -- synchronous read --
    rf_read: process(clk_i)
    begin
      if rising_edge(clk_i) then
        rs1_o <= regfile(to_integer(unsigned(ctrl_i.rf_rs1(AWIDTH-1 downto 0))));
        rs2_o <= regfile(to_integer(unsigned(ctrl_i.rf_rs2(AWIDTH-1 downto 0))));
      end if;
    end process rf_read;

    -- unused --
    rf_we <= '0';
    addr  <= (others => '0');
    wdata <= (others => '0');

  end generate;


  -- Architecture Style 3: Latch-Based ------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  arch_latch:
  if (ARCH_SEL = 3) generate

    -- write buffer --
    rf_write: process(clk_i)
    begin
      if rising_edge(clk_i) then
        -- input register --
        if (ctrl_i.rf_wb_en = '1') then
          wdata <= rd_i;
        end if;
        -- one-hot decoder --
        onehot <= (others => '0');
        for i in 0 to (2**AWIDTH)-1 loop
          if (unsigned(ctrl_i.rf_rd(AWIDTH-1 downto 0)) = to_unsigned(i, AWIDTH)) then
            onehot(i) <= ctrl_i.rf_wb_en;
          end if;
        end loop;
      end if;
    end process rf_write;

    -- individual latches (transparent when clock is LOW) --
    regfile_gen:
    for i in 1 to (2**AWIDTH)-1 generate
      regfile(i) <= wdata when (clk_i = '0') and (onehot(i) = '1') else regfile(i);
    end generate;
    regfile(0) <= (others => '0'); -- x0 is hardwired to zero

    -- synchronous read --
    rf_read: process(clk_i)
    begin
      if rising_edge(clk_i) then
        rs1_o <= regfile(to_integer(unsigned(ctrl_i.rf_rs1(AWIDTH-1 downto 0))));
        rs2_o <= regfile(to_integer(unsigned(ctrl_i.rf_rs2(AWIDTH-1 downto 0))));
      end if;
    end process rf_read;

    -- unused --
    rf_we <= '0';
    addr  <= (others => '0');

  end generate;

end neorv32_cpu_regfile_rtl;
