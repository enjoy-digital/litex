import time
from config import *
from tools import *

wb.open()
regs = wb.regs
###
i = 0
data_errors = 0
ctrl_errors = 0
while True:
	regs.bist_sector.write(i)
	regs.bist_count.write(4)
	regs.bist_start.write(1)
	while (regs.bist_done.read() != 1):
		time.sleep(0.01)
	data_errors += regs.bist_data_errors.read()
	ctrl_errors += regs.bist_ctrl_errors.read()
	if i%10 == 0:
		print("sector %08d / data_errors %0d / ctrl_errors %d " %(i, data_errors, ctrl_errors))
		data_errors = 0
		ctrl_errors = 0
	i += 1
###
wb.close()
