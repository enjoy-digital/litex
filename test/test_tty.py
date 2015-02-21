import socket
import threading

test_message = "LiteEth virtual TTY Hello world"

def test(fpga_ip, udp_port, test_message):
	tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	rx_sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	rx_sock.bind(("", udp_port))

	def receive():
		data, addr = rx_sock.recvfrom(8192)
		rx_packet = []
		for byte in data:
			rx_packet.append(int(byte))
		for e in rx_packet:
			print(chr(e))

	def send():
		tx_sock.sendto(bytes(test_message, "utf-8"), (fpga_ip, udp_port))

	receive_thread = threading.Thread(target=receive)
	receive_thread.start()

	send_thread = threading.Thread(target=send)
	send_thread.start()

	try:
		send_thread.join(10)
		receive_thread.join(0.1)
	except KeyboardInterrupt:
		pass

test_message = "LiteEth virtual TTY Hello world\n"
test("192.168.1.40", 10000, test_message)
