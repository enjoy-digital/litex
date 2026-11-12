-- ================================================================================ --
-- NEORV32 SoC - Custom Functions Subsystem (CFS)                                   --
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

entity neorv32_cfs is
  port (
    -- global control --
    clk_i     : in  std_ulogic; -- global clock line
    rstn_i    : in  std_ulogic; -- global reset line, low-active, async
    -- CPU access --
    bus_req_i : in  bus_req_t; -- bus request
    bus_rsp_o : out bus_rsp_t; -- bus response
    -- CPU interrupt --
    irq_o     : out std_ulogic; -- interrupt request
    -- external IO --
    cfs_in_i  : in  std_ulogic_vector(255 downto 0); -- custom inputs conduit
    cfs_out_o : out std_ulogic_vector(255 downto 0) -- custom outputs conduit
  );
end neorv32_cfs;

architecture neorv32_cfs_rtl of neorv32_cfs is

  -- exemplary CFS interface registers --
  type cfs_regs_t is array (0 to 3) of std_ulogic_vector(31 downto 0); -- implement 4 read/write registers
  signal cfs_reg_wr : cfs_regs_t; -- for WRITE accesses
  signal cfs_reg_rd : cfs_regs_t; -- for READ accesses

begin

  -- CFS IOs --------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- By default, the CFS provides two IO ports (cfs_in_i and cfs_out_o) that are available at the processor's top entity.
  -- These are intended as "conduits" to propagate custom CFS signals between the CFS and the processor top entity.

  cfs_out_o <= (others => '0'); -- not used for this minimal example


  -- Interrupt ------------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- The CFS features a single interrupt signal, which is connected to the CPU's "fast interrupt" channel 1 (FIRQ1).
  -- The according CPU interrupt becomes pending as long as <irq_o> is high.

  irq_o <= '0'; -- not used for this minimal example


  -- Read/Write Access ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- The CFS provides up to 64kB of memory-mapped address space (16 address bits, byte-addressing) that can be used
  -- for custom memories and interface registers. According to the CPU's bus protocol, each read or write access has
  -- to be acknowledged in the following cycle using the <bus_rsp_o.ack_o> signal (or even later if the module needs
  -- additional time to complete the access). If no ACK is generated, the bus access will time out causing a bus access
  -- fault exception.
  --
  -- [EXAMPLE] Read and write access to the interface registers and bus transfer acknowledge. This example only four
  -- physical 32-bit read/write register (using the four lowest CFS address bits). The remaining addresses of the CFS
  -- are not associated with any physical registers - any access to those is simply ignored but still acknowledged;
  -- read accesses will return zero. Only full-word write accesses are supported (and acknowledged) by this example.
  -- Sub-word write accesses are ignored.

  bus_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      cfs_reg_wr(0) <= (others => '0');
      cfs_reg_wr(1) <= (others => '0');
      cfs_reg_wr(2) <= (others => '0');
      cfs_reg_wr(3) <= (others => '0');
      bus_rsp_o     <= rsp_terminate_c;
    elsif rising_edge(clk_i) then -- synchronous interface for read and write accesses
      -- transfer/access acknowledge --
      bus_rsp_o.ack <= bus_req_i.stb; -- send ACK right after the access request
      bus_rsp_o.err <= '0'; -- set high together with bus_rsp_o.ack if there is an access error

      -- bus access --
      bus_rsp_o.data <= (others => '0'); -- the output HAS TO BE ZERO if there is no actual (read) access
      if (bus_req_i.stb = '1') then -- valid access cycle, STB is high for exactly one cycle

        -- write access (word-wise) --
        if (bus_req_i.rw = '1') then
          if (bus_req_i.addr(15 downto 2) = "00000000000000") then -- 16-bit byte address = 14-bit word address
            cfs_reg_wr(0) <= bus_req_i.data;
          end if;
          if (bus_req_i.addr(15 downto 2) = "00000000000001") then
            cfs_reg_wr(1) <= bus_req_i.data;
          end if;
          if (bus_req_i.addr(15 downto 2) = "00000000000010") then
            cfs_reg_wr(2) <= bus_req_i.data;
          end if;
          if (bus_req_i.addr(15 downto 2) = "00000000000011") then
            cfs_reg_wr(3) <= bus_req_i.data;
          end if;

        -- read access (word-wise) --
        else
          case bus_req_i.addr(15 downto 2) is -- 16-bit byte address = 14-bit word address
            when "00000000000000" => bus_rsp_o.data <= cfs_reg_rd(0);
            when "00000000000001" => bus_rsp_o.data <= cfs_reg_rd(1);
            when "00000000000010" => bus_rsp_o.data <= cfs_reg_rd(2);
            when "00000000000011" => bus_rsp_o.data <= cfs_reg_rd(3);
            when others           => bus_rsp_o.data <= (others => '0');
          end case;
        end if;

      end if;
    end if;
  end process bus_access;


  -- CFS Function Core ----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- This is where the actual functionality can be implemented. The logic below is just a very
  -- simple example that transforms data from an input register into data in an output register.

  cfs_reg_rd(0) <= x"0000000" & "000" & or_reduce_f(cfs_reg_wr(0)); -- OR all bits
  cfs_reg_rd(1) <= x"0000000" & "000" & xor_reduce_f(cfs_reg_wr(1)); -- XOR all bits
  cfs_reg_rd(2) <= bit_rev_f(cfs_reg_wr(2)); -- bit reversal
  cfs_reg_rd(3) <= (others => '1');


end neorv32_cfs_rtl;
