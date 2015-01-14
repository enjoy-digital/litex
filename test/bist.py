import time
import argparse
from config import *

logical_sector_size = 512

class SATABISTDriver:
	def __init__(self, regs, name):
		self.regs = regs
		self.name = name
		for s in ["start", "sector", "count", "loops", "random", "done", "errors"]:
			setattr(self, s, getattr(regs, name + "_"+ s))

	def run(self, sector, count, loops, random):
		self.sector.write(sector)
		self.count.write(count)
		self.loops.write(loops)
		self.random.write(random)
		self.start.write(1)
		while (self.done.read() == 0):
			pass
		return self.errors.read()

class SATABISTGeneratorDriver(SATABISTDriver):
	def __init__(self, regs, name):
		SATABISTDriver.__init__(self, regs, name + "_generator")

class SATABISTCheckerDriver(SATABISTDriver):
	def __init__(self, regs, name):
		SATABISTDriver.__init__(self, regs, name + "_checker")

class Timer:
	def __init__(self):
		self.value = None

	def start(self):
		self._start = time.time()

	def stop(self):
		self._stop = time.time()
		self.value = self._stop - self._start

KB = 1024
MB = 1024*KB
GB = 1024*MB

def compute_speed(loops, count, elapsed_time, unit):
	return loops*count*logical_sector_size/unit/elapsed_time

def _get_args():
	parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
		description="""\
SATA BIST utility.
""")
	parser.add_argument("-s", "--sector", default=0, help="start sector")
	parser.add_argument("-c", "--count", default=16384, help="number of sectors per transaction")
	parser.add_argument("-l", "--loops", default=4, help="number of loop for each transaction")
	parser.add_argument("-r", "--random", default=True, help="use random data")

	return parser.parse_args()

if __name__ == "__main__":
	args = _get_args()
	wb.open()
	###
	generator = SATABISTGeneratorDriver(wb.regs, "sata_bist")
	checker = SATABISTCheckerDriver(wb.regs, "sata_bist")
	timer = Timer()

	sector = int(args.sector)
	count = int(args.count)
	loops = int(args.loops)
	random = int(args.random)
	try:
		while True:
			# generator (write data to HDD)
			timer.start()
			generator.run(sector, count, loops, random)
			timer.stop()
			write_speed = compute_speed(loops, count, timer.value, MB)

			# checker (read and check data from HDD)
			timer.start()
			errors = checker.run(sector, count, loops, random)
			timer.stop()
			read_speed = compute_speed(loops, count, timer.value, MB)
			sector += count

			print("sector=%d write_speed=%4.2fMB/sec read_speed=%4.2fMB/sec errors=%d" %(sector, write_speed, read_speed, errors))

	except KeyboardInterrupt:
		pass
	###
	wb.close()
