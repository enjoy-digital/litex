from collections import namedtuple

PhySettingsT = namedtuple("PhySettings", "memtype dfi_databits nphases rdphase wrphase rdcmdphase wrcmdphase cl cwl read_latency write_latency")
def PhySettings(memtype, dfi_databits, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, read_latency, write_latency, cwl=0):
    return PhySettingsT(memtype, dfi_databits, nphases, rdphase, wrphase, rdcmdphase, wrcmdphase, cl, cwl, read_latency, write_latency)

GeomSettingsT = namedtuple("_GeomSettings", "bankbits rowbits colbits addressbits")
def GeomSettings(bankbits, rowbits, colbits):
    return GeomSettingsT(bankbits, rowbits, colbits, max(rowbits, colbits))

TimingSettings = namedtuple("TimingSettings", "tRP tRCD tWR tWTR tREFI tRFC")
