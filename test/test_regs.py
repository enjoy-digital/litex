from config import *

wb.open()
regs = wb.regs
###
print("sysid     : 0x%04x" %regs.identifier_sysid.read())
print("revision  : 0x%04x" %regs.identifier_revision.read())
print("frequency : %d MHz" %(regs.identifier_frequency.read()/1000000))
print("l2_size   : %d" %regs.identifier_l2_size.read())
###
wb.close()
