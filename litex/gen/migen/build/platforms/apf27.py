from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


_ios = [
    ("clk0", 0, Pins("N9"), IOStandard("LVCMOS18")),
    ("fpga_reset", 0, Pins("T9"), IOStandard("LVCMOS18"), Drive("8")),
    ("fpga_initb", 0, Pins("T12"), IOStandard("LVCMOS18"), Drive("8")),
    ("weim", 0,
        Subsignal("cs4_dtack", Pins("R3"), IOStandard("LVCMOS18"), Drive("8")),
        Subsignal("cs5n", Pins("P10"), IOStandard("LVCMOS18")),
        Subsignal("eb0n", Pins("P9"), IOStandard("LVCMOS18")),
        Subsignal("oen", Pins("R9"), IOStandard("LVCMOS18")),
        Subsignal("data",
                  Pins("T5 T6 P7 N8 P12 T13 R13 T14 P5 N6 T3 T11 T4 R5 M10 T10"),
                  IOStandard("LVCMOS18"), Drive("8")),
        Subsignal("addr",
                  Pins("N5 L7 M7 M8 L8 L9 L10 M11 P11 N11 N12 P13"),
                  IOStandard("LVCMOS18"))
     )
]

_connectors = [
   ("J2",
        "None",  # no 0 pin
        "None",  # 1 +3v3
        "None",  # 2 +3v3
        "None",  # 3 GND
        "None",  # 4 GND
        "None",  # 5 DP USB_OTG_PHY +3V3
        "None",  # 6 DM USB_OTG_PHY +3V3
        "None",  # 7 VBUS USB_OTG_ PHY +3V3
        "None",  # 8 PSW_N USB_OTG_PHY +3V3
        "None",  # 9 ID USB_OTG_PHY +3V3
        "None",  # 10 FAULT USB_OTG_PHY +3V3
        "None",  # 11 RXP Ethernet_PHY +3V3
        "None",  # 12 RXN Ethernet_PHY +3V3
        "None",  # 13 ETH_LINK Ethernet_PHY +2V8
        "None",  # 14 PC_VS2 PC +2V8 PF13
        "None",  # 15 PC_VS1 PC +2V8 PF14
        "None",  # 16 PC_PWRON PC +2V8 PF16
        "None",  # 17 PC_READY PC +2V8 PF17
        "None",  # 18 PWM0 PWM0 +2V8 PE5
        "None",  # 19 TOUT GPT +2V8 PC14
        "None",  # 20 GND POWER
        "None",  # 21 VCC01 (IN) BANK1 SUPPLY VCCO1
        "C16",  # 22 IO_L24P_1 FPGA_BANK1 VCC01
        "C15",  # 23 IO_L24N_1 FPGA_BANK1 VCC01
        "D16",  # 24 IO_L22_P1 FPGA_BANK1 VCC01
        "None",  # 25 GND POWER
        "B14",  # 26 IO_L02N_0 FPGA_BANK0 VCCO0
        "B15",  # 27 IO_L02P_0 FPGA_BANK0
        "A13",  # 28 IO_L04N_0 FPGA_BANK0
        "A14",  # 29 IO_L04P_0 FPGA_BANK0 VCCO0
        "D11",  # 30 IO_L03N_0 FPGA_BANK0 VCCO0
        "C12",  # 31 IO_L03P_0 FPGA_BANK0 VCCO0
        "A10",  # 32 IO_L08N_0 FPGA_BANK0 VCCO0
        "B10",  # 33 IO_L08P_0 FPGA_BANK0 VCCO0
        "A9",  # 34 IO_L10N_0 / GLCK7 FPGA_BANK0 VCCO0
        "C9",  # 35 IO_L10P_0 / GCLK6 FPGA_BANK0 VCCO0
        "B8",  # 36 IO_L12N_0 / GCLK11 FPGA_BANK0 VCCO0
        "A8",  # 37 IO_L12P_0 / GCLK10 FPGA_BANK0 VCCO0
        "B6",  # 38 IO_L15N_0 FPGA_BANK0 VCCO0
        "A6",  # 39 IO_L15P_0 FPGA_BANK0 VCCO0
        "B4",  # 40 IO_L18N_0 FPGA_BANK0 VCCO0
        "A4",  # 41 IO_L18P_0 FPGA_BANK0 VCCO0
        "None",  # 42 GND POWER
        "N3",  # 43 IO_L24P_3 FPGA_BANK3 VCCO3
        "R1",  # 44 IO_L23P_3 FPGA_BANK3 VCCO3
        "P1",  # 45 IO_L22N_3 FPGA_BANK3 VCCO3
        "N1",  # 46 IO_L20N_3 FPGA_BANK3 VCCO3
        "M1",  # 47 IO_L20P_3 FPGA_BANK3 VCCO3
        "H3",  # 48 IO_L12P_3 FPGA_BANK3 VCCO3
        "K1",  # 49 IO_L15N_3 FPGA_BANK3 VCCO3
        "J1",  # 50 IO_L14N_3 FPGA_BANK3 VCCO3
        "H1",  # 51 IO_L11N_3 FPGA_BANK3 VCCO3
        "G1",  # 52 IO_L08N_3 FPGA_BANK3 VCCO3
        "F1",  # 53 IO_L08P_3 FPGA_BANK3 VCCO3
        "E1",  # 54 IO_L03N_3 FPGA_BANK3 VCCO3
        "D1",  # 55 IO_LO3P_3 FPGA_BANK3 VCCO3
        "C1",  # 56 IO_L01N_3 FPGA_BANK3 VCCO3
        "None",  # 57 GND POWER
        "None",  # 58 TRSTN JTAG +2V8
        "None",  # 59 TDI JTAG +2V8
        "None",  # 60 TCK JTAG +2V8
        "None",  # 61 TDO JTAG +2V8
        "None",  # 62 TMS JTAG +2V8
        "None",  # 63 GND POWER
        "C2",  # 64 IO_L01P_3 FPGA_BANK3 VCCO3
        "D3",  # 65 IO_L02N_3 FPGA_BANK3 VCCO3
        "D4",  # 66 IO_L02P_3 FPGA_BANK3 VCCO3
        "F4",  # 67 IP_LO4N_3 FPGA_BANK3 VCCO3
        "G2",  # 68 IO_L11P_3 FPGA_BANK3 VCCO3
        "J2",  # 69 IO_L14P_3 FPGA_BANK3 VCCO3
        "K3",  # 70 IO_L15P_3 FPGA_BANK3 VCCO3
        "J3",  # 71 IO_L12N_3 FPGA_BANK3 VCCO3
        "N2",  # 72 IO_L22P_3 FPGA_BANK3 VCCO3
        "P2",  # 73 IO_L23N_3 FPGA_BANK3 VCCO3
        "M4",  # 74 IO_L24N_3 FPGA_BANK3 VCCO3
        "L6",  # 75 IP_L25N_3 FPGA_BANK3 VCCO3
        "None",  # 76 VCCO3 (IN) BANK3 SUPPLY VCCO3 (3.3Vmax)
        "None",  # 77 VCCO3 (IN) BANK3 SUPPLY VCCO3 (3.3Vmax)
        "A3",  # 78 IO_L19P_0 FPGA_BANK0 VCCO0
        "B3",  # 79 IO_L19N_0 FPGA_BANK0 VCCO0
        "A5",  # 80 IO_L17P_0 FPGA_BANK0 VCCO0
        "C5",  # 81 IO_L17N_0 FPGA_BANK0 VCCO0
        "D7",  # 82 IO_L16P_0 FPGA_BANK0 VCCO0
        "C6",  # 83 IO_L16N_0 FPGA_BANK0 VCCO0
        "C8",  # 84 IO_L11P_0 / GCLK8 FPGA_BANK0 VCCO0
        "D8",  # 85 IO_L11N_0 / GCLK9 FPGA_BANK0 VCCO0
        "C10",  # 86 IO_L09P_0 / GCLK4 FPGA_BANK0 VCCO0
        "D9",  # 87 IO_L09N_0 / GCLK5 FPGA_BANK0 VCCO0
        "C11",  # 88 IO_L07P_0 FPGA_BANK0 VCCO0
        "A11",  # 89 IO_L07N_0 FPGA_BANK0 VCCO0
        "D13",  # 90 IO_L01P_0 FPGA_BANK0 VCCO0
        "C13",  # 91 IO_L01N_0 FPGA_BANK0 VCCO0
        "None",  # 92 VCCO0 (IN) BANK0 SUPPLY VCCO0 (3.3Vmax)
        "None",  # 93 VCCO0 (IN) BANK0 SUPPLY VCCO0 (3.3Vmax)
        "None",  # 94 GND POWER VCCO0 A13
        "D15",  # 95 IO_L22N_1 FPGA_BANK1 VCC01
        "E13",  # 96 IO_L23P_1 FPGA_BANK1 VCC01
        "D14",  # 97 IO_L23N_1 FPGA_BANK1 VCC01
        "E14",  # 98 IO_L20P_1 FPGA_BANK1 VCC01
        "F13",  # 99 IO_L20N_1 FPGA_BANK1 VCC01
        "None",  # 100 GND POWER (3.3Vmax)
        "None",  # 101 USR_RESETN (open CONFIG Pos PC15 +2V8 drain with pullup)
        "None",  # 102 TIN GPT +2V8
        "None",  # 103 EXTAL_26M CONFIG +2V5
        "None",  # 104 RX3 RS232_3 RS232
        "None",  # 105 TX3 RS232_3 RS232
        "None",  # 106 RX1 RS232_1 RS232
        "None",  # 107 TX1 RS232_1 RS232
        "None",  # 108 BOOT CONFIG +2V8
        "None",  # 109 TXN Ethernet_PHY +3V3
        "None",  # 110 TXP Ethernet_PHY +3V3
        "None",  # 111 ETH_ACTIVITY Ethernet_PHY +2V8
        "None",  # 112 USBH2_NXT USB_HOST2 +2V5 PA3
        "None",  # 113 USBH2_DIR USB_HOST2 +2V5 PA1
        "None",  # 114 USBH2_DATA7 USB_HOST2 +2V5 PA2
        "None",  # 115 USBH2_STP USB_HOST2 +2V5 PA4
        "None")  # 116 USBH2_CLK USB_HOST2 +2V5 PA0
]


class Platform(XilinxPlatform):
    default_clk_name = "clk0"
    default_clk_period = 10

    def __init__(self):
        XilinxPlatform.__init__(self, "xc3s200a-ft256-4", _ios, _connectors)
