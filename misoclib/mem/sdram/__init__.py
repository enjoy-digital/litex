from collections import namedtuple

PhySettingsT = namedtuple("PhySettings", "memtype dfi_databits nphases rdphase wrphase rdcmdphase wrcmdphase cl cwl read_latency write_latency")
def PhySettings(memtype, dfi_databits, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, read_latency, write_latency, cwl=0):
	return PhySettingsT(memtype, dfi_databits, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, cwl, read_latency, write_latency)

GeomSettingsT = namedtuple("_GeomSettings", "databits bankbits rowbits colbits addressbits")
def GeomSettings(databits, bankbits, rowbits, colbits):
	return GeomSettingsT(databits, bankbits, rowbits, colbits, max(rowbits, colbits))

TimingSettings = namedtuple("TimingSettings", "tRP tRCD tWR tWTR tREFI tRFC")
