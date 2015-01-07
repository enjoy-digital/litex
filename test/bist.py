import time
import argparse
from config import *

logical_sector_size = 512

class SATABISTDriver:
	def __init__(self, regs):
		self.regs = regs

	def run(self, sector, count, loops, mode):
		self.regs.sata_bist_ctrl_sector.write(sector)
		self.regs.sata_bist_ctrl_count.write(count)
		self.regs.sata_bist_ctrl_loops.write(loops)
		if mode == "write":
			self.regs.sata_bist_ctrl_write.write(1)
		elif mode == "read":
			self.regs.sata_bist_ctrl_read.write(1)
		while (self.regs.sata_bist_ctrl_done.read() == 0):
			pass
		return self.regs.sata_bist_ctrl_errors.read()

	def write(self, sector, count, loops):
		self.run(sector, count, loops, "write")

	def read(self, sector, count, loops):
		return self.run(sector, count, loops, "read")

def _get_args():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
		description="""\
SATA BIST utility.
""")
	parser.add_argument("-s", "--sector", default=0, help="BIST start sector")
	parser.add_argument("-c", "--count", default=16384, help="BIST count (number of sectors per transaction)")
	parser.add_argument("-l", "--loops", default=4, help="BIST loops (number of loop for each transaction")

	return parser.parse_args()

if __name__ == "__main__":
	args = _get_args()
	wb.open()
	###
	bist = SATABISTDriver(wb.regs)
	sector = int(args.sector)
	count = int(args.count)
	loops = int(args.loops)
	try:
		write_time = 0
		read_time = 0
		while True:
			# Write
			start = time.time()
			bist.write(sector, count, loops)
			end = time.time()
			write_time = end-start
			write_speed = loops*count*logical_sector_size/(1024*1024)/write_time

			# Read
			start = time.time()
			read_errors = bist.read(sector, count, loops)
			end = time.time()
			read_time = end-start
			read_speed = loops*count*logical_sector_size/(1024*1024)/read_time

			sector += count

			print("sector=%d write_speed=%4.2fMB/sec read_speed=%4.2fMB/sec errors=%d" %(sector, write_speed, read_speed, read_errors))

	except KeyboardInterrupt:
		pass
	###
	wb.close()
