import platform
import os
import sys
import time
import threading

# XXX FTDI Communication POC

sys.path.append("../")
from ftdi import FTDIComDevice, FTDI_INTERFACE_B

def uart_console(ftdi_com):
    def read():
        while True:
            print(chr(ftdi_com.uartread()), end="")

    readthread = threading.Thread(target=read, daemon=True)
    readthread.start()

    def write():
        while True:
            for e in input():
                c = ord(e)
                ftdi_com.uartwrite(c)
            ftdi_com.uartwrite(ord("\n"))


    writethread = threading.Thread(target=write, daemon=True)
    writethread.start()


def uart_virtual(ftdi_com):
    import pty, serial
    master, slave = pty.openpty()
    s_name = os.ttyname(slave)
    ser = serial.Serial(s_name)

    def read():
        while True:
            s = ftdi_com.uartread()
            s = bytes(chr(s).encode('utf-8'))
            os.write(master, s)

    readthread = threading.Thread(target=read, daemon=True)
    readthread.start()

    def write():
        while True:
            for c in list(os.read(master, 100)):
                ftdi_com.uartwrite(c)

    writethread = threading.Thread(target=write, daemon=True)
    writethread.start()

    return s_name


ftdi_map = {
    "uart": 0,
    "dma":  1
}
ftdi_com = FTDIComDevice(FTDI_INTERFACE_B,
                         mode="asynchronous",
                         uart_tag=ftdi_map["uart"],
                         dma_tag=ftdi_map["dma"],
                         verbose=False)
ftdi_com.open()
# test DMA
for i in range(256):
    ftdi_com.dmawrite([i])
    print("%02x" %(ftdi_com.dmaread()[0]), end="")
    sys.stdout.flush()
print("")
# test UART
if platform.system() == "Windows":
    uart_console(ftdi_com) # redirect uart to console since pty does not exist on Windows platforms
else:
    s_name = uart_virtual(ftdi_com)
    print(s_name)
while True:
    time.sleep(1)
