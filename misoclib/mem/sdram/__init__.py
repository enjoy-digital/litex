from collections import namedtuple

PhySettingsT = namedtuple("PhySettings", "memtype dfi_d nphases rdphase wrphase rdcmdphase wrcmdphase cl cwl read_latency write_latency")
def PhySettings(memtype, dfi_d, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, read_latency, write_latency, cwl=0):
	return PhySettingsT(memtype, dfi_d, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, cwl, read_latency, write_latency)

GeomSettingsT = namedtuple("_GeomSettings", "bank_a row_a col_a mux_a")
def GeomSettings(bank_a, row_a, col_a):
	return GeomSettingsT(bank_a, row_a, col_a, max(row_a, col_a))

TimingSettings = namedtuple("TimingSettings", "tRP tRCD tWR tWTR tREFI tRFC" \
	" req_queue_size read_time write_time")
