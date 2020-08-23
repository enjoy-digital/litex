--
-- This file is part of LiteX.
--
-- Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
-- SPDX-License-Identifier: BSD-2-Clause

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library work;
use work.common.all;
use work.wishbone_types.all;

entity microwatt_wrapper is
    generic (
        SIM             : boolean := false;
        DISABLE_FLATTEN : boolean := false
    );
    port (
        clk          : in std_logic;
        rst          : in std_logic;

        wishbone_insn_dat_r : in std_ulogic_vector(63 downto 0);
        wishbone_insn_ack   : in std_ulogic;
        wishbone_insn_stall : in std_ulogic;

        wishbone_insn_adr   : out std_ulogic_vector(31 downto 0);
        wishbone_insn_dat_w : out std_ulogic_vector(63 downto 0);
        wishbone_insn_cyc   : out std_ulogic;
        wishbone_insn_stb   : out std_ulogic;
        wishbone_insn_sel   : out std_ulogic_vector(7 downto 0);
        wishbone_insn_we    : out std_ulogic;

        wishbone_data_dat_r : in std_ulogic_vector(63 downto 0);
        wishbone_data_ack   : in std_ulogic;
        wishbone_data_stall : in std_ulogic;

        wishbone_data_adr   : out std_ulogic_vector(31 downto 0);
        wishbone_data_dat_w : out std_ulogic_vector(63 downto 0);
        wishbone_data_cyc   : out std_ulogic;
        wishbone_data_stb   : out std_ulogic;
        wishbone_data_sel   : out std_ulogic_vector(7 downto 0);
        wishbone_data_we    : out std_ulogic;

        dmi_addr : in  std_ulogic_vector(3 downto 0);
        dmi_din  : in  std_ulogic_vector(63 downto 0);
        dmi_dout : out std_ulogic_vector(63 downto 0);
        dmi_req  : in  std_ulogic;
        dmi_wr   : in  std_ulogic;
        dmi_ack  : out std_ulogic;

        terminated_out  : out std_logic
        );
end microwatt_wrapper;

architecture rtl of microwatt_wrapper is

    signal wishbone_insn_in  : wishbone_slave_out;
    signal wishbone_insn_out : wishbone_master_out;

    signal wishbone_data_in  : wishbone_slave_out;
    signal wishbone_data_out : wishbone_master_out;

    signal core_ext_irq 	     : std_ulogic;

begin

    -- wishbone_insn mapping
    wishbone_insn_in.dat   <= wishbone_insn_dat_r;
    wishbone_insn_in.ack   <= wishbone_insn_ack;
    wishbone_insn_in.stall <= wishbone_insn_stall;

    wishbone_insn_adr      <= wishbone_insn_out.adr;
    wishbone_insn_dat_w    <= wishbone_insn_out.dat;
    wishbone_insn_cyc      <= wishbone_insn_out.cyc;
    wishbone_insn_stb      <= wishbone_insn_out.stb;
    wishbone_insn_sel      <= wishbone_insn_out.sel;
    wishbone_insn_we       <= wishbone_insn_out.we;

    -- wishbone_data mapping
    wishbone_data_in.dat   <= wishbone_data_dat_r;
    wishbone_data_in.ack   <= wishbone_data_ack;
    wishbone_data_in.stall <= wishbone_data_stall;

    wishbone_data_adr      <= wishbone_data_out.adr;
    wishbone_data_dat_w    <= wishbone_data_out.dat;
    wishbone_data_cyc      <= wishbone_data_out.cyc;
    wishbone_data_stb      <= wishbone_data_out.stb;
    wishbone_data_sel      <= wishbone_data_out.sel;
    wishbone_data_we       <= wishbone_data_out.we;

    -- core_ext_irq mapping
    core_ext_irq <= '0';

    microwatt_core : entity work.core
        generic map (
            SIM             => SIM,
            DISABLE_FLATTEN => DISABLE_FLATTEN
        )
        port map (
            clk               => clk,
            rst               => rst,

            alt_reset         => '0',

            wishbone_insn_in  => wishbone_insn_in,
            wishbone_insn_out => wishbone_insn_out,

            wishbone_data_in  => wishbone_data_in,
            wishbone_data_out => wishbone_data_out,

            dmi_addr          => dmi_addr,
            dmi_din           => dmi_din,
            dmi_dout          => dmi_dout,
            dmi_req           => dmi_req,
            dmi_wr            => dmi_wr,
            dmi_ack           => dmi_ack,

            ext_irq           => core_ext_irq,

            terminated_out    => terminated_out
        );

end rtl;
