from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bank.description import *
from migen.genlib.fsm import FSM, NextState
from migen.genlib.misc import split, displacer, chooser
from migen.genlib.record import Record, layout_len


# cachesize (in 32-bit words) is the size of the data store, must be a power of 2
class WB2LASMI(Module, AutoCSR):
    def __init__(self, cachesize, lasmim):
        self._cachesize = CSRStatus(8, reset=log2_int(cachesize))
        self.wishbone = wishbone.Interface()

        ###

        data_width = flen(self.wishbone.dat_r)
        if lasmim.dw > data_width and (lasmim.dw % data_width) != 0:
            raise ValueError("LASMI data width must be a multiple of {dw}".format(dw=data_width))
        if lasmim.dw < data_width and (data_width % lasmim.dw) != 0:
            raise ValueError("WISHBONE data width must be a multiple of {dw}".format(dw=lasmim.dw))

        # Split address:
        # TAG | LINE NUMBER | LINE OFFSET
        offsetbits = log2_int(max(lasmim.dw//data_width, 1))
        addressbits = lasmim.aw + offsetbits
        linebits = log2_int(cachesize) - offsetbits
        tagbits = addressbits - linebits
        wordbits = log2_int(max(data_width//lasmim.dw, 1))
        adr_offset, adr_line, adr_tag = split(self.wishbone.adr, offsetbits, linebits, tagbits)
        word = Signal(wordbits) if wordbits else None

        # Data memory
        data_mem = Memory(lasmim.dw*2**wordbits, 2**linebits)
        data_port = data_mem.get_port(write_capable=True, we_granularity=8)
        self.specials += data_mem, data_port

        write_from_lasmi = Signal()
        write_to_lasmi = Signal()
        if adr_offset is None:
            adr_offset_r = None
        else:
            adr_offset_r = Signal(offsetbits)
            self.sync += adr_offset_r.eq(adr_offset)

        self.comb += [
            data_port.adr.eq(adr_line),
            If(write_from_lasmi,
                displacer(lasmim.dat_r, word, data_port.dat_w),
                displacer(Replicate(1, lasmim.dw//8), word, data_port.we)
            ).Else(
                data_port.dat_w.eq(Replicate(self.wishbone.dat_w, max(lasmim.dw//data_width, 1))),
                If(self.wishbone.cyc & self.wishbone.stb & self.wishbone.we & self.wishbone.ack,
                    displacer(self.wishbone.sel, adr_offset, data_port.we, 2**offsetbits, reverse=True)
                )
            ),
            If(write_to_lasmi,
                chooser(data_port.dat_r, word, lasmim.dat_w),
                lasmim.dat_we.eq(2**(lasmim.dw//8)-1)
            ),
            chooser(data_port.dat_r, adr_offset_r, self.wishbone.dat_r, reverse=True)
        ]


        # Tag memory
        tag_layout = [("tag", tagbits), ("dirty", 1)]
        tag_mem = Memory(layout_len(tag_layout), 2**linebits)
        tag_port = tag_mem.get_port(write_capable=True)
        self.specials += tag_mem, tag_port
        tag_do = Record(tag_layout)
        tag_di = Record(tag_layout)
        self.comb += [
            tag_do.raw_bits().eq(tag_port.dat_r),
            tag_port.dat_w.eq(tag_di.raw_bits())
        ]

        self.comb += [
            tag_port.adr.eq(adr_line),
            tag_di.tag.eq(adr_tag)
        ]
        if word is not None:
            self.comb += lasmim.adr.eq(Cat(word, adr_line, tag_do.tag))
        else:
            self.comb += lasmim.adr.eq(Cat(adr_line, tag_do.tag))

        # Lasmim word computation, word_clr and word_inc will be simplified
        # at synthesis when wordbits=0
        word_clr = Signal()
        word_inc = Signal()
        if word is not None:
            self.sync += \
                If(word_clr,
                    word.eq(0),
                ).Elif(word_inc,
                    word.eq(word+1)
                )

        def word_is_last(word):
            if word is not None:
                return word == 2**wordbits-1
            else:
                return 1

        # Control FSM
        assert(lasmim.write_latency >= 1 and lasmim.read_latency >= 1)
        fsm = FSM(reset_state="IDLE")
        self.submodules += fsm


        fsm.act("IDLE",
            If(self.wishbone.cyc & self.wishbone.stb, NextState("TEST_HIT"))
        )
        fsm.act("TEST_HIT",
            word_clr.eq(1),
            If(tag_do.tag == adr_tag,
                self.wishbone.ack.eq(1),
                If(self.wishbone.we,
                    tag_di.dirty.eq(1),
                    tag_port.we.eq(1)
                ),
                NextState("IDLE")
            ).Else(
                If(tag_do.dirty,
                    NextState("EVICT_REQUEST")
                ).Else(
                    NextState("REFILL_WRTAG")
                )
            )
        )

        fsm.act("EVICT_REQUEST",
            lasmim.stb.eq(1),
            lasmim.we.eq(1),
            If(lasmim.req_ack, NextState("EVICT_DATA"))
        )
        fsm.act("EVICT_DATA",
            If(lasmim.dat_w_ack,
                write_to_lasmi.eq(1),
                word_inc.eq(1),
                If(word_is_last(word),
                    NextState("REFILL_WRTAG"),
                ).Else(
                    NextState("EVICT_REQUEST")
                )
            )
        )

        fsm.act("REFILL_WRTAG",
            # Write the tag first to set the LASMI address
            tag_port.we.eq(1),
            word_clr.eq(1),
            NextState("REFILL_REQUEST")
        )
        fsm.act("REFILL_REQUEST",
            lasmim.stb.eq(1),
            If(lasmim.req_ack, NextState("REFILL_DATA"))
        )
        fsm.act("REFILL_DATA",
            If(lasmim.dat_r_ack,
                write_from_lasmi.eq(1),
                word_inc.eq(1),
                If(word_is_last(word),
                    NextState("TEST_HIT"),
                ).Else(
                    NextState("REFILL_REQUEST")
                )
            )
        )
