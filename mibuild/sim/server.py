# This file is Copyright (c) 2015 Florent Kermarrec <florent@enjoy-digital.fr>
# License: BSD

import socket
import os
import pty
import time
import threading
import subprocess
import struct
import fcntl

messages= {
	"EXIT":		0,
	"ACK":		1,
	"ERROR": 	2,
	"UART": 	3,
	"ETHERNET":	4
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

		os.system("openvpn --mktun --dev tap0")
		os.system("ip link set tap0 up")
		os.system("ip addr add 192.169.0.14/24 dev tap0")
		os.system("iface tap0 inet")
		os.system("mknod /dev/net/tap c 10 200")
		os.system("chmod 600 /dev/net/tap")


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
		os.system("openvpn --rmtun --dev tap0")
		os.system("rm -f /dev/net/tap")
		self._cleanup_file()

# XXX proof of concept
server = VerilatorServer()
server.accept()
print("Connection accepted")

TUNSETIFF	= 0x400454ca
IFF_TAP		= 0x0002
IFF_NO_PI 	= 0x1000

def read():
	while True:
		packet = server.recv()
		if packet is not None:
			if packet[0] == messages["UART"]:
				c = bytes(chr(packet[1]).encode('utf-8'))
				os.write(server.serial, c)
			elif packet[0] == messages["ETHERNET"]:
				tap = os.open("/dev/net/tun", os.O_RDWR)
				fcntl.ioctl(tap, TUNSETIFF, struct.pack("16sH", b"tap0", IFF_TAP | IFF_NO_PI))
				os.write(tap, packet[1+8:-4])
				os.close(tap)
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

try:
    while True:
       time.sleep(1)
except KeyboardInterrupt:
	server.close()

