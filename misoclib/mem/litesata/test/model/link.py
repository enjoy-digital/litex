import subprocess
import math

from misoclib.mem.litesata.common import *
from misoclib.mem.litesata.test.common import *

def print_link(s):
    print_with_prefix(s, "[LNK]: ")


def import_scrambler_datas():
    with subprocess.Popen(["./scrambler"],
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE) as process:
        process.stdin.write("0x10000".encode("ASCII"))
        out, err = process.communicate()
    return [int(e, 16) for e in out.decode("utf-8").split("\n")[:-1]]


class LinkPacket(list):
    def __init__(self, init=[]):
        self.ongoing = False
        self.done = False
        self.scrambled_datas = import_scrambler_datas()
        for dword in init:
            self.append(dword)


class LinkRXPacket(LinkPacket):
    def descramble(self):
        for i in range(len(self)):
            self[i] = self[i] ^ self.scrambled_datas[i]

    def check_crc(self):
        stdin = ""
        for v in self[:-1]:
            stdin += "0x{:08x} ".format(v)
        stdin += "exit"
        with subprocess.Popen("./crc",
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE) as process:
            process.stdin.write(stdin.encode("ASCII"))
            out, err = process.communicate()
        crc = int(out.decode("ASCII"), 16)
        r = (self[-1] == crc)
        self.pop()
        return r

    def decode(self):
        self.descramble()
        return self.check_crc()


class LinkTXPacket(LinkPacket):
    def insert_crc(self):
        stdin = ""
        for v in self:
            stdin += "0x{:08x} ".format(v)
        stdin += "exit"
        with subprocess.Popen("./crc",
                              stdin=subprocess.PIPE,
                              stdout=subprocess.PIPE) as process:
            process.stdin.write(stdin.encode("ASCII"))
            out, err = process.communicate()
        crc = int(out.decode("ASCII"), 16)
        self.append(crc)

    def scramble(self):
        for i in range(len(self)):
            self[i] = self[i] ^ self.scrambled_datas[i]

    def encode(self):
        self.insert_crc()
        self.scramble()


class LinkLayer(Module):
    def __init__(self, phy, debug=False, random_level=0):
        self.phy = phy
        self.debug = debug
        self.random_level = random_level
        self.tx_packets = []
        self.tx_packet = LinkTXPacket()
        self.rx_packet = LinkRXPacket()

        self.rx_cont = False
        self.rx_last = 0
        self.tx_cont = False
        self.tx_cont_nb = -1
        self.tx_lasts = [0, 0, 0]

        self.scrambled_datas = import_scrambler_datas()

        self.transport_callback = None

        self.send_state = ""
        self.send_states = ["RDY", "SOF", "DATA", "EOF", "WTRM"]

    def set_transport_callback(self, callback):
        self.transport_callback = callback

    def send(self, dword):
        if self.send_state == "RDY":
            self.phy.send(primitives["X_RDY"])
            if dword == primitives["R_RDY"]:
                self.send_state = "SOF"
        elif self.send_state == "SOF":
            self.phy.send(primitives["SOF"])
            self.send_state = "DATA"
        elif self.send_state == "DATA":
            if dword == primitives["HOLD"]:
                self.phy.send(primitives["HOLDA"])
            else:
                self.phy.send(self.tx_packet.pop(0))
                if len(self.tx_packet) == 0:
                    self.send_state = "EOF"
        elif self.send_state == "EOF":
            self.phy.send(primitives["EOF"])
            self.send_state = "WTRM"
        elif self.send_state == "WTRM":
            self.phy.send(primitives["WTRM"])
            if dword == primitives["R_OK"]:
                self.tx_packet.done = True
            elif dword == primitives["R_ERR"]:
                self.tx_packet.done = True
            if self.tx_packet.done:
                self.phy.send(primitives["SYNC"])

    def insert_cont(self):
        self.tx_lasts.pop(0)
        self.tx_lasts.append(self.phy.tx.dword.dat)
        self.tx_cont = True
        for i in range(3):
            if not is_primitive(self.tx_lasts[i]):
                self.tx_cont = False
            if self.tx_lasts[i] != self.tx_lasts[0]:
                self.tx_cont = False
        if self.tx_cont:
            if self.tx_cont_nb == 0:
                self.phy.send(primitives["CONT"])
            else:
                self.phy.send(self.scrambled_datas[self.tx_cont_nb])
            self.tx_cont_nb += 1
        else:
            self.tx_cont_nb = 0

    def remove_cont(self, dword):
        if dword == primitives["HOLD"]:
            if self.rx_cont:
                self.tx_lasts = [0, 0, 0]
        if dword == primitives["CONT"]:
            self.rx_cont = True
        elif is_primitive(dword):
            self.rx_last = dword
            self.rx_cont = False
        if self.rx_cont:
            dword = self.rx_last
        return dword

    def callback(self, dword):
        if dword == primitives["X_RDY"]:
            self.phy.send(primitives["R_RDY"])
        elif dword == primitives["WTRM"]:
            self.phy.send(primitives["R_OK"])
            if self.rx_packet.ongoing:
                self.rx_packet.decode()
                if self.transport_callback is not None:
                    self.transport_callback(self.rx_packet)
                self.rx_packet.ongoing = False
        elif dword == primitives["HOLD"]:
            self.phy.send(primitives["HOLDA"])
        elif dword == primitives["EOF"]:
            pass
        elif self.rx_packet.ongoing:
            if dword != primitives["HOLD"]:
                n = randn(100)
                if n < self.random_level:
                    self.phy.send(primitives["HOLD"])
                else:
                    self.phy.send(primitives["R_IP"])
                if not is_primitive(dword):
                        self.rx_packet.append(dword)
        elif dword == primitives["SOF"]:
            self.rx_packet = LinkRXPacket()
            self.rx_packet.ongoing = True

    def gen_simulation(self, selfp):
        self.tx_packet.done = True
        self.phy.send(primitives["SYNC"])
        while True:
            yield from self.phy.receive()
            if self.debug:
                print_link(self.phy)
            self.phy.send(primitives["SYNC"])
            rx_dword = self.phy.rx.dword.dat
            rx_dword = self.remove_cont(rx_dword)
            if len(self.tx_packets) != 0:
                if self.tx_packet.done:
                    self.tx_packet = self.tx_packets.pop(0)
                    self.tx_packet.encode()
                    self.send_state = "RDY"
            if not self.tx_packet.done:
                self.send(rx_dword)
            else:
                self.callback(rx_dword)
            self.insert_cont()
