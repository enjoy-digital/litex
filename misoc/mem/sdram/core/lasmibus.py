from migen import *
from migen.bus.transactions import *
from migen.genlib import roundrobin
from migen.genlib.record import *
from migen.genlib.misc import optree


class Interface(Record):
    def __init__(self, aw, dw, nbanks, req_queue_size, read_latency, write_latency):
        self.aw = aw
        self.dw = dw
        self.nbanks = nbanks
        self.req_queue_size = req_queue_size
        self.read_latency = read_latency
        self.write_latency = write_latency

        bank_layout = [
            ("adr",      aw, DIR_M_TO_S),
            ("we",        1, DIR_M_TO_S),
            ("stb",       1, DIR_M_TO_S),
            ("req_ack",   1, DIR_S_TO_M),
            ("dat_w_ack", 1, DIR_S_TO_M),
            ("dat_r_ack", 1, DIR_S_TO_M),
            ("lock",      1, DIR_S_TO_M)
        ]
        if nbanks > 1:
            layout = [("bank"+str(i), bank_layout) for i in range(nbanks)]
        else:
            layout = bank_layout
        layout += [
            ("dat_w",     dw, DIR_M_TO_S),
            ("dat_we", dw//8, DIR_M_TO_S),
            ("dat_r",     dw, DIR_S_TO_M)
        ]
        Record.__init__(self, layout)


class Initiator(Module):
    def __init__(self, generator, bus):
        self.generator = generator
        self.bus = bus
        self.transaction_start = 0
        self.transaction = None
        self.transaction_end = None

    def do_simulation(self, selfp):
        selfp.bus.dat_w = 0
        selfp.bus.dat_we = 0

        if self.transaction is not None:
            if selfp.bus.req_ack:
                selfp.bus.stb = 0
            if selfp.bus.dat_ack:
                if isinstance(self.transaction, TRead):
                    self.transaction_end = selfp.simulator.cycle_counter + self.bus.read_latency
                else:
                    self.transaction_end = selfp.simulator.cycle_counter + self.bus.write_latency - 1

        if self.transaction is None or selfp.simulator.cycle_counter == self.transaction_end:
            if self.transaction is not None:
                self.transaction.latency = selfp.simulator.cycle_counter - self.transaction_start - 1
                if isinstance(self.transaction, TRead):
                    self.transaction.data = selfp.bus.dat_r
                else:
                    selfp.bus.dat_w = self.transaction.data
                    selfp.bus.dat_we = self.transaction.sel
            try:
                self.transaction = next(self.generator)
            except StopIteration:
                raise StopSimulation
            if self.transaction is not None:
                self.transaction_start = selfp.simulator.cycle_counter
                selfp.bus.stb = 1
                selfp.bus.adr = self.transaction.address
                if isinstance(self.transaction, TRead):
                    selfp.bus.we = 0
                else:
                    selfp.bus.we = 1


class TargetModel:
    def __init__(self):
        self.last_bank = 0

    def read(self, bank, address):
        return 0

    def write(self, bank, address, data, we):
        pass

    # Round-robin scheduling
    def select_bank(self, pending_banks):
        if not pending_banks:
            return -1
        self.last_bank += 1
        if self.last_bank > max(pending_banks):
            self.last_bank = 0
        while self.last_bank not in pending_banks:
            self.last_bank += 1
        return self.last_bank


class _ReqFIFO(Module):
    def __init__(self, req_queue_size, bank):
        self.req_queue_size = req_queue_size
        self.bank = bank
        self.contents = []

    def do_simulation(self, selfp):
        if len(self.contents) < self.req_queue_size:
            if selfp.bank.stb:
                self.contents.append((selfp.bank.we, selfp.bank.adr))
            selfp.bank.req_ack = 1
        else:
            selfp.bank.req_ack = 0
        selfp.bank.lock = bool(self.contents)
    do_simulation.passive = True


class Target(Module):
    def __init__(self, model, *ifargs, **ifkwargs):
        self.model = model
        self.bus = Interface(*ifargs, **ifkwargs)
        self.req_fifos = [_ReqFIFO(self.bus.req_queue_size, getattr(self.bus, "bank"+str(nb)))
            for nb in range(self.bus.nbanks)]
        self.submodules += self.req_fifos
        self.rd_pipeline = [None]*self.bus.read_latency
        self.wr_pipeline = [None]*(self.bus.write_latency + 1)

    def do_simulation(self, selfp):
        # determine banks with pending requests
        pending_banks = set(nb for nb, rf in enumerate(self.req_fifos) if rf.contents)

        # issue new transactions
        selected_bank_n = self.model.select_bank(pending_banks)
        selected_transaction = None
        for nb in range(self.bus.nbanks):
            bank = getattr(selfp.bus, "bank"+str(nb))
            if nb == selected_bank_n:
                bank.dat_ack = 1
                selected_transaction = self.req_fifos[nb].contents.pop(0)
            else:
                bank.dat_ack = 0

        rd_transaction = None
        wr_transaction = None
        if selected_bank_n >= 0:
            we, adr = selected_transaction
            if we:
                wr_transaction = selected_bank_n, adr
            else:
                rd_transaction = selected_bank_n, adr

        # data pipeline
        self.rd_pipeline.append(rd_transaction)
        self.wr_pipeline.append(wr_transaction)
        done_rd_transaction = self.rd_pipeline.pop(0)
        done_wr_transaction = self.wr_pipeline.pop(0)
        if done_rd_transaction is not None:
            selfp.bus.dat_r = self.model.read(done_rd_transaction[0], done_rd_transaction[1])
        if done_wr_transaction is not None:
            self.model.write(done_wr_transaction[0], done_wr_transaction[1],
                selfp.bus.dat_w, selfp.bus.dat_we)
    do_simulation.passive = True
