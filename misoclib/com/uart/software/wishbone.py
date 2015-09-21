import serial
from struct import *
from misoclib.com.uart.software.reg import *


def write_b(uart, data):
    uart.write(pack('B', data))


class UARTWishboneBridgeDriver:
    cmds = {
        "write": 0x01,
        "read":  0x02
    }
    def __init__(self, port, baudrate=115200, addrmap=None, busword=8, debug=False):
        self.port = port
        self.baudrate = str(baudrate)
        self.debug = debug
        self.uart = serial.Serial(port, baudrate, timeout=0.25)
        if addrmap is not None:
            self.regs = build_map(addrmap, busword, self.read, self.write)

    def open(self):
        self.uart.flushOutput()
        self.uart.close()
        self.uart.open()
        self.uart.flushInput()

    def close(self):
        self.uart.flushOutput()
        self.uart.close()

    def read(self, addr, burst_length=1):
        datas = []
        self.uart.flushInput()
        write_b(self.uart, self.cmds["read"])
        write_b(self.uart, burst_length)
        word_addr = addr//4
        write_b(self.uart, (word_addr >> 24) & 0xff)
        write_b(self.uart, (word_addr >> 16) & 0xff)
        write_b(self.uart, (word_addr >>  8) & 0xff)
        write_b(self.uart, (word_addr >>  0) & 0xff)
        for i in range(burst_length):
            data = 0
            for k in range(4):
                data = data << 8
                data |= ord(self.uart.read())
            if self.debug:
                print("RD {:08X} @ {:08X}".format(data, addr + 4*i))
            datas.append(data)
        if burst_length == 1:
            return datas[0]
        else:
            return datas

    def write(self, addr, data):
        if isinstance(data, list):
            burst_length = len(data)
        else:
            burst_length = 1
            data = [data]
        write_b(self.uart, self.cmds["write"])
        write_b(self.uart, burst_length)
        word_addr = addr//4
        write_b(self.uart, (word_addr >> 24) & 0xff)
        write_b(self.uart, (word_addr >> 16) & 0xff)
        write_b(self.uart, (word_addr >>  8) & 0xff)
        write_b(self.uart, (word_addr >>  0) & 0xff)
        for i in range(len(data)):
            dat = data[i]
            for j in range(4):
                write_b(self.uart, (dat >> 24) & 0xff)
                dat = dat << 8
            if self.debug:
                print("WR {:08X} @ {:08X}".format(data[i], addr + 4*i))
