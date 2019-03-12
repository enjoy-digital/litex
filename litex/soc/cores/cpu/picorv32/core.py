import os

from migen import *

from litex.soc.interconnect import wishbone


class PicoRV32(Module):
    name = "picorv32"
    endianness = "little"
    gcc_triple = ("riscv64-unknown-elf", "riscv32-unknown-elf")
    gcc_flags_template = "-D__picorv32__ -mno-save-restore -march=rv32{ext} -mabi=ilp32"
    linker_output_format = "elf32-littleriscv"

    def __init__(self, platform, progaddr_reset, variant):
        self.gcc_flags = ""

        self.reset = Signal()
        self.ibus = i = wishbone.Interface()
        self.dbus = d = wishbone.Interface()
        self.interrupt = Signal(32)
        self.trap = Signal()

        # # #

        mem_valid = Signal()
        mem_instr = Signal()
        mem_ready = Signal()
        mem_addr = Signal(32)
        mem_wdata = Signal(32)
        mem_wstrb = Signal(4)
        mem_rdata = Signal(32)

        # PicoRV32 parameters. To create a new variant, modify this dictionary
        # and change the desired parameters.
        picorv32_params = {
            "p_ENABLE_COUNTERS" : 1,
            "p_ENABLE_COUNTERS64" : 1,
            # Changing REGS has no effect as on FPGAs, the registers are
            # implemented using a register file stored in DPRAM.
            "p_ENABLE_REGS_16_31" : 1,
            "p_ENABLE_REGS_DUALPORT" : 1,
            "p_LATCHED_MEM_RDATA" : 0,
            "p_TWO_STAGE_SHIFT" : 1,
            "p_TWO_CYCLE_COMPARE" : 0,
            "p_TWO_CYCLE_ALU" : 0,
            "p_CATCH_MISALIGN" : 1,
            "p_CATCH_ILLINSN" : 1,
            "p_ENABLE_PCPI" : 0,
            "p_ENABLE_MUL" : 1,
            "p_ENABLE_DIV" : 1,
            "p_ENABLE_FAST_MUL" : 0,
            "p_ENABLE_IRQ" : 1,
            "p_ENABLE_IRQ_QREGS" : 1,
            "p_ENABLE_IRQ_TIMER" : 1,
            "p_ENABLE_TRACE" : 0,
            "p_MASKED_IRQ" : 0x00000000,
            "p_LATCHED_IRQ" : 0xffffffff,
            "p_PROGADDR_RESET" : progaddr_reset,
            "p_PROGADDR_IRQ" : progaddr_reset + 0x00000010,
            "p_STACKADDR" : 0xffffffff
        }

        if variant == None:
            self.gcc_flags = PicoRV32.gcc_flags_template.format(ext="im")
        elif variant == "minimal":
            picorv32_params.update({
                "p_ENABLE_COUNTERS" : 0,
                "p_ENABLE_COUNTERS64" : 0,
                "p_TWO_STAGE_SHIFT" : 0,
                "p_CATCH_MISALIGN" : 0,
                "p_ENABLE_MUL" : 0,
                "p_ENABLE_DIV" : 0,
                "p_ENABLE_IRQ_TIMER" : 0
            })
            self.gcc_flags = PicoRV32.gcc_flags_template.format(ext="i")

        self.specials += Instance("picorv32",
            # parameters dictionary
            **picorv32_params,

            # clock / reset
            i_clk=ClockSignal(),
            i_resetn=~(ResetSignal() | self.reset),

            # trap
            o_trap=self.trap,

            # memory interface
            o_mem_valid=mem_valid,
            o_mem_instr=mem_instr,
            i_mem_ready=mem_ready,

            o_mem_addr=mem_addr,
            o_mem_wdata=mem_wdata,
            o_mem_wstrb=mem_wstrb,
            i_mem_rdata=mem_rdata,

            # look ahead interface (not used)
            o_mem_la_read=Signal(),
            o_mem_la_write=Signal(),
            o_mem_la_addr=Signal(32),
            o_mem_la_wdata=Signal(32),
            o_mem_la_wstrb=Signal(4),

            # co-processor interface (not used)
            o_pcpi_valid=Signal(),
            o_pcpi_insn=Signal(32),
            o_pcpi_rs1=Signal(32),
            o_pcpi_rs2=Signal(32),
            i_pcpi_wr=0,
            i_pcpi_rd=0,
            i_pcpi_wait=0,
            i_pcpi_ready=0,

            # irq interface
            i_irq=self.interrupt,
            o_eoi=Signal(32)) # not used

        # adapt memory interface to wishbone
        self.comb += [
             # instruction
             i.adr.eq(mem_addr[2:]),
             i.dat_w.eq(mem_wdata),
             i.we.eq(mem_wstrb != 0),
             i.sel.eq(mem_wstrb),
             i.cyc.eq(mem_valid & mem_instr),
             i.stb.eq(mem_valid & mem_instr),
             i.cti.eq(0),
             i.bte.eq(0),
             If(mem_instr,
                 mem_ready.eq(i.ack),
                 mem_rdata.eq(i.dat_r),
             ),

             # data
             d.adr.eq(mem_addr[2:]),
             d.dat_w.eq(mem_wdata),
             d.we.eq(mem_wstrb != 0),
             d.sel.eq(mem_wstrb),
             d.cyc.eq(mem_valid & ~mem_instr),
             d.stb.eq(mem_valid & ~mem_instr),
             d.cti.eq(0),
             d.bte.eq(0),
             If(~mem_instr,
                 mem_ready.eq(d.ack),
                 mem_rdata.eq(d.dat_r)
             )
        ]

        # add verilog sources
        self.add_sources(platform)

    @staticmethod
    def add_sources(platform):
        vdir = os.path.join(
            os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_source(os.path.join(vdir, "picorv32.v"))
