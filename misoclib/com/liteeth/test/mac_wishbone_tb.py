from migen.fhdl.std import *
from migen.bus import wishbone
from migen.bus.transactions import *
from migen.sim.generic import run_simulation

from misoclib.com.liteeth.common import *
from misoclib.com.liteeth.core.mac import LiteEthMAC

from misoclib.com.liteeth.test.common import *
from misoclib.com.liteeth.test.model import phy, mac


class WishboneMaster:
    def __init__(self, obj):
        self.obj = obj
        self.dat = 0

    def write(self, adr, dat):
        self.obj.cyc = 1
        self.obj.stb = 1
        self.obj.adr = adr
        self.obj.we = 1
        self.obj.sel = 0xF
        self.obj.dat_w = dat
        while self.obj.ack == 0:
            yield
        self.obj.cyc = 0
        self.obj.stb = 0
        yield

    def read(self, adr):
        self.obj.cyc = 1
        self.obj.stb = 1
        self.obj.adr = adr
        self.obj.we = 0
        self.obj.sel = 0xF
        self.obj.dat_w = 0
        while self.obj.ack == 0:
            yield
        self.dat = self.obj.dat_r
        self.obj.cyc = 0
        self.obj.stb = 0
        yield


class SRAMReaderDriver:
    def __init__(self, obj):
        self.obj = obj

    def start(self, slot, length):
        self.obj._slot.storage = slot
        self.obj._length.storage = length
        self.obj._start.re = 1
        yield
        self.obj._start.re = 0
        yield

    def wait_done(self):
        while self.obj.ev.done.pending == 0:
            yield

    def clear_done(self):
        self.obj.ev.done.clear = 1
        yield
        self.obj.ev.done.clear = 0
        yield


class SRAMWriterDriver:
    def __init__(self, obj):
        self.obj = obj

    def wait_available(self):
        while self.obj.ev.available.pending == 0:
            yield

    def clear_available(self):
        self.obj.ev.available.clear = 1
        yield
        self.obj.ev.available.clear = 0
        yield


class TB(Module):
    def __init__(self):
        self.submodules.phy_model = phy.PHY(8, debug=False)
        self.submodules.mac_model = mac.MAC(self.phy_model, debug=False, loopback=True)
        self.submodules.ethmac = LiteEthMAC(phy=self.phy_model, dw=32, interface="wishbone", with_preamble_crc=True)

        # use sys_clk for each clock_domain
        self.clock_domains.cd_eth_rx = ClockDomain()
        self.clock_domains.cd_eth_tx = ClockDomain()
        self.comb += [
            self.cd_eth_rx.clk.eq(ClockSignal()),
            self.cd_eth_rx.rst.eq(ResetSignal()),
            self.cd_eth_tx.clk.eq(ClockSignal()),
            self.cd_eth_tx.rst.eq(ResetSignal()),
        ]

    def gen_simulation(self, selfp):
        selfp.cd_eth_rx.rst = 1
        selfp.cd_eth_tx.rst = 1
        yield
        selfp.cd_eth_rx.rst = 0
        selfp.cd_eth_tx.rst = 0

        wishbone_master = WishboneMaster(selfp.ethmac.bus)
        sram_reader_driver = SRAMReaderDriver(selfp.ethmac.interface.sram.reader)
        sram_writer_driver = SRAMWriterDriver(selfp.ethmac.interface.sram.writer)

        sram_writer_slots_offset = [0x000, 0x200]
        sram_reader_slots_offset = [0x400, 0x600]

        length = 150+2

        tx_payload = [seed_to_data(i, True) % 0xFF for i in range(length)] + [0, 0, 0, 0]

        errors = 0

        while True:
            for slot in range(2):
                print("slot {}: ".format(slot), end="")
                # fill tx memory
                for i in range(length//4+1):
                    dat = int.from_bytes(tx_payload[4*i:4*(i+1)], "big")
                    yield from wishbone_master.write(sram_reader_slots_offset[slot]+i, dat)

                # send tx payload & wait
                yield from sram_reader_driver.start(slot, length)
                yield from sram_reader_driver.wait_done()
                yield from sram_reader_driver.clear_done()

                # wait rx
                yield from sram_writer_driver.wait_available()
                yield from sram_writer_driver.clear_available()

                # get rx payload (loopback on PHY Model)
                rx_payload = []
                for i in range(length//4+1):
                    yield from wishbone_master.read(sram_writer_slots_offset[slot]+i)
                    dat = wishbone_master.dat
                    rx_payload += list(dat.to_bytes(4, byteorder='big'))

                # check results
                s, l, e = check(tx_payload[:length], rx_payload[:min(length, len(rx_payload))])
                print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

if __name__ == "__main__":
    run_simulation(TB(), ncycles=3000, vcd_name="my.vcd", keep_files=True)
