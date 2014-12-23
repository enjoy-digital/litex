import time
from config import *
from tools import *

sector_size = 512

wb.open()
###
class SATABISTDriver:
	def __init__(self, regs):
		self.regs = regs
		self.last_sector = 0
		self.last_time = time.time()
		self.last_errors = 0

	def start_loopback(self, sector, count):
		self.regs.bist_start_sector.write(sector)
		self.regs.bist_count.write(count)
		self.regs.bist_stop.write(0)
		self.regs.bist_start.write(1)

	def stop(self):
		self.regs.bist_stop.write(1)

	def show_status(self):
		errors = self.regs.bist_errors.read() - self.last_errors
		self.last_errors += errors

		sector = self.regs.bist_sector.read()
		n = sector - self.last_sector
		self.last_sector = sector

		t = self.last_time - time.time()
		self.last_time = time.time()

		print("%4.2f Mb/sec errors=%d sector=%d" %(n*512*8*2/(1024*1024), errors, sector))

bist = SATABISTDriver(wb.regs)
try:
	bist.start_loopback(0, 4)
	while True:
		bist.show_status()
		time.sleep(1)
except KeyboardInterrupt:
	pass
bist.stop()
###
wb.close()
