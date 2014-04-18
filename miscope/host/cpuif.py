from migen.bank.description import CSRStatus

def get_csr_csv(csr_base, bank_array):
	r = ""
	for name, csrs, mapaddr, rmap in bank_array.banks:
		reg_base = csr_base + 0x800*mapaddr
		for csr in csrs:
			nr = (csr.size + 7)//8
			r += "{}_{},0x{:08x},{},{}\n".format(name, csr.name, reg_base, nr, "ro" if isinstance(csr, CSRStatus) else "rw")
			reg_base += 4*nr
	return r
