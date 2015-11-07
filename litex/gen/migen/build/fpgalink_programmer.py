import os

from migen.build.generic_programmer import GenericProgrammer
from migen.build.xilinx.programmer import _create_xsvf

try:
   import fl
except ImportError:
   import fpgalink3 as fl

fl.flInitialise(0)


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
            handle = fl.flOpen(self.fpgalink_vidpid)
        except fl.FLException as ex:
            if not ivp:
                raise FLException(
                    "Could not open FPGALink device at {0} and"
                    " no initial VID:PID was supplied".format(vp))

            print("Loading firmware into %s..." % ivp)
            fl.flLoadStandardFirmware(ivp, vp)

            print("Awaiting renumeration...")
            if not fl.flAwaitDevice(vp, 600):
                raise fl.FLException(
                    "FPGALink device did not renumerate properly"
                    " as {0}".format(vp))

            print("Attempting to open connection to FPGALink device", vp,
                  "again...")
            handle = fl.flOpen(vp)

        # Only Nero capable hardware support doing programming.
        assert fl.flIsNeroCapable(handle)
        print("Cable connection opened.")
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
        print("Programming device...")
        fl.flProgram(handle, "J:"+self.pin_cfg, progFile=xsvf_file)
        print("Programming successful!")
        print("="*n+"\n")
        fl.flClose(handle)

    def flash(self, address, data_file):
        raise NotImplementedError("Not supported yet.")
