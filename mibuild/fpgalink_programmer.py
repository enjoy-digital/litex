
import os

from mibuild.generic_programmer import GenericProgrammer
from mibuild.xilinx.programmer import _create_xsvf

import fpgalink3
fpgalink3.flInitialise(0)


class FPGALink(GenericProgrammer):
    """Using the fpgalink library from makestuff

    You will need fpgalink library installed from
    https://github.com/makestuff/libfpgalink
    """

    needs_bitreverse = False

    def __init__(self, initial_vidpid=None, pin_cfg="D0D2D3D4",
                 fpgalink_vidpid="1D50:602B:0002", flash_proxy_basename=None):
        """
        Parameters
        ----------
        initial_vidpid : string
            The USB vendor and product id of the device before fpgalink
            firmware is loaded onto the device.

            Format is vid:pid as 4 digit hex numbers.

        pin_cfg : string
            FPGALink pin configuration string describing how the JTAG interface
            is hooked up to the programmer.

        fpgalink_vidpid : string
            The USB vendor, product and device id of the device after the
            fpgalink firmware is loaded onto the device.

            Format is vid:pid:did as 4 digit hex numbers.
            Defaults to 1D50:602B:0002 which is the makestuff FPGALink device.
        """
        GenericProgrammer.__init__(self, flash_proxy_basename)
        self.initial_vidpid = initial_vidpid
        self.fpgalink_vidpid = fpgalink_vidpid
        self.pin_cfg = pin_cfg

    def open_device(self):
        ivp = self.initial_vidpid
        vp = self.fpgalink_vidpid

        print("Attempting to open connection to FPGALink device", vp, "...")
        try:
            handle = fpgalink3.flOpen(self.fpgalink_vidpid)
        except fpgalink3.FLException as ex:
            if not ivp:
                raise FLException(
                    "Could not open FPGALink device at {0} and"
                    " no initial VID:PID was supplied".format(vp))

            print("Loading firmware into %s..." % ivp)
            fpgalink3.flLoadStandardFirmware(ivp, vp)

            print("Awaiting renumeration...")
            if not fpgalink3.flAwaitDevice(vp, 600):
                raise fpgalink3.FLException(
                    "FPGALink device did not renumerate properly"
                    " as {0}".format(vp))

            print("Attempting to open connection to FPGALink device", vp,
                  "again...")
            handle = fpgalink3.flOpen(vp)

        # Only Nero capable hardware support doing programming.
        assert fpgalink3.flIsNeroCapable(handle)
        return handle

    def load_bitstream(self, bitstream_file):
        n = 27

        xsvf_file = os.path.splitext(bitstream_file)[0]+'.xsvf'
        print("\nGenerating xsvf formatted bitstream")
        print("="*n)
        if os.path.exists(xsvf_file):
            os.unlink(xsvf_file)
        _create_xsvf(bitstream_file, xsvf_file)
        print("\n"+"="*n+"\n")

        print("Programming %s to device." % xsvf_file)
        print("="*n)
        handle = self.open_device()
        fpgalink3.flProgram(handle, 'J:'+self.pin_cfg, progFile=xsvf_file)
        print("Programming successful!")
        print("="*n+"\n")
        fpgalink3.flClose(handle)

    def flash(self, address, data_file):
        raise NotImplementedError("Not supported yet.")
