# This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import socket
import os
import pty
import time
import threading

messages= {
	"EXIT":		0,
	"ACK":		1,
	"ERROR": 	2,
	"UART": 	3
}

class PacketTooLarge(Exception):
	pass

class VerilatorServer:
	def __init__(self, sockaddr="/tmp/simsocket"):
		self.sockaddr = sockaddr
		self.socket = socket.socket(socket.AF_UNIX, socket.SOCK_SEQPACKET)
		self._cleanup_file()
		self.socket.bind(self.sockaddr)
		self.socket.listen(1)

		master, slave = pty.openpty()
		self.serial = master
		self.serial_name = os.ttyname(slave)

		self.ack = False

		self._print_banner()

	def _print_banner(self):
		print("Mibuild simulation server")
		print("sockaddr: {}".format(self.sockaddr))
		print("serial: {}".format(self.serial_name))

	def _cleanup_file(self):
		try:
			os.remove(self.sockaddr)
		except OSError:
			pass

	def accept(self):
		self.conn, addr = self.socket.accept()

	def send(self, packet):
		self.conn.send(packet)

	def recv(self):
		maxlen = 2048
		packet = self.conn.recv(maxlen)
		if len(packet) < 1:
			return None
		if len(packet) >= maxlen:
			raise PacketTooLarge
		return packet

	def close(self):
		if hasattr(self, "conn"):
			self.conn.shutdown(socket.SHUT_RDWR)
			self.conn.close()
		if hasattr(self, "socket"):
			self.socket.shutdown(socket.SHUT_RDWR)
			self.socket.close()
		self._cleanup_file()

# XXX proof of concept
server = VerilatorServer()
server.accept()
print("Connection accepted")

def read():
	while True:
		packet = server.recv()
		if packet is not None:
			if packet[0] == messages["UART"]:
				c = bytes(chr(packet[1]).encode('utf-8'))
				os.write(server.serial, c)

			elif packet[0] == messages["ACK"]:
				server.ack = True

def write():
	while True:
		for c in list(os.read(server.serial, 100)):
			packet = [messages["UART"], c]
			server.send(bytes(packet))
			while not server.ack:
				pass
			server.ack = False

readthread = threading.Thread(target=read, daemon=True)
readthread.start()

writethread = threading.Thread(target=write, daemon=True)
writethread.start()

while True:
	time.sleep(1)
