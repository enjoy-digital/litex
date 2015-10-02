# tCK=5ns CL=7 CWL=6

from migen import *

from misoc.interconnect.dfi import *
from misoc.interconnect.csr import *
from misoc.cores import sdram_settings


class K7DDRPHY(Module, AutoCSR):
    def __init__(self, pads):
        addressbits = len(pads.a)
        bankbits = len(pads.ba)
        databits = len(pads.dq)
        nphases = 4

        self._wlevel_en = CSRStorage()
        self._wlevel_strobe = CSR()
        self._dly_sel = CSRStorage(databits//8)
        self._rdly_dq_rst = CSR()
        self._rdly_dq_inc = CSR()
        self._rdly_dq_bitslip = CSR()
        self._wdly_dq_rst = CSR()
        self._wdly_dq_inc = CSR()
        self._wdly_dqs_rst = CSR()
        self._wdly_dqs_inc = CSR()

        self.settings = sdram_settings.PhySettings(
            memtype="DDR3",
            dfi_databits=2*databits,
            nphases=nphases,
            rdphase=0,
            wrphase=2,
            rdcmdphase=1,
            wrcmdphase=0,
            cl=7,
            cwl=6,
            read_latency=6,
            write_latency=2
        )

        self.dfi = Interface(addressbits, bankbits, 2*databits, nphases)

        ###

        # Clock
        sd_clk_se = Signal()
        self.specials += [
            Instance("OSERDESE2",
                     p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                     p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                     p_SERDES_MODE="MASTER",

                     o_OQ=sd_clk_se,
                     i_OCE=1,
                     i_RST=ResetSignal(),
                     i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                     i_D1=0, i_D2=1, i_D3=0, i_D4=1,
                     i_D5=0, i_D6=1, i_D7=0, i_D8=1
            ),
            Instance("OBUFDS",
                     i_I=sd_clk_se,
                     o_O=pads.clk_p,
                     o_OB=pads.clk_n
            )
        ]

        # Addresses and commands
        for i in range(addressbits):
            self.specials += \
                Instance("OSERDESE2",
                         p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                         p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                         p_SERDES_MODE="MASTER",

                         o_OQ=pads.a[i],
                         i_OCE=1,
                         i_RST=ResetSignal(),
                         i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_D1=self.dfi.phases[0].address[i], i_D2=self.dfi.phases[0].address[i],
                         i_D3=self.dfi.phases[1].address[i], i_D4=self.dfi.phases[1].address[i],
                         i_D5=self.dfi.phases[2].address[i], i_D6=self.dfi.phases[2].address[i],
                         i_D7=self.dfi.phases[3].address[i], i_D8=self.dfi.phases[3].address[i]
                )
        for i in range(bankbits):
            self.specials += \
                Instance("OSERDESE2",
                         p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                         p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                         p_SERDES_MODE="MASTER",

                         o_OQ=pads.ba[i],
                         i_OCE=1,
                         i_RST=ResetSignal(),
                         i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_D1=self.dfi.phases[0].bank[i], i_D2=self.dfi.phases[0].bank[i],
                         i_D3=self.dfi.phases[1].bank[i], i_D4=self.dfi.phases[1].bank[i],
                         i_D5=self.dfi.phases[2].bank[i], i_D6=self.dfi.phases[2].bank[i],
                         i_D7=self.dfi.phases[3].bank[i], i_D8=self.dfi.phases[3].bank[i]
                )
        for name in "ras_n", "cas_n", "we_n", "cs_n", "cke", "odt", "reset_n":
            self.specials += \
                Instance("OSERDESE2",
                         p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                         p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                         p_SERDES_MODE="MASTER",

                         o_OQ=getattr(pads, name),
                         i_OCE=1,
                         i_RST=ResetSignal(),
                         i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_D1=getattr(self.dfi.phases[0], name), i_D2=getattr(self.dfi.phases[0], name),
                         i_D3=getattr(self.dfi.phases[1], name), i_D4=getattr(self.dfi.phases[1], name),
                         i_D5=getattr(self.dfi.phases[2], name), i_D6=getattr(self.dfi.phases[2], name),
                         i_D7=getattr(self.dfi.phases[3], name), i_D8=getattr(self.dfi.phases[3], name)
                )

        # DQS and DM
        oe_dqs = Signal()
        dqs_serdes_pattern = Signal(8)
        self.comb += \
            If(self._wlevel_en.storage,
                If(self._wlevel_strobe.re,
                    dqs_serdes_pattern.eq(0b00000001)
                ).Else(
                    dqs_serdes_pattern.eq(0b00000000)
                )
            ).Else(
                dqs_serdes_pattern.eq(0b01010101)
            )
        for i in range(databits//8):
            dm_o_nodelay = Signal()
            self.specials += \
                Instance("OSERDESE2",
                         p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                         p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                         p_SERDES_MODE="MASTER",

                         o_OQ=dm_o_nodelay,
                         i_OCE=1,
                         i_RST=ResetSignal(),
                         i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_D1=self.dfi.phases[0].wrdata_mask[i], i_D2=self.dfi.phases[0].wrdata_mask[databits//8+i],
                         i_D3=self.dfi.phases[1].wrdata_mask[i], i_D4=self.dfi.phases[1].wrdata_mask[databits//8+i],
                         i_D5=self.dfi.phases[2].wrdata_mask[i], i_D6=self.dfi.phases[2].wrdata_mask[databits//8+i],
                         i_D7=self.dfi.phases[3].wrdata_mask[i], i_D8=self.dfi.phases[3].wrdata_mask[databits//8+i]
                )
            self.specials += \
                Instance("ODELAYE2",
                         p_DELAY_SRC="ODATAIN", p_SIGNAL_PATTERN="DATA",
                         p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
                         p_PIPE_SEL="FALSE", p_ODELAY_TYPE="VARIABLE", p_ODELAY_VALUE=0,

                         i_C=ClockSignal(),
                         i_LD=self._dly_sel.storage[i] & self._wdly_dq_rst.re,
                         i_CE=self._dly_sel.storage[i] & self._wdly_dq_inc.re,
                         i_LDPIPEEN=0, i_INC=1,

                         o_ODATAIN=dm_o_nodelay, o_DATAOUT=pads.dm[i]
                )

            dqs_nodelay = Signal()
            dqs_delayed = Signal()
            dqs_t = Signal()
            self.specials += [
                Instance("OSERDESE2",
                         p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                         p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                         p_SERDES_MODE="MASTER",

                         o_OFB=dqs_nodelay, o_TQ=dqs_t,
                         i_OCE=1, i_TCE=1,
                         i_RST=ResetSignal(),
                         i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_D1=dqs_serdes_pattern[0], i_D2=dqs_serdes_pattern[1],
                         i_D3=dqs_serdes_pattern[2], i_D4=dqs_serdes_pattern[3],
                         i_D5=dqs_serdes_pattern[4], i_D6=dqs_serdes_pattern[5],
                         i_D7=dqs_serdes_pattern[6], i_D8=dqs_serdes_pattern[7],
                         i_T1=~oe_dqs
                ),
                Instance("ODELAYE2",
                         p_DELAY_SRC="ODATAIN", p_SIGNAL_PATTERN="DATA",
                         p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
                         p_PIPE_SEL="FALSE", p_ODELAY_TYPE="VARIABLE", p_ODELAY_VALUE=6,

                         i_C=ClockSignal(),
                         i_LD=self._dly_sel.storage[i] & self._wdly_dqs_rst.re,
                         i_CE=self._dly_sel.storage[i] & self._wdly_dqs_inc.re,
                         i_LDPIPEEN=0, i_INC=1,

                         o_ODATAIN=dqs_nodelay, o_DATAOUT=dqs_delayed
                ),
                Instance("OBUFTDS",
                         i_I=dqs_delayed, i_T=dqs_t,
                         o_O=pads.dqs_p[i], o_OB=pads.dqs_n[i]
                )
            ]

        # DQ
        oe_dq = Signal()
        for i in range(databits):
            dq_o_nodelay = Signal()
            dq_o_delayed = Signal()
            dq_i_nodelay = Signal()
            dq_i_delayed = Signal()
            dq_t = Signal()
            self.specials += [
                Instance("OSERDESE2",
                         p_DATA_WIDTH=8, p_TRISTATE_WIDTH=1,
                         p_DATA_RATE_OQ="DDR", p_DATA_RATE_TQ="BUF",
                         p_SERDES_MODE="MASTER",

                         o_OQ=dq_o_nodelay, o_TQ=dq_t,
                         i_OCE=1, i_TCE=1,
                         i_RST=ResetSignal(),
                         i_CLK=ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_D1=self.dfi.phases[0].wrdata[i], i_D2=self.dfi.phases[0].wrdata[databits+i],
                         i_D3=self.dfi.phases[1].wrdata[i], i_D4=self.dfi.phases[1].wrdata[databits+i],
                         i_D5=self.dfi.phases[2].wrdata[i], i_D6=self.dfi.phases[2].wrdata[databits+i],
                         i_D7=self.dfi.phases[3].wrdata[i], i_D8=self.dfi.phases[3].wrdata[databits+i],
                         i_T1=~oe_dq
                ),
                Instance("ISERDESE2",
                         p_DATA_WIDTH=8, p_DATA_RATE="DDR",
                         p_SERDES_MODE="MASTER", p_INTERFACE_TYPE="NETWORKING",
                         p_NUM_CE=1, p_IOBDELAY="IFD",

                         i_DDLY=dq_i_delayed,
                         i_CE1=1,
                         i_RST=ResetSignal() | (self._dly_sel.storage[i//8] & self._wdly_dq_rst.re),
                         i_CLK=ClockSignal("sys4x"), i_CLKB=~ClockSignal("sys4x"), i_CLKDIV=ClockSignal(),
                         i_BITSLIP=self._dly_sel.storage[i//8] & self._rdly_dq_bitslip.re,
                         o_Q8=self.dfi.phases[0].rddata[i], o_Q7=self.dfi.phases[0].rddata[databits+i],
                         o_Q6=self.dfi.phases[1].rddata[i], o_Q5=self.dfi.phases[1].rddata[databits+i],
                         o_Q4=self.dfi.phases[2].rddata[i], o_Q3=self.dfi.phases[2].rddata[databits+i],
                         o_Q2=self.dfi.phases[3].rddata[i], o_Q1=self.dfi.phases[3].rddata[databits+i]
                ),
                Instance("ODELAYE2",
                         p_DELAY_SRC="ODATAIN", p_SIGNAL_PATTERN="DATA",
                         p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
                         p_PIPE_SEL="FALSE", p_ODELAY_TYPE="VARIABLE", p_ODELAY_VALUE=0,

                         i_C=ClockSignal(),
                         i_LD=self._dly_sel.storage[i//8] & self._wdly_dq_rst.re,
                         i_CE=self._dly_sel.storage[i//8] & self._wdly_dq_inc.re,
                         i_LDPIPEEN=0, i_INC=1,

                         o_ODATAIN=dq_o_nodelay, o_DATAOUT=dq_o_delayed
                ),
                Instance("IDELAYE2",
                         p_DELAY_SRC="IDATAIN", p_SIGNAL_PATTERN="DATA",
                         p_CINVCTRL_SEL="FALSE", p_HIGH_PERFORMANCE_MODE="TRUE", p_REFCLK_FREQUENCY=200.0,
                         p_PIPE_SEL="FALSE", p_IDELAY_TYPE="VARIABLE", p_IDELAY_VALUE=6,

                         i_C=ClockSignal(),
                         i_LD=self._dly_sel.storage[i//8] & self._rdly_dq_rst.re,
                         i_CE=self._dly_sel.storage[i//8] & self._rdly_dq_inc.re,
                         i_LDPIPEEN=0, i_INC=1,

                         i_IDATAIN=dq_i_nodelay, o_DATAOUT=dq_i_delayed
                ),
                Instance("IOBUF",
                         i_I=dq_o_delayed, o_O=dq_i_nodelay, i_T=dq_t,
                         io_IO=pads.dq[i]
                )
            ]

        # Flow control
        #
        # total read latency = 6:
        #  2 cycles through OSERDESE2
        #  2 cycles CAS
        #  2 cycles through ISERDESE2
        rddata_en = self.dfi.phases[self.settings.rdphase].rddata_en
        for i in range(5):
            n_rddata_en = Signal()
            self.sync += n_rddata_en.eq(rddata_en)
            rddata_en = n_rddata_en
        self.sync += [phase.rddata_valid.eq(rddata_en | self._wlevel_en.storage)
            for phase in self.dfi.phases]

        oe = Signal()
        last_wrdata_en = Signal(4)
        wrphase = self.dfi.phases[self.settings.wrphase]
        self.sync += last_wrdata_en.eq(Cat(wrphase.wrdata_en, last_wrdata_en[:3]))
        self.comb += oe.eq(last_wrdata_en[1] | last_wrdata_en[2] | last_wrdata_en[3])
        self.sync += \
            If(self._wlevel_en.storage,
                oe_dqs.eq(1), oe_dq.eq(0)
            ).Else(
                oe_dqs.eq(oe), oe_dq.eq(oe)
            )
