import socket
import time
import threading
import copy

KB = 1024
MB = 1024*KB
GB = 1024*MB

def seed_to_data(seed, random=True):
	if random:
		return (seed * 0x31415979 + 1) & 0xffffffff
	else:
		return seed

def check(p1, p2):
	p1 = copy.deepcopy(p1)
	p2 = copy.deepcopy(p2)
	if isinstance(p1, int):
		return 0, 1, int(p1 != p2)
	else:
		if len(p1) >= len(p2):
			ref, res = p1, p2
		else:
			ref, res = p2, p1
		shift = 0
		while((ref[0] != res[0]) and (len(res)>1)):
			res.pop(0)
			shift += 1
		length = min(len(ref), len(res))
		errors = 0
		for i in range(length):
			if ref.pop(0) != res.pop(0):
				errors += 1
		return shift, length, errors

def generate_packet(seed, length):
	r = []
	for i in range(length):
		r.append(seed_to_data(seed, True)%0xff) # XXX FIXME
		seed += 1
	return r, seed

FPGA_IP = "192.168.1.40"
HOST_IP = "192.168.1.12"
UDP_PORT = 6000
MESSAGE = bytes("LiteEth UDP Loopback test", "utf-8")
tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx_sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx_sock.bind(("", UDP_PORT))

def receive():
	rx_seed = 0
	while rx_seed < 1*MB:
		data, addr = rx_sock.recvfrom(1024)
		rx_packet = []
		for byte in data:
			rx_packet.append(int(byte))
		rx_reference_packet, rx_seed = generate_packet(rx_seed, 512)
		s, l, e = check(rx_reference_packet, rx_packet)
		print("shift "+ str(s) + " / length " + str(l) + " / errors " + str(e))
	done = True

def send():
	tx_seed = 0
	while tx_seed < 1*MB:
		tx_packet, tx_seed = generate_packet(tx_seed, 512)
		tx_sock.sendto(bytes(tx_packet), (FPGA_IP, UDP_PORT))
		time.sleep(0.01)

receive_thread = threading.Thread(target=receive, daemon=True)
receive_thread.start()

send_thread = threading.Thread(target=send, daemon=True)
send_thread.start()

while True:
  time.sleep(1)
