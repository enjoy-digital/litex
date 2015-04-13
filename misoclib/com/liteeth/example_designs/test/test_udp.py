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
        while((ref[0] != res[0]) and (len(res) > 1)):
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
        r.append(seed_to_data(seed, True)%0xff)  # XXX FIXME
        seed += 1
    return r, seed


def test(fpga_ip, udp_port, test_size):
    tx_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock  = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    rx_sock.bind(("", udp_port))

    def receive():
        rx_seed = 0
        while rx_seed < test_size:
            data, addr = rx_sock.recvfrom(8192)
            rx_packet = []
            for byte in data:
                rx_packet.append(int(byte))
            rx_reference_packet, rx_seed = generate_packet(rx_seed, 1024)
            s, l, e = check(rx_reference_packet, rx_packet)
            print("shift " + str(s) + " / length " + str(l) + " / errors " + str(e))

    def send():
        tx_seed = 0
        while tx_seed < test_size:
            tx_packet, tx_seed = generate_packet(tx_seed, 1024)
            tx_sock.sendto(bytes(tx_packet), (fpga_ip, udp_port))
            time.sleep(0.001)  # XXX: FIXME, Python limitation?

    receive_thread = threading.Thread(target=receive)
    receive_thread.start()

    send_thread = threading.Thread(target=send)
    send_thread.start()

    try:
        send_thread.join(10)
        receive_thread.join(0.1)
    except KeyboardInterrupt:
        pass


def main(wb):
    test("192.168.0.42", 6000, 128*KB)
    test("192.168.0.42", 8000, 128*KB)
