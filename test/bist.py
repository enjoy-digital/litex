import time
import argparse
from config import *

logical_sector_size = 512

class SATABISTDriver:
	def __init__(self, regs):
		self.regs = regs
		self.last_sector = 0
		self.last_time = time.time()
		self.last_errors = 0
		self.mode = "rw"

	def set_mode(self, mode):
		self.mode = mode
		self.regs.sata_bist_write_only.write(0)
		self.regs.sata_bist_read_only.write(0)
		if mode == "wr":
			self.regs.sata_bist_write_only.write(1)
		if mode == "rd":
			self.regs.sata_bist_read_only.write(1)

	def start(self, sector, count, mode):
		self.set_mode(mode)
		self.regs.sata_bist_start_sector.write(sector)
		self.regs.sata_bist_count.write(count)
		self.regs.sata_bist_stop.write(0)
		self.regs.sata_bist_start.write(1)

	def stop(self):
		self.regs.sata_bist_stop.write(1)

	def show_status(self):
		errors = self.regs.sata_bist_errors.read() - self.last_errors
		self.last_errors += errors

		sector = self.regs.sata_bist_sector.read()
		n = sector - self.last_sector
		self.last_sector = sector

		t = self.last_time - time.time()
		self.last_time = time.time()

		if self.mode in ["wr", "rd"]:
			speed_mult = 1
		else:
			speed_mult = 2
		print("%4.2f MB/sec errors=%d sector=%d" %(n*logical_sector_size*speed_mult/(1024*1024), errors, sector))


def _get_args():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
		description="""\
SATA BIST utility.
""")
	parser.add_argument("-s", "--sector", default=0, help="BIST start sector")
	parser.add_argument("-c", "--count", default=4, help="BIST count (number of sectors per transaction)")
	parser.add_argument("-m", "--mode", default="rw", help="BIST mode (rw, wr, rd")

	return parser.parse_args()

if __name__ == "__main__":
	args = _get_args()
	wb.open()
	###
	bist = SATABISTDriver(wb.regs)
	try:
		bist.start(int(args.sector), int(args.count), args.mode)
		while True:
			bist.show_status()
			time.sleep(1)
	except KeyboardInterrupt:
		pass
	bist.stop()
	###
	wb.close()
