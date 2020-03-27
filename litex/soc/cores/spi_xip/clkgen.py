from migen import *


class LiteSPIClkGen(Module):
    def __init__(self, pads, device):
        self.div     = div     = Signal(8)
        self.posedge = posedge = Signal()
        self.negedge = negedge = Signal()
        self.clk     = clk     = Signal()
        self.en      = en      = Signal()
        cnt          = Signal(8)
        clkd         = Signal()

        self.comb += [
            posedge.eq(clk & ~clkd),
            negedge.eq(~clk & clkd),
        ]

        self.sync += [
            clkd.eq(clk),
            If(en,
                If(cnt < div,
                    cnt.eq(cnt+1),
                ).Else(
                    cnt.eq(0),
                    clk.eq(~clk),
                )
            ).Else(
                clk.eq(0),
                cnt.eq(0),
            )
        ]

        if not hasattr(pads, "clk"):
            pads.clk = Signal()
            if device == "xc7":
                e2_clk = Signal()
                e2_net = Signal()
                e2_cnt = Signal(4)
                self.specials += Instance("STARTUPE2",
                    i_CLK=0,
                    i_GSR=0,
                    i_GTS=0,
                    i_KEYCLEARB=0,
                    i_PACK=0,
                    i_USRCCLKO=e2_net,
                    i_USRCCLKTS=0,
                    i_USRDONEO=1,
                    i_USRDONETS=1,
                )
                # startupe2 needs 3 usrcclko cycles to switch over to user clock
                self.comb += If(e2_cnt == 6,
                                 e2_net.eq(pads.clk)
                             ).Else(
                                 e2_net.eq(e2_clk)
                             )
                self.sync += If(e2_cnt < 6,
                                 e2_cnt.eq(e2_cnt+1),
                                 e2_clk.eq(~e2_clk)
                             )
            else:
                raise NotImplementedError

