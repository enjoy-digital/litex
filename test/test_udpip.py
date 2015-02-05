from config import *
import time

wb.open()
regs = wb.regs
###
regs.ethphy_crg_reset.write(1)
regs.ethphy_crg_reset.write(0)
time.sleep(5)
regs.bist_generator_src_port.write(0x1234)
regs.bist_generator_dst_port.write(0x5678)
regs.bist_generator_ip_address.write(0x12345678)
regs.bist_generator_length.write(64)

for i in range(16):
	regs.bist_generator_start.write(1)
	time.sleep(1)

###
wb.close()
