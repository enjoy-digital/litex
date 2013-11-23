from migen.fhdl.std import *
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
			("adr",		aw,		DIR_M_TO_S),
			("we",		1,		DIR_M_TO_S),
			("stb",		1,		DIR_M_TO_S),
			("req_ack",	1,		DIR_S_TO_M),
			("dat_ack",	1,		DIR_S_TO_M),
			("lock",	1,		DIR_S_TO_M)
		]
		if nbanks > 1:
			layout = [("bank"+str(i), bank_layout) for i in range(nbanks)]
		else:
			layout = bank_layout
		layout += [
			("dat_w",	dw, 	DIR_M_TO_S),
			("dat_we",	dw//8, 	DIR_M_TO_S),
			("dat_r",	dw, 	DIR_S_TO_M)
		]
		Record.__init__(self, layout)

def _getattr_all(l, attr):
	it = iter(l)
	r = getattr(next(it), attr)
	for e in it:
		if getattr(e, attr) != r:
			raise ValueError
	return r

class Crossbar(Module):
	def __init__(self, controllers, cba_shift):
		self._controllers = controllers
		self._cba_shift = cba_shift

		self._rca_bits = _getattr_all(controllers, "aw")
		self._dw = _getattr_all(controllers, "dw")
		self._nbanks = _getattr_all(controllers, "nbanks")
		self._req_queue_size = _getattr_all(controllers, "req_queue_size")
		self._read_latency = _getattr_all(controllers, "read_latency")
		self._write_latency = _getattr_all(controllers, "write_latency")

		self._bank_bits = log2_int(self._nbanks, False)
		self._controller_bits = log2_int(len(self._controllers), False)

		self._masters = []

	def get_master(self):
		if self.finalized:
			raise FinalizeError
		lasmi_master = Interface(self._rca_bits + self._bank_bits + self._controller_bits,
			self._dw, 1, self._req_queue_size, self._read_latency, self._write_latency)
		self._masters.append(lasmi_master)
		return lasmi_master

	def do_finalize(self):
		nmasters = len(self._masters)

		m_ca, m_ba, m_rca = self._split_master_addresses(self._controller_bits,
			self._bank_bits, self._rca_bits, self._cba_shift)
		
		for nc, controller in enumerate(self._controllers):
			if self._controller_bits:
				controller_selected = [ca == nc for ca in m_ca]
			else:
				controller_selected = [1]*nmasters
			master_req_acks = [0]*nmasters
			master_dat_acks = [0]*nmasters
			rrs = [roundrobin.RoundRobin(nmasters, roundrobin.SP_CE) for n in range(self._nbanks)]
			self.submodules += rrs
			for nb, rr in enumerate(rrs):
				bank = getattr(controller, "bank"+str(nb))

				# for each master, determine if another bank locks it
				master_locked = []
				for nm, master in enumerate(self._masters):
					locked = 0
					for other_nb, other_rr in enumerate(rrs):
						if other_nb != nb:
							other_bank = getattr(controller, "bank"+str(other_nb))
							locked = locked | (other_bank.lock & (other_rr.grant == nm))
					master_locked.append(locked)

				# arbitrate
				bank_selected = [cs & (ba == nb) & ~locked for cs, ba, locked in zip(controller_selected, m_ba, master_locked)]
				bank_requested = [bs & master.stb for bs, master in zip(bank_selected, self._masters)]
				self.comb += [
					rr.request.eq(Cat(*bank_requested)),
					rr.ce.eq(~bank.stb & ~bank.lock)
				]

				# route requests
				self.comb += [
					bank.adr.eq(Array(m_rca)[rr.grant]),
					bank.we.eq(Array(self._masters)[rr.grant].we),
					bank.stb.eq(Array(bank_requested)[rr.grant])
				]
				master_req_acks = [master_req_ack | ((rr.grant == nm) & bank_selected[nm] & bank.req_ack)
					for nm, master_req_ack in enumerate(master_req_acks)]
				master_dat_acks = [master_dat_ack | ((rr.grant == nm) & bank.dat_ack)
					for nm, master_dat_ack in enumerate(master_dat_acks)]

			self.comb += [master.req_ack.eq(master_req_ack) for master, master_req_ack in zip(self._masters, master_req_acks)]
			self.comb += [master.dat_ack.eq(master_dat_ack) for master, master_dat_ack in zip(self._masters, master_dat_acks)]

			# route data writes
			controller_selected_wl = controller_selected
			for i in range(self._write_latency):
				n_controller_selected_wl = [Signal() for i in range(nmasters)]
				self.sync += [n.eq(o) for n, o in zip(n_controller_selected_wl, controller_selected_wl)]
				controller_selected_wl = n_controller_selected_wl
			dat_w_maskselect = []
			dat_we_maskselect = []
			for master, selected in zip(self._masters, controller_selected_wl):
				o_dat_w = Signal(self._dw)
				o_dat_we = Signal(self._dw//8)
				self.comb += If(selected,
						o_dat_w.eq(master.dat_w),
						o_dat_we.eq(master.dat_we)
					)
				dat_w_maskselect.append(o_dat_w)
				dat_we_maskselect.append(o_dat_we)
			self.comb += [
				controller.dat_w.eq(optree("|", dat_w_maskselect)),
				controller.dat_we.eq(optree("|", dat_we_maskselect))
			]

		# route data reads
		if self._controller_bits:
			for master in self._masters:
				controller_sel = Signal(self._controller_bits)
				for nc, controller in enumerate(self._controllers):
					for nb in range(nbanks):
						bank = getattr(controller, "bank"+str(nb))
						self.comb += If(bank.stb & bank.ack, controller_sel.eq(nc))
				for i in range(self._read_latency):
					n_controller_sel = Signal(self._controller_bits)
					self.sync += n_controller_sel.eq(controller_sel)
					controller_sel = n_controller_sel
				self.comb += master.dat_r.eq(Array(self._controllers)[controller_sel].dat_r)
		else:
			self.comb += [master.dat_r.eq(self._controllers[0].dat_r) for master in self._masters]

	def _split_master_addresses(self, controller_bits, bank_bits, rca_bits, cba_shift):
		m_ca = []	# controller address
		m_ba = []	# bank address
		m_rca = []	# row and column address
		for master in self._masters:
			cba = Signal(self._controller_bits + self._bank_bits)
			rca = Signal(self._rca_bits)
			cba_upper = cba_shift + controller_bits + bank_bits
			self.comb += cba.eq(master.adr[cba_shift:cba_upper])
			if cba_shift < self._rca_bits:
				if cba_shift:
					self.comb += rca.eq(Cat(master.adr[:cba_shift], master.adr[cba_upper:]))
				else:
					self.comb += rca.eq(master.adr[cba_upper:])
			else:
				self.comb += rca.eq(master.adr[:cba_shift])

			if self._controller_bits:
				ca = Signal(self._controller_bits)
				ba = Signal(self._bank_bits)
				self.comb += Cat(ba, ca).eq(cba)
			else:
				ca = None
				ba = cba

			m_ca.append(ca)
			m_ba.append(ba)
			m_rca.append(rca)
		return m_ca, m_ba, m_rca

class Initiator(Module):
	def __init__(self, generator, bus):
		self.generator = generator
		self.bus = bus
		self.transaction_start = 0
		self.transaction = None
		self.transaction_end = None
		self.done = False
	
	def do_simulation(self, s):
		s.wr(self.bus.dat_w, 0)
		s.wr(self.bus.dat_we, 0)
		if not self.done:
			if self.transaction is not None:
				if s.rd(self.bus.req_ack):
					s.wr(self.bus.stb, 0)
				if s.rd(self.bus.dat_ack):
					if isinstance(self.transaction, TRead):
						self.transaction_end = s.cycle_counter + self.bus.read_latency
					else:
						self.transaction_end = s.cycle_counter + self.bus.write_latency - 1

			if self.transaction is None or s.cycle_counter == self.transaction_end:
				if self.transaction is not None:
					self.transaction.latency = s.cycle_counter - self.transaction_start - 1
					if isinstance(self.transaction, TRead):
						self.transaction.data = s.rd(self.bus.dat_r)
					else:
						s.wr(self.bus.dat_w, self.transaction.data)
						s.wr(self.bus.dat_we, self.transaction.sel)
				try:
					self.transaction = next(self.generator)
				except StopIteration:
					self.done = True
					self.transaction = None
				if self.transaction is not None:
					self.transaction_start = s.cycle_counter
					s.wr(self.bus.stb, 1)
					s.wr(self.bus.adr, self.transaction.address)
					if isinstance(self.transaction, TRead):
						s.wr(self.bus.we, 0)
					else:
						s.wr(self.bus.we, 1)

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

	def do_simulation(self, s):
		if len(self.contents) < self.req_queue_size:
			if s.rd(self.bank.stb):
				self.contents.append((s.rd(self.bank.we), s.rd(self.bank.adr)))
			s.wr(self.bank.req_ack, 1)
		else:
			s.wr(self.bank.req_ack, 0)
		s.wr(self.bank.lock, bool(self.contents))

class Target(Module):
	def __init__(self, model, *ifargs, **ifkwargs):
		self.model = model
		self.bus = Interface(*ifargs, **ifkwargs)
		self.req_fifos = [_ReqFIFO(self.bus.req_queue_size, getattr(self.bus, "bank"+str(nb)))
			for nb in range(self.bus.nbanks)]
		self.submodules += self.req_fifos
		self.rd_pipeline = [None]*self.bus.read_latency
		self.wr_pipeline = [None]*(self.bus.write_latency + 1)

	def do_simulation(self, s):
		# determine banks with pending requests
		pending_banks = set(nb for nb, rf in enumerate(self.req_fifos) if rf.contents)

		# issue new transactions
		selected_bank_n = self.model.select_bank(pending_banks)
		selected_transaction = None
		for nb in range(self.bus.nbanks):
			bank = getattr(self.bus, "bank"+str(nb))
			if nb == selected_bank_n:
				s.wr(bank.dat_ack, 1)
				selected_transaction = self.req_fifos[nb].contents.pop(0)
			else:
				s.wr(bank.dat_ack, 0)
		
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
			s.wr(self.bus.dat_r, self.model.read(done_rd_transaction[0], done_rd_transaction[1]))
		if done_wr_transaction is not None:
			self.model.write(done_wr_transaction[0], done_wr_transaction[1],
				s.rd(self.bus.dat_w), s.rd(self.bus.dat_we))
