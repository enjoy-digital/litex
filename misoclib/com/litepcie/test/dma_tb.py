import random
from migen.fhdl.std import *
from migen.sim.generic import run_simulation
from migen.actorlib.structuring import Converter

from misoclib.com.litepcie.common import *
from misoclib.com.litepcie.core import Endpoint
from misoclib.com.litepcie.core.irq import interrupt_controller
from misoclib.com.litepcie.frontend.dma import writer, reader

from misoclib.com.litepcie.test.common import *
from misoclib.com.litepcie.test.model.host import *

DMA_READER_IRQ = 1
DMA_WRITER_IRQ = 2

root_id = 0x100
endpoint_id = 0x400
max_length = Signal(8, reset=128)
dma_size = 1024


class DMADriver():
    def __init__(self, dma, selfp):
        self.dma = dma
        self.selfp = selfp

    def set_prog_mode(self):
        dma = getattr(self.selfp, self.dma)
        dma.table._loop_prog_n.storage = 0
        yield

    def set_loop_mode(self):
        dma = getattr(self.selfp, self.dma)
        dma.table._loop_prog_n.storage = 1
        yield

    def flush(self):
        dma = getattr(self.selfp, self.dma)
        dma.table._flush.re = 1
        yield
        dma.table._flush.re = 0
        yield

    def program_descriptor(self, address, length):
        value = address
        value |= (length << 32)

        dma = getattr(self.selfp, self.dma)

        dma.table._value.storage = value
        dma.table._we.r = 1
        dma.table._we.re = 1
        yield
        dma.table._we.re = 0
        yield

    def enable(self):
        dma = getattr(self.selfp, self.dma)
        dma._enable.storage = 1
        yield

    def disable(self):
        dma = getattr(self.selfp, self.dma)
        dma._enable.storage = 0
        yield


class InterruptHandler(Module):
    def __init__(self, debug=False):
        self.debug = debug
        self.sink = Sink(interrupt_layout())
        self.dma_writer_irq = 0

    def set_tb_selfp(self, tb_selfp):
        self.tb_selfp = tb_selfp

    def do_simulation(self, selfp):
        tb_selfp = self.tb_selfp
        tb_selfp.irq_controller._clear.r = 0
        tb_selfp.irq_controller._clear.re = 0
        selfp.sink.ack = 1
        self.dma_writer_irq = 0
        if selfp.sink.stb and (selfp.simulator.cycle_counter%4 == 0):
            # get vector
            irq_vector = tb_selfp.irq_controller._vector.status

            # handle irq
            if irq_vector & DMA_READER_IRQ:
                if self.debug:
                    print("DMA_READER IRQ : {}".format(tb_selfp.dma_reader.table._index.status))
                # clear irq_controller
                tb_selfp.irq_controller._clear.re = 1
                tb_selfp.irq_controller._clear.r |= DMA_READER_IRQ

            if irq_vector & DMA_WRITER_IRQ:
                if self.debug:
                    print("DMA_WRITER IRQ : {}".format(tb_selfp.dma_writer.table._index.status))
                # clear irq_controller
                tb_selfp.irq_controller._clear.re = 1
                tb_selfp.irq_controller._clear.r |= DMA_WRITER_IRQ
                self.dma_writer_irq = 1


test_size = 16*1024


class TB(Module):
    def __init__(self, with_converter=False):
        self.submodules.host = Host(64, root_id, endpoint_id,
            phy_debug=False,
            chipset_debug=False, chipset_split=True, chipset_reordering=True,
            host_debug=True)
        self.submodules.endpoint = Endpoint(self.host.phy, max_pending_requests=8, with_reordering=True)
        self.submodules.dma_reader = reader.DMAReader(self.endpoint, self.endpoint.crossbar.get_master_port(read_only=True))
        self.submodules.dma_writer = writer.DMAWriter(self.endpoint, self.endpoint.crossbar.get_master_port(write_only=True))

        if with_converter:
                self.submodules.up_converter = Converter(dma_layout(16), dma_layout(64))
                self.submodules.down_converter = Converter(dma_layout(64), dma_layout(16))

                self.comb += [
                    self.dma_reader.source.connect(self.down_converter.sink),
                    self.down_converter.source.connect(self.up_converter.sink),
                    self.up_converter.source.connect(self.dma_writer.sink)
                ]
        else:
            self.comb += self.dma_reader.source.connect(self.dma_writer.sink)

        self.submodules.irq_controller = interrupt_controller.InterruptController(2)
        self.comb += [
            self.irq_controller.irqs[log2_int(DMA_READER_IRQ)].eq(self.dma_reader.table.irq),
            self.irq_controller.irqs[log2_int(DMA_WRITER_IRQ)].eq(self.dma_writer.table.irq)
        ]
        self.submodules.irq_handler = InterruptHandler()
        self.comb += self.irq_controller.source.connect(self.irq_handler.sink)

    def gen_simulation(self, selfp):
        self.host.malloc(0x00000000, test_size*2)
        self.host.chipset.enable()
        host_datas = [seed_to_data(i, True) for i in range(test_size//4)]
        self.host.write_mem(0x00000000, host_datas)

        dma_reader_driver = DMADriver("dma_reader", selfp)
        dma_writer_driver = DMADriver("dma_writer", selfp)

        self.irq_handler.set_tb_selfp(selfp)

        yield from dma_reader_driver.set_prog_mode()
        yield from dma_reader_driver.flush()
        for i in range(8):
            yield from dma_reader_driver.program_descriptor((test_size//8)*i, test_size//8)

        yield from dma_writer_driver.set_prog_mode()
        yield from dma_writer_driver.flush()
        for i in range(8):
            yield from dma_writer_driver.program_descriptor(test_size + (test_size//8)*i, test_size//8)

        selfp.irq_controller._enable.storage = DMA_READER_IRQ | DMA_WRITER_IRQ

        yield from dma_reader_driver.enable()
        yield from dma_writer_driver.enable()

        i = 0
        while i != 8:
            i += self.irq_handler.dma_writer_irq
            yield

        for i in range(100):
            yield
        loopback_datas = self.host.read_mem(test_size, test_size)

        s, l, e = check(host_datas, loopback_datas)
        print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    run_simulation(TB(with_converter=False), ncycles=4000, vcd_name="my.vcd", keep_files=True)
