import time
from config import *
from tools import *

sector_size = 512

wb.open()
regs = wb.regs
###
regs.bist_start.write(1)
last_sector = 0
while True:
	time.sleep(1)
	sector = regs.bist_sector.read()
	n_sectors = sector - last_sector
	last_sector = sector
	n_bytes = n_sectors*sector_size*4*2
	ctrl_errors = regs.bist_ctrl_errors.read()
	data_errors = regs.bist_data_errors.read()
	print("%04d MB/s / data_errors %08d / ctrl_errors %08d " %(n_bytes/(1024*1024), data_errors, ctrl_errors))
###
wb.close()
