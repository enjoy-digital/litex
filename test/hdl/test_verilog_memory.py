import unittest

from migen import *

from litex.gen.fhdl.verilog import convert


class _DualPortWriteFirstMemory(Module):
    def __init__(self, we_granularity=0):
        self.clock_domains.cd_sys = ClockDomain()

        we_width = 1 if we_granularity == 0 else 32//we_granularity

        self.p0_adr   = Signal(9,  name="p0_adr")
        self.p0_dat_w = Signal(32, name="p0_dat_w")
        self.p0_dat_r = Signal(32, name="p0_dat_r")
        self.p0_we    = Signal(we_width, name="p0_we")
        self.p1_adr   = Signal(9,  name="p1_adr")
        self.p1_dat_w = Signal(32, name="p1_dat_w")
        self.p1_dat_r = Signal(32, name="p1_dat_r")
        self.p1_we    = Signal(we_width, name="p1_we")

        mem = Memory(32, 512, name="capture_memory", init=[0x01, 0x02, 0x03, 0xdeadbeef])
        p0  = mem.get_port(write_capable=True, mode=WRITE_FIRST, we_granularity=we_granularity)
        p1  = mem.get_port(write_capable=True, mode=WRITE_FIRST, we_granularity=we_granularity)
        self.specials += mem, p0, p1
        self.comb += [
            p0.adr.eq(self.p0_adr),
            p0.dat_w.eq(self.p0_dat_w),
            p0.we.eq(self.p0_we),
            self.p0_dat_r.eq(p0.dat_r),
            p1.adr.eq(self.p1_adr),
            p1.dat_w.eq(self.p1_dat_w),
            p1.we.eq(self.p1_we),
            self.p1_dat_r.eq(p1.dat_r),
        ]

    def get_ios(self):
        return {
            self.p0_adr,
            self.p0_dat_w,
            self.p0_dat_r,
            self.p0_we,
            self.p1_adr,
            self.p1_dat_w,
            self.p1_dat_r,
            self.p1_we,
        }


class TestMemoryVerilog(unittest.TestCase):
    def _convert(self, dut):
        return convert(dut, ios=dut.get_ios(), name="test").main_source

    def test_write_first_dual_write_ports_use_registered_data_outputs(self):
        verilog = self._convert(_DualPortWriteFirstMemory())

        self.assertIn("reg [31:0] capture_memory_dat0;", verilog)
        self.assertIn("reg [31:0] capture_memory_dat1;", verilog)
        self.assertNotIn("capture_memory_adr0", verilog)
        self.assertNotIn("capture_memory_adr1", verilog)
        self.assertIn(
            "if (p0_we1)\n"
            "\t\tcapture_memory_dat0 <= p0_dat_w1;\n"
            "\telse\n"
            "\t\tcapture_memory_dat0 <= capture_memory[p0_adr1];",
            verilog,
        )
        self.assertIn("assign p0_dat_r1 = capture_memory_dat0;", verilog)
        self.assertIn("assign p1_dat_r1 = capture_memory_dat1;", verilog)

    def test_write_first_byte_writes_keep_split_write_template(self):
        verilog = self._convert(_DualPortWriteFirstMemory(we_granularity=8))

        self.assertIn("reg [8:0] capture_memory_adr0;", verilog)
        self.assertIn("reg [8:0] capture_memory_adr1;", verilog)
        self.assertIn(
            "capture_memory[p0_adr1][we_index*8 +: 8] <= p0_dat_w1[we_index*8 +: 8];",
            verilog,
        )
        self.assertIn("capture_memory_adr0 <= p0_adr1;", verilog)
        self.assertIn("assign p0_dat_r1 = capture_memory[capture_memory_adr0];", verilog)


if __name__ == "__main__":
    unittest.main()
