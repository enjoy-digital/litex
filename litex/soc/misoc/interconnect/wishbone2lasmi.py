from migen import *
from migen.genlib.fsm import FSM, NextState


class WB2LASMI(Module):
    def __init__(self, wishbone, lasmim):

        ###

        # Control FSM
        self.submodules.fsm = fsm = FSM(reset_state="IDLE")
        fsm.act("IDLE",
            If(wishbone.cyc & wishbone.stb,
                NextState("REQUEST")
            )
        )
        fsm.act("REQUEST",
            lasmim.stb.eq(1),
            lasmim.we.eq(wishbone.we),
            If(lasmim.req_ack,
                If(wishbone.we,
                    NextState("WRITE_DATA")
                ).Else(
                    NextState("READ_DATA")
                )
            )
        )
        fsm.act("WRITE_DATA",
            If(lasmim.dat_w_ack,
                lasmim.dat_we.eq(wishbone.sel),
                wishbone.ack.eq(1),
                NextState("IDLE")
            )
        )
        fsm.act("READ_DATA",
            If(lasmim.dat_r_ack,
                wishbone.ack.eq(1),
                NextState("IDLE")
            )
        )

        # Address / Datapath
        self.comb += [
            lasmim.adr.eq(wishbone.adr),
            If(lasmim.dat_w_ack,
                lasmim.dat_w.eq(wishbone.dat_w),
            ),
            wishbone.dat_r.eq(lasmim.dat_r)
        ]
