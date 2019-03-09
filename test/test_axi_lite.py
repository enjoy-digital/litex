import unittest

from migen import *

from litex.soc.interconnect import csr
from litex.soc.interconnect import csr_bus
from litex.soc.interconnect import axi_lite

class CSRModule(Module, csr.AutoCSR):
    def __init__(self):
        self.foo = csr.CSRStorage(32, reset=1)
        self.bar = csr.CSRStorage(32, reset=1)


class AXILiteDUT(Module):
    def __init__(self):
        self.csr = csr_bus.Interface(data_width=32, address_width=12)
        self.axi = axi_lite.Interface(data_width=32, address_width=14)
        self.submodules.csrmodule = CSRModule()
        self.submodules.dut = axi_lite.AXILite2CSR(self.axi, self.csr)
        self.submodules.csrbankarray = csr_bus.CSRBankArray(
            self, self.map_csr, data_width=32, address_width=12)
        self.submodules.csrcon = csr_bus.Interconnect(
            self.csr, self.csrbankarray.get_buses())

    def map_csr(self, name, memory):
        return {"csrmodule": 0}[name]


class TestAXILite(unittest.TestCase):
    def test_write_read(self):
        def generator(dut):
            axi = dut.axi

            for _ in range(8):
                yield

            # Write test
            yield axi.aw.valid.eq(1)
            yield axi.aw.addr.eq(4)
            yield axi.w.valid.eq(1)
            yield axi.b.ready.eq(1)
            yield axi.w.data.eq(0x2137)

            while (yield axi.aw.ready) != 1:
                yield
            while (yield axi.w.ready) != 1:
                yield
            yield axi.aw.valid.eq(0)
            yield axi.w.valid.eq(0)

            for _ in range(8):
                yield

            # Read test
            yield axi.ar.valid.eq(1)
            yield axi.r.ready.eq(1)
            yield axi.ar.addr.eq(4)

            while (yield axi.ar.ready != 1):
                yield
            yield axi.ar.valid.eq(0)
            while (yield axi.r.valid != 1):
                yield
            yield axi.r.ready.eq(0)

            read = yield axi.r.data
            assert read == 0x2137

            for _ in range(8):
                yield
        dut = AXILiteDUT()
        run_simulation(dut, generator(dut.dut), vcd_name='axi-write-read.vcd')

    def test_simultaneous(dut):
        def generator(dut):
            axi = dut.axi

            for _ in range(8):
                yield

            # Write
            yield axi.aw.valid.eq(1)
            yield axi.aw.addr.eq(2)
            yield axi.w.valid.eq(1)
            yield axi.b.ready.eq(1)
            yield axi.w.data.eq(0x2137)
            # Read
            yield axi.ar.valid.eq(1)
            yield axi.r.ready.eq(1)
            yield axi.ar.addr.eq(2)

            yield
            yield

            is_reading = yield axi.ar.ready
            is_writing = yield axi.aw.ready

            assert is_reading
            assert not is_writing


        dut = AXILiteDUT()
        run_simulation(dut, generator(dut.dut), vcd_name='axi-simultaneous.vcd')
