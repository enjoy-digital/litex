import socket
import time
import threading

FPGA_IP = "192.168.1.40"
HOST_IP = "192.168.1.12"
UDP_PORT = 5010
MESSAGE = bytes("LiteEth UDP Loopback test", "utf-8")
tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx_sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
rx_sock.bind(("", UDP_PORT))

def receive():
    while True:
      data, addr = rx_sock.recvfrom(1024)
      print(data)

def send():
  while True:
    tx_sock.sendto(MESSAGE, (FPGA_IP, UDP_PORT))
    time.sleep(0.01)

receive_thread = threading.Thread(target=receive, daemon=True)
receive_thread.start()

send_thread = threading.Thread(target=send, daemon=True)
send_thread.start()

while True:
  time.sleep(1)
