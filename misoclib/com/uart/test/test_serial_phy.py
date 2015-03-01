# XXX Adapt test to new architecture
class UARTTB(Module):
	def __init__(self):
		self.clk_freq = 83333333
		self.baud = 3000000
		self.pads = Record([("rx", 1), ("tx", 1)])
		self.submodules.slave = UART(self.pads, self.clk_freq, self.baud)

	def wait_for(self, ns_time):
		freq_in_ghz = self.clk_freq/(10**9)
		period = 1/freq_in_ghz
		num_loops = int(ns_time/period)
		for i in range(num_loops+1):
			yield

	def gen_simulation(self, selfp):
		baud_in_ghz = self.baud/(10**9)
		uart_period = int(1/baud_in_ghz)
		half_uart_period = int(1/(2*baud_in_ghz))

		# Set TX an RX lines idle
		selfp.pads.tx = 1
		selfp.pads.rx = 1
		yield

		# First send a few characters

		tx_string = "01234"
		print("Sending string: " + tx_string)
		for c in tx_string:
			selfp.slave._r_rxtx.r = ord(c)
			selfp.slave._r_rxtx.re = 1
			yield
			selfp.slave._r_rxtx.re = 0

			yield from self.wait_for(half_uart_period)

			if selfp.pads.tx:
				print("FAILURE: no start bit sent")

			val = 0
			for i in range(8):
				yield from self.wait_for(uart_period)
				val >>= 1
				if selfp.pads.tx:
					val |= 0x80

			yield from self.wait_for(uart_period)

			if selfp.pads.tx == 0:
				print("FAILURE: no stop bit sent")

			if ord(c) != val:
				print("FAILURE: sent decimal value "+str(val)+" (char "+chr(val)+") instead of "+c)
			else:
				print("SUCCESS: sent "+c)
			while selfp.slave.ev.tx.trigger != 1:
				yield

		# Then receive a character

		rx_string = '5'
		print("Receiving character "+rx_string)
		rx_value = ord(rx_string)
		for i in range(11):
			if (i == 0):
				# start bit
				selfp.pads.rx = 0
			elif (i == 9):
				# stop bit
				selfp.pads.rx = 1
			elif (i == 10):
				selfp.pads.rx = 1
				break
			else:
				selfp.pads.rx = 1 if (rx_value & 1) else 0
				rx_value >>= 1
			yield from self.wait_for(uart_period)

		rx_value = ord(rx_string)
		received_value = selfp.slave._r_rxtx.w
		if (received_value == rx_value):
			print("RX SUCCESS: ")
		else:
			print("RX FAILURE: ")

		print("received "+chr(received_value))

		while True:
			yield

if __name__ == "__main__":
	from migen.sim.generic import Simulator, TopLevel
	from migen.sim import icarus
	with Simulator(UARTTB(), TopLevel("top.vcd", clk_period=int(1/0.08333333)), icarus.Runner(keep_files=False)) as s:
		s.run(20000)
