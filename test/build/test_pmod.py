import unittest

from litex.build.generic_platform import GenericPlatform
from litex.build.pmod import PmodGPIO, PmodUSBHostDual, PmodUSBUART


class TestPmod(unittest.TestCase):
    def test_gpio_generates_connector_backed_io(self):
        platform = GenericPlatform("", [], connectors=[("pmoda", "A0 A1 A2 A3 A4 A5 A6 A7")])
        platform.add_extension(PmodGPIO("pmoda").get_io(type(platform)))
        platform.request("pmoda")

        constraints = platform.constraint_manager.get_sig_constraints()
        self.assertEqual(constraints[0][1], ["A0", "A1", "A2", "A3", "A4", "A5", "A6", "A7"])

    def test_usb_uart_uses_digilent_pinout(self):
        platform = GenericPlatform("", [], connectors=[("pmodb", "B0 B1 B2 B3 B4 B5 B6 B7")])
        platform.add_extension(PmodUSBUART("pmodb").get_io(type(platform)))
        uart = platform.request("usb_uart")

        constraints = platform.constraint_manager.get_sig_constraints()
        pins_by_subsignal = {constraint[3][2]: constraint[1] for constraint in constraints}
        self.assertTrue(hasattr(uart, "tx"))
        self.assertTrue(hasattr(uart, "rx"))
        self.assertEqual(pins_by_subsignal["tx"], ["B1"])
        self.assertEqual(pins_by_subsignal["rx"], ["B2"])

    def test_usb_host_dual_can_be_added_directly(self):
        platform = GenericPlatform("", [], connectors=[("pmodb", "B0 B1 B2 B3 B4 B5 B6 B7")])
        platform.add_extension(PmodUSBHostDual("pmodb", bundled=True, name="usb_pmodb_dual"))
        usb = platform.request("usb_pmodb_dual")

        constraints = platform.constraint_manager.get_sig_constraints()
        pins_by_subsignal = {constraint[3][2]: constraint[1] for constraint in constraints}
        self.assertTrue(hasattr(usb, "dp"))
        self.assertTrue(hasattr(usb, "dm"))
        self.assertEqual(pins_by_subsignal["dp"], ["B0", "B2"])
        self.assertEqual(pins_by_subsignal["dm"], ["B1", "B3"])


if __name__ == "__main__":
    unittest.main()
