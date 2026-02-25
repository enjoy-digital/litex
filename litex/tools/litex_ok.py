#!/usr/bin/env python3

#
# This file is part of LiteX.
#
# Copyright (c) 2023 Andrew Elbert Wilson <Andrew.E.Wilson@ieee.org>
# SPDX-License-Identifier: BSD-2-Clause


import time
import argparse
#Dependencies for ok library
# * sudo apt install libsdl2-2.0-0
# * sudo apt install liblua5.3-0
# * udev rules for ok USB 60-opalkelly.rules
import ok


# Run ----------------------------------------------------------------------------------------------

def _get_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    parser.add_argument("bitstream",                                               help="Bitstream for XEM8320")
    return parser.parse_args()

def main():
    args = _get_args()
    print(args.bitstream)
    xem = ok.FrontPanelDevices().Open()
    if not xem:
        print ("A device could not be opened. Is one connected?")
        exit()
    devInfo = ok.okTDeviceInfo()
    if (xem.NoError != xem.GetDeviceInfo(devInfo)):
        print ("Unable to retrieve device information.")
        exit()
    print(" Product: " + devInfo.productName)
    print("Firmware version: %d.%d" % (devInfo.deviceMajorVersion, devInfo.deviceMinorVersion))
    print(" Serial Number: %s" % devInfo.serialNumber)
    print(" Device ID: %s" % devInfo.deviceID)
    tic = time.perf_counter()
    if (xem.NoError != xem.ConfigureFPGA(args.bitstream)):
        print ("FPGA configuration failed.")
    else:
        toc = time.perf_counter()
        print (f"FPGA configuration succeded in {toc - tic:0.4f} seconds")

    xem.Close()
if __name__ == "__main__":
    main()
