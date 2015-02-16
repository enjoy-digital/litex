from config import *

wb.open()
regs = wb.regs
###
regs.phy_crg_reset.write(1)
print("sysid     : 0x%04x" %regs.identifier_sysid.read())
print("revision  : 0x%04x" %regs.identifier_revision.read())
print("frequency : %d MHz" %(regs.identifier_frequency.read()/1000000))
SRAM_BASE = 0x02000000
wb.write(SRAM_BASE, [i for i in range(64)])
print(wb.read(SRAM_BASE, 64))
###
wb.close()
