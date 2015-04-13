import time
from misoclib.tools.litescope.host.driver.io import LiteScopeIODriver


def led_anim0(io):
    for i in range(10):
        io.write(0xA5)
        time.sleep(0.1)
        io.write(0x5A)
        time.sleep(0.1)


def led_anim1(io):
    for j in range(4):
        # Led <<
        led_data = 1
        for i in range(8):
            io.write(led_data)
            time.sleep(i*i*0.0020)
            led_data = (led_data<<1)
        # Led >>
        ledData = 128
        for i in range(8):
            io.write(led_data)
            time.sleep(i*i*0.0020)
            led_data = (led_data>>1)


def main(wb):
    io = LiteScopeIODriver(wb.regs, "io")
    wb.open()
    # # #
    led_anim0(io)
    led_anim1(io)
    print("{:02X}".format(io.read()))
    # # #
    wb.close()
