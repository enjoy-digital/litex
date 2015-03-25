#!/usr/bin/env python3
import sys, os, time, serial, threading, argparse
from serial.tools.miniterm import console, character, LF

sfl_magic_len = 14
sfl_magic_req = "sL5DdSMmkekro\n"
sfl_magic_ack = "z6IHG7cYDID6o\n"

# General commands
sfl_cmd_abort = 0x00
sfl_cmd_load = 0x01
sfl_cmd_jump = 0x02

# Replies
sfl_ack_success = 'K'
sfl_ack_crcerror = 'C'
sfl_ack_unknown = 'U'
sfl_ack_error = 'E'

# XXX : can we get CRC16 from a standard Python library as it's done
# for CRC32 with binascii?
crc16_table = [
	0x0000, 0x1021, 0x2042, 0x3063, 0x4084, 0x50A5, 0x60C6, 0x70E7,
	0x8108, 0x9129, 0xA14A, 0xB16B, 0xC18C, 0xD1AD, 0xE1CE, 0xF1EF,
	0x1231, 0x0210, 0x3273, 0x2252, 0x52B5, 0x4294, 0x72F7, 0x62D6,
	0x9339, 0x8318, 0xB37B, 0xA35A, 0xD3BD, 0xC39C, 0xF3FF, 0xE3DE,
	0x2462, 0x3443, 0x0420, 0x1401, 0x64E6, 0x74C7, 0x44A4, 0x5485,
	0xA56A, 0xB54B, 0x8528, 0x9509, 0xE5EE, 0xF5CF, 0xC5AC, 0xD58D,
	0x3653, 0x2672, 0x1611, 0x0630, 0x76D7, 0x66F6, 0x5695, 0x46B4,
	0xB75B, 0xA77A, 0x9719, 0x8738, 0xF7DF, 0xE7FE, 0xD79D, 0xC7BC,
	0x48C4, 0x58E5, 0x6886, 0x78A7, 0x0840, 0x1861, 0x2802, 0x3823,
	0xC9CC, 0xD9ED, 0xE98E, 0xF9AF, 0x8948, 0x9969, 0xA90A, 0xB92B,
	0x5AF5, 0x4AD4, 0x7AB7, 0x6A96, 0x1A71, 0x0A50, 0x3A33, 0x2A12,
	0xDBFD, 0xCBDC, 0xFBBF, 0xEB9E, 0x9B79, 0x8B58, 0xBB3B, 0xAB1A,
	0x6CA6, 0x7C87, 0x4CE4, 0x5CC5, 0x2C22, 0x3C03, 0x0C60, 0x1C41,
	0xEDAE, 0xFD8F, 0xCDEC, 0xDDCD, 0xAD2A, 0xBD0B, 0x8D68, 0x9D49,
	0x7E97, 0x6EB6, 0x5ED5, 0x4EF4, 0x3E13, 0x2E32, 0x1E51, 0x0E70,
	0xFF9F, 0xEFBE, 0xDFDD, 0xCFFC, 0xBF1B, 0xAF3A, 0x9F59, 0x8F78,
	0x9188, 0x81A9, 0xB1CA, 0xA1EB, 0xD10C, 0xC12D, 0xF14E, 0xE16F,
	0x1080, 0x00A1, 0x30C2, 0x20E3, 0x5004, 0x4025, 0x7046, 0x6067,
	0x83B9, 0x9398, 0xA3FB, 0xB3DA, 0xC33D, 0xD31C, 0xE37F, 0xF35E,
	0x02B1, 0x1290, 0x22F3, 0x32D2, 0x4235, 0x5214, 0x6277, 0x7256,
	0xB5EA, 0xA5CB, 0x95A8, 0x8589, 0xF56E, 0xE54F, 0xD52C, 0xC50D,
	0x34E2, 0x24C3, 0x14A0, 0x0481, 0x7466, 0x6447, 0x5424, 0x4405,
	0xA7DB, 0xB7FA, 0x8799, 0x97B8, 0xE75F, 0xF77E, 0xC71D, 0xD73C,
	0x26D3, 0x36F2, 0x0691, 0x16B0, 0x6657, 0x7676, 0x4615, 0x5634,
	0xD94C, 0xC96D, 0xF90E, 0xE92F, 0x99C8, 0x89E9, 0xB98A, 0xA9AB,
	0x5844, 0x4865, 0x7806, 0x6827, 0x18C0, 0x08E1, 0x3882, 0x28A3,
	0xCB7D, 0xDB5C, 0xEB3F, 0xFB1E, 0x8BF9, 0x9BD8, 0xABBB, 0xBB9A,
	0x4A75, 0x5A54, 0x6A37, 0x7A16, 0x0AF1, 0x1AD0, 0x2AB3, 0x3A92,
	0xFD2E, 0xED0F, 0xDD6C, 0xCD4D, 0xBDAA, 0xAD8B, 0x9DE8, 0x8DC9,
	0x7C26, 0x6C07, 0x5C64, 0x4C45, 0x3CA2, 0x2C83, 0x1CE0, 0x0CC1,
	0xEF1F, 0xFF3E, 0xCF5D, 0xDF7C, 0xAF9B, 0xBFBA, 0x8FD9, 0x9FF8,
	0x6E17, 0x7E36, 0x4E55, 0x5E74, 0x2E93, 0x3EB2, 0x0ED1, 0x1EF0
]

def crc16(l):
	crc = 0
	for d in l:
		crc = crc16_table[((crc >> 8) ^ d) & 0xff] ^ (crc << 8)
	return crc

class SFLFrame:
	def __init__(self):
		self.length = None
		self.cmd = None
		self.payload = []
		self.crc = None
		self.raw = []

	def compute_crc(self):
		crc_data = []
		crc_data.append(self.cmd)
		for d in self.payload:
			crc_data.append(d)
		self.crc = crc16(crc_data)
		return self.crc

	def encode(self):
		self.raw = []
		self.raw.append(self.length)
		self.compute_crc()
		self.raw.append((self.crc & 0xff00) >> 8)
		self.raw.append(self.crc & 0x00ff)
		self.raw.append(self.cmd)
		for d in self.payload:
			self.raw.append(d)

def get_file_data(filename):
	with open(filename, "rb") as f:
		data = []
		while True:
			w = f.read(1)
			if not w:
				break
			data.append(int.from_bytes(w, "big"))
	return data

class Flterm:
	def __init__(self, kernel_image, kernel_address):
		self.kernel_image = kernel_image
		self.kernel_address = kernel_address

		self.reader_alive = False
		self.writer_alive = False

		self.detect_magic_str = " "*len(sfl_magic_req)

	def open(self, port, speed):
		port = port if not port.isdigit() else int(port)
		self.serial = serial.Serial(port, speed, timeout=0.25)
		self.serial.flushOutput()
		self.serial.flushInput()
		self.serial.close() # in case port was not correctly closed
		self.serial.open()

	def close(self):
		self.serial.close()

	def write_exact(self, data):
		if isinstance(data, str):
			self.serial.write(bytes(data, "utf-8"))
		else:
			self.serial.write(serial.to_bytes(data))

	def send_frame(self, frame):
		frame.encode()
		retry = 1
		while retry:
			self.write_exact(frame.raw)
			# Get the reply from the device
			reply = character(self.serial.read())
			if reply == sfl_ack_success:
				retry = 0
			elif reply == sfl_ack_crcerror:
				retry = 1
			else:
				print("[FLTERM] Got unknown reply '{}' from the device, aborting.".format(reply))
				return 0
		return 1

	def upload(self, filename, address):
		data = get_file_data(filename)
		print("[FLTERM] Uploading {} ({} bytes)...".format(filename, len(data)))
		current_address = address
		position = 0
		length = len(data)
		start = time.time()
		while len(data) != 0:
			print("{}%\r".format(100*position//length), end="")
			frame = SFLFrame()
			if len(data) > 251:
				frame_data = data[:251]
			frame.length = len(frame_data)+4
			frame.cmd = sfl_cmd_load
			frame.payload.append((current_address & 0xff000000) >> 24)
			frame.payload.append((current_address & 0x00ff0000) >> 16)
			frame.payload.append((current_address & 0x0000ff00) >> 8)
			frame.payload.append((current_address & 0x000000ff) >> 0)
			for d in frame_data:
				frame.payload.append(d)
			if self.send_frame(frame) == 0:
				return
			current_address += len(frame_data)
			position += len(frame_data)
			try:
				data = data[251:]
			except:
				data = []
		end = time.time()
		elapsed = end - start
		print("[FLTERM] Upload complete ({0:.1f}KB/s).".format(length/(elapsed*1024)))
		return length

	def boot(self):
		print("[FLTERM] Booting the device.")
		frame = SFLFrame()
		frame.length = 4
		frame.cmd = sfl_cmd_jump
		frame.payload.append((self.kernel_address & 0xff000000) >> 24)
		frame.payload.append((self.kernel_address & 0x00ff0000) >> 16)
		frame.payload.append((self.kernel_address & 0x0000ff00) >> 8)
		frame.payload.append((self.kernel_address & 0x000000ff) >> 0)
		self.send_frame(frame)

	def detect_magic(self, data):
		if data is not "":
			self.detect_magic_str = self.detect_magic_str[1:] + data
			return self.detect_magic_str == sfl_magic_req
		else:
			return False

	def answer_magic(self):
		print("[FLTERM] Received firmware download request from the device.")
		if os.path.exists(self.kernel_image):
			self.write_exact(sfl_magic_ack)
			self.upload(self.kernel_image, self.kernel_address)
			self.boot()
		print("[FLTERM] Done.");

	def reader(self):
		try:
			while self.reader_alive:
				c = character(self.serial.read())
				if c == '\r':
					sys.stdout.write('\n')
				else:
					sys.stdout.write(c)
				sys.stdout.flush()

				if self.kernel_image is not None:
					if self.detect_magic(c):
						self.answer_magic()

		except serial.SerialException:
			self.reader_alive = False
			raise

	def start_reader(self):
		self.reader_alive = True
		self.reader_thread = threading.Thread(target=self.reader)
		self.reader_thread.setDaemon(True)
		self.reader_thread.start()

	def stop_reader(self):
		self.reader_alive = False
		self.reader_thread.join()

	def writer(self):
		try:
			while self.writer_alive:
				try:
					b = console.getkey()
				except KeyboardInterrupt:
					b = serial.to_bytes([3])
				c = character(b)
				if c == chr(0x03):
					self.stop()
				elif c == '\n':
					self.serial.write(LF)
				else:
					self.serial.write(b)
		except:
			self.writer_alive = False
			raise

	def start_writer(self):
		self.writer_alive = True
		self.writer_thread = threading.Thread(target=self.writer)
		self.writer_thread.setDaemon(True)
		self.writer_thread.start()

	def stop_writer(self):
		self.writer_alive = False
		self.writer_thread.join()

	def start(self):
		print("[FLTERM] Starting....")
		self.start_reader()
		self.start_writer()

	def stop(self):
		self.reader_alive = False
		self.writer_alive = False

	def join(self, writer_only=False):
		self.writer_thread.join()
		if not writer_only:
			self.reader_thread.join()

def _get_args():
	parser = argparse.ArgumentParser()
	parser.add_argument("--port", default="2", help="serial port")
	parser.add_argument("--speed", default=115200, help="serial baudrate")
	parser.add_argument("--kernel", default=None, help="kernel image")
	parser.add_argument("--kernel_adr", default=0x40000000, help="kernel address")
	return parser.parse_args()

if __name__ == "__main__":
	args = _get_args()
	flterm = Flterm(args.kernel, args.kernel_adr)
	flterm.open(args.port, args.speed)
	flterm.start()
	try:
		flterm.join(True)
	except KeyboardInterrupt:
		pass
	flterm.join()
