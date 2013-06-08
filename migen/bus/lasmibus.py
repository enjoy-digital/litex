from migen.fhdl.std import *
from migen.genlib import roundrobin
from migen.genlib.record import *
from migen.genlib.misc import optree

class Interface(Record):
	def __init__(self, aw, dw, nbanks, read_latency, write_latency):
		self.aw = aw
		self.dw = dw
		self.nbanks = nbanks
		self.read_latency = read_latency
		self.write_latency = write_latency

		bank_layout = [
			("adr",		aw,		DIR_M_TO_S),
			("we",		1,		DIR_M_TO_S),
			("stb",		1,		DIR_M_TO_S),
			("ack",		1,		DIR_S_TO_M)
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
		read_latency = _getattr_all(controllers, "read_latency")
		write_latency = _getattr_all(controllers, "write_latency")

		bank_bits = log2_int(nbanks, False)
		controller_bits = log2_int(ncontrollers, False)
		self.masters = [Interface(rca_bits + bank_bits + controller_bits, dw, 1, read_latency, write_latency)
			for i in range(nmasters)]
		masters_a = Array(self.masters)

		###

		m_ca, m_ba, m_rca = self._split_master_addresses(controller_bits, bank_bits, rca_bits, cba_shift)
		
		for nc, controller in enumerate(controllers):
			if controller_bits:
				controller_selected = [ca == nc for ca in m_ca]
			else:
				controller_selected = [1]*nmasters
			for nb in range(nbanks):
				bank = getattr(controller, "bank"+str(nb))

				# arbitrate
				rr = roundrobin.RoundRobin(nmasters, roundrobin.SP_CE)
				self.submodules += rr
				bank_selected = [cs & (ba == nb) for cs, ba in zip(controller_selected, m_ba)]
				bank_requested = [bs & master.stb for bs, master in zip(bank_selected, self.masters)]
				self.comb += [
					rr.request.eq(Cat(*bank_requested)),
					rr.ce.eq(~bank.stb | bank.ack)
				]

				# route requests
				self.comb += [
					bank.adr.eq(Array(m_rca)[rr.grant]),
					bank.we.eq(masters_a[rr.grant].we),
					bank.stb.eq(masters_a[rr.grant].stb),
					masters_a[rr.grant].ack.eq(bank.ack)
				]

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
				self.comb += rca.eq(Cat(master.adr[:cba_shift], master.adr[cba_upper:]))
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
