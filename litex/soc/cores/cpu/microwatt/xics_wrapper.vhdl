-- This file is Copyright (c) 2019 Florent Kermarrec <florent@enjoy-digital.fr>
--              Copyright (c) 2020 Raptor Engineering, LLC <sales@raptorengineering.com>
-- License: BSD

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library work;
use work.common.all;
use work.wishbone_types.all;

entity xics_icp_wrapper is
    port (
        clk            : in std_logic;
        rst            : in std_logic;

        wishbone_dat_r : out std_ulogic_vector(31 downto 0);
        wishbone_ack   : out std_ulogic;
        wishbone_stall : out std_ulogic;

        wishbone_adr   : in std_ulogic_vector(29 downto 0);
        wishbone_dat_w : in std_ulogic_vector(31 downto 0);
        wishbone_cyc   : in std_ulogic;
        wishbone_stb   : in std_ulogic;
        wishbone_sel   : in std_ulogic_vector(3 downto 0);
        wishbone_we    : in std_ulogic;

        ics_in_src     : in std_ulogic_vector(3 downto 0);
        ics_in_pri     : in std_ulogic_vector(7 downto 0);

        core_irq_out   : out std_ulogic
        );
end xics_icp_wrapper;

architecture rtl of xics_icp_wrapper is

    signal wishbone_in  : wb_io_master_out;
    signal wishbone_out : wb_io_slave_out;

    signal ics_in       : ics_to_icp_t;

begin
    -- wishbone mapping
    wishbone_dat_r    <= wishbone_out.dat;
    wishbone_ack      <= wishbone_out.ack;
    wishbone_stall    <= wishbone_out.stall;

    wishbone_in.adr   <= wishbone_adr(27 downto 0) & "00";
    wishbone_in.dat   <= wishbone_dat_w;
    wishbone_in.cyc   <= wishbone_cyc;
    wishbone_in.stb   <= wishbone_stb;
    wishbone_in.sel   <= wishbone_sel;
    wishbone_in.we    <= wishbone_we;

    ics_in.src        <= ics_in_src;
    ics_in.pri        <= ics_in_pri;

    xics_icp : entity work.xics_icp
        port map (
            clk               => clk,
            rst               => rst,

            wb_in             => wishbone_in,
            wb_out            => wishbone_out,

            ics_in            => ics_in,

            core_irq_out      => core_irq_out
        );

end rtl;

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library work;
use work.common.all;
use work.wishbone_types.all;

entity xics_ics_wrapper is
    port (
        clk            : in std_logic;
        rst            : in std_logic;

        wishbone_dat_r : out std_ulogic_vector(31 downto 0);
        wishbone_ack   : out std_ulogic;
        wishbone_stall : out std_ulogic;

        wishbone_adr   : in std_ulogic_vector(29 downto 0);
        wishbone_dat_w : in std_ulogic_vector(31 downto 0);
        wishbone_cyc   : in std_ulogic;
        wishbone_stb   : in std_ulogic;
        wishbone_sel   : in std_ulogic_vector(3 downto 0);
        wishbone_we    : in std_ulogic;

        int_level_in   : in std_ulogic_vector(31 downto 0);

        icp_out_src    : out std_ulogic_vector(3 downto 0);
        icp_out_pri    : out std_ulogic_vector(7 downto 0)
        );
end xics_ics_wrapper;

architecture rtl of xics_ics_wrapper is

    signal wishbone_in  : wb_io_master_out;
    signal wishbone_out : wb_io_slave_out;

    signal icp_out      : ics_to_icp_t;
    signal int_level_uw : std_ulogic_vector(15 downto 0);

begin
    -- wishbone mapping
    wishbone_dat_r    <= wishbone_out.dat;
    wishbone_ack      <= wishbone_out.ack;
    wishbone_stall    <= wishbone_out.stall;

    wishbone_in.adr   <= wishbone_adr(27 downto 0) & "00";
    wishbone_in.dat   <= wishbone_dat_w;
    wishbone_in.cyc   <= wishbone_cyc;
    wishbone_in.stb   <= wishbone_stb;
    wishbone_in.sel   <= wishbone_sel;
    wishbone_in.we    <= wishbone_we;

    icp_out_src       <= icp_out.src;
    icp_out_pri       <= icp_out.pri;

    -- Assign external interrupts
    interrupts: process(all)
    begin
        int_level_uw <= (others => '0');
        int_level_uw(0) <= int_level_in(0);
        int_level_uw(1) <= int_level_in(1);
        int_level_uw(2) <= int_level_in(2);
        int_level_uw(3) <= int_level_in(3);
        int_level_uw(4) <= int_level_in(4);
        int_level_uw(5) <= int_level_in(5);
        int_level_uw(6) <= int_level_in(6);
        int_level_uw(7) <= int_level_in(7);
        int_level_uw(8) <= int_level_in(8);
        int_level_uw(9) <= int_level_in(9);
        int_level_uw(10) <= int_level_in(10);
        int_level_uw(11) <= int_level_in(11);
        int_level_uw(12) <= int_level_in(12);
        int_level_uw(13) <= int_level_in(13);
        int_level_uw(14) <= int_level_in(14);
        int_level_uw(15) <= int_level_in(15);
    end process;

    xics_ics : entity work.xics_ics
        generic map (
            SRC_NUM           => 16
        )
        port map (
            clk               => clk,
            rst               => rst,

            wb_in             => wishbone_in,
            wb_out            => wishbone_out,

            int_level_in      => int_level_uw,
            icp_out           => icp_out
        );

end rtl;