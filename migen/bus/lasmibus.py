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
	def __init__(self, controllers, nmasters, cba_shift):
		ncontrollers = len(controllers)
		rca_bits = _getattr_all(controllers, "aw")
		dw = _getattr_all(controllers, "dw")
		nbanks = _getattr_all(controllers, "nbanks")
		req_queue_size = _getattr_all(controllers, "req_queue_size")
		read_latency = _getattr_all(controllers, "read_latency")
		write_latency = _getattr_all(controllers, "write_latency")

		bank_bits = log2_int(nbanks, False)
		controller_bits = log2_int(ncontrollers, False)
		self.masters = [Interface(rca_bits + bank_bits + controller_bits, dw, 1, req_queue_size, read_latency, write_latency)
			for i in range(nmasters)]

		###

		m_ca, m_ba, m_rca = self._split_master_addresses(controller_bits, bank_bits, rca_bits, cba_shift)
		
		for nc, controller in enumerate(controllers):
			if controller_bits:
				controller_selected = [ca == nc for ca in m_ca]
			else:
				controller_selected = [1]*nmasters
			master_req_acks = [0]*nmasters
			master_dat_acks = [0]*nmasters
			for nb in range(nbanks):
				bank = getattr(controller, "bank"+str(nb))

				# arbitrate
				rr = roundrobin.RoundRobin(nmasters, roundrobin.SP_CE)
				self.submodules += rr
				bank_selected = [cs & (ba == nb) for cs, ba in zip(controller_selected, m_ba)]
				bank_requested = [bs & master.stb for bs, master in zip(bank_selected, self.masters)]
				self.comb += [
					rr.request.eq(Cat(*bank_requested)),
					rr.ce.eq(~bank.stb & ~bank.lock)
				]

				# route requests
				self.comb += [
					bank.adr.eq(Array(m_rca)[rr.grant]),
					bank.we.eq(Array(self.masters)[rr.grant].we),
					bank.stb.eq(Array(bank_requested)[rr.grant])
				]
				master_req_acks = [master_req_ack | ((rr.grant == nm) & bank_selected[nm] & bank.req_ack)
					for nm, master_req_ack in enumerate(master_req_acks)]
				master_dat_acks = [master_dat_ack | ((rr.grant == nm) & bank.dat_ack)
					for nm, master_dat_ack in enumerate(master_dat_acks)]

			self.comb += [master.req_ack.eq(master_req_ack) for master, master_req_ack in zip(self.masters, master_req_acks)]
			self.comb += [master.dat_ack.eq(master_dat_ack) for master, master_dat_ack in zip(self.masters, master_dat_acks)]

			# route data writes
			controller_selected_wl = controller_selected
			for i in range(write_latency):
				n_controller_selected_wl = [Signal() for i in range(nmasters)]
				self.sync += [n.eq(o) for n, o in zip(n_controller_selected_wl, controller_selected_wl)]
				controller_selected_wl = n_controller_selected_wl
			dat_w_maskselect = []
			dat_we_maskselect = []
			for master, selected in zip(self.masters, controller_selected_wl):
				o_dat_w = Signal(dw)
				o_dat_we = Signal(dw//8)
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
		if controller_bits:
			for master in self.masters:
				controller_sel = Signal(controller_bits)
				for nc, controller in enumerate(controllers):
					for nb in range(nbanks):
						bank = getattr(controller, "bank"+str(nb))
						self.comb += If(bank.stb & bank.ack, controller_sel.eq(nc))
				for i in range(read_latency):
					n_controller_sel = Signal(controller_bits)
					self.sync += n_controller_sel.eq(controller_sel)
					controller_sel = n_controller_sel
				self.comb += master.dat_r.eq(Array(controllers)[controller_sel].dat_r)
		else:
			self.comb += [master.dat_r.eq(controllers[0].dat_r) for master in self.masters]

	def _split_master_addresses(self, controller_bits, bank_bits, rca_bits, cba_shift):
		m_ca = []	# controller address
		m_ba = []	# bank address
		m_rca = []	# row and column address
		for master in self.masters:
			cba = Signal(controller_bits + bank_bits)
			rca = Signal(rca_bits)
			cba_upper = cba_shift + controller_bits + bank_bits
			self.comb += cba.eq(master.adr[cba_shift:cba_upper])
			if cba_shift < rca_bits:
				if cba_shift:
					self.comb += rca.eq(Cat(master.adr[:cba_shift], master.adr[cba_upper:]))
				else:
					self.comb += rca.eq(master.adr[cba_upper:])
			else:
				self.comb += rca.eq(master.adr[:cba_shift])

			if controller_bits:
				ca = Signal(controller_bits)
				ba = Signal(bank_bits)
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
			if self.transaction is not None and s.rd(self.bus.ack):
				s.wr(self.bus.stb, 0)
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

class Target(Module):
	def __init__(self, model, *ifargs, **ifkwargs):
		self.model = model
		self.bus = Interface(*ifargs, **ifkwargs)
		self.rd_pipeline = [None]*self.bus.read_latency
		self.wr_pipeline = [None]*(self.bus.write_latency + 1)

	def do_simulation(self, s):
		# determine banks with pending requests
		pending_banks = set()
		for nb in range(self.bus.nbanks):
			bank = getattr(self.bus, "bank"+str(nb))
			if s.rd(bank.stb) and not s.rd(bank.ack):
				pending_banks.add(nb)

		# issue new transactions
		selected_bank_n = self.model.select_bank(pending_banks)
		for nb in range(self.bus.nbanks):
			bank = getattr(self.bus, "bank"+str(nb))
			if nb == selected_bank_n:
				s.wr(bank.ack, 1)
			else:
				s.wr(bank.ack, 0)
		
		rd_transaction = None
		wr_transaction = None
		if selected_bank_n >= 0:
			selected_bank = getattr(self.bus, "bank"+str(selected_bank_n))
			if s.rd(selected_bank.we):
				wr_transaction = selected_bank_n, s.rd(selected_bank.adr)
			else:
				rd_transaction = selected_bank_n, s.rd(selected_bank.adr)

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
