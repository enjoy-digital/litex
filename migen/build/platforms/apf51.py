from migen.build.generic_platform import *
from migen.build.xilinx import XilinxPlatform


_ios = [
    ("clk3", 0, Pins("N8"), IOStandard("LVCMOS33")),
    ("clko", 0, Pins("N7"), IOStandard("LVCMOS33")),
    ("fpga_initb", 0, Pins("P3"), IOStandard("LVCMOS33")),
    ("fpga_program", 0, Pins("R2"), IOStandard("LVCMOS33")),
    ("eim", 0,
        Subsignal("bclk", Pins("N12")),
        Subsignal("eb1", Pins("P13")),
        Subsignal("cs1", Pins("R11")),
        Subsignal("cs2", Pins("N9")),
        Subsignal("lba", Pins("R9")),
        Subsignal("eb0", Pins("P7")),
        Subsignal("oe", Pins("R7")),
        Subsignal("rw", Pins("R6")),
        Subsignal("dtack", Pins("N4")),
        Subsignal("wait", Pins("R4")),
        Subsignal("da", Pins("N6 L5 L6 R5 P5 N11 M11 P11 L8 K8 M8 M10 L9 R10 N5 M5")),
        IOStandard("LVCMOS33")
    )
]

_connectors = [
        ("J2",
            "None",  # No 0 pin
            "None",  # 1 FPGA Bank1 power
            "None",  # 2 FPGA Bank1 power
            "None",  # 3 GND
            "B14",  # 4 IO_L1P_A25_1
            "B15",  # 5 IO_L1N_A24_VREF_1
            "C14",  # 6 IO_L33P_A15_M1A10_1
            "C15",  # 7 IO_L33N_A14_M1A4_1
            "D13",  # 8 IO_L35P_A11_M1A7_1
            "D15",  # 9 IO_L35N_A10_M1A2_1
            "E14",  # 10 IO_L37P_A7_M1A0_1
            "E15",  # 11 IO_L37N_A6_M1A1_1
            "None",  # 12 GND
            "F13",  # 13 IO_L39P_M1A3_1
            "F15",  # 14 IO_L39N_M1ODT_1
            "G14",  # 15 IO_L41P_GCLK9_IRDY1_M1RASN_1
            "G15",  # 16 IO_L41N_GCLK8_M1CASN_1
            "H13",  # 17 IO_L42P_GCLK7_M1UDM_1
            "H15",  # 18 IO_L42N_GCLK6_TRDY1_M1LDM
            "J14",  # 19 IO_L43P_GCLK5_M1DQ4_1
            "J15",  # 20 IO_L43N_GCLK4_M1DQ5_1
            "K13",  # 21 IO_L44P_A3_M1DQ6_1
            "K15",  # 22 IO_L44N_A2_M1DQ7_1
            "L14",  # 23 IO_L45P_A1_M1LDQS_1
            "L15",  # 24 IO_L45N_A0_M1LDQSN_1
            "None",  # 25 GND
            "E2",  # 26 IO_L52P_M3A8_3
            "E1",  # 27 IO_L52N_M3A9_3
            "D3",  # 28 IO_L54P_M3RESET_3
            "D1",  # 29 IO_L54N_M3A11_3
            "F3",  # 30 IO_L46P_M3CLK_3
            "F1",  # 31 IO_L46N_M3CLKN_3
            "G2",  # 32 IO_L44P_GCLK21_M3A5_3
            "G1",  # 33 IO_L44N_GCLK20_M3A6_3
            "H3",  # 34 IO_L42P_GCLK25_TRDY2_M3UDM_3
            "H1",  # 35 IO_L42N_GCLK24_M3LDM_3
            "K3",  # 36 IO_L40P_M3DQ6_3
            "K1",  # 37 IO_L40N_M3DQ7_3
            "None",  # 38 GND
            "None",  # 39 GPIO4_16
            "None",  # 40 GPIO4_17
            "None",  # 41 BOOT_MODE0
            "None",  # 42 AUD5_RXFS
            "None",  # 43 AUD5_RXC
            "None",  # 44 GND
            "None",  # 45 AUD5_RXD
            "None",  # 46 AUD5_TXC
            "None",  # 47 AUD5_TXFS
            "None",  # 48 GND
            "None",  # 49 SPI2_SCLK_GPT_CMPOUT3
            "None",  # 50 SPI2_MISO
            "None",  # 51 SPI2_MOSI
            "None",  # 52 SPI2_SS1
            "None",  # 53 SPI2_SS2
            "None",  # 54 SPI2_SS3
            "None",  # 55 SPI2_RDY
            "None",  # 56 OWIRE
            "None",  # 57 GND
            "None",  # 58 SPI1_SCLK
            "None",  # 59 SPI1_MISO
            "None",  # 60 SPI1_MOSI
            "None",  # 61 SPI1_SS0
            "None",  # 62 SPI1_SS1
            "None",  # 63 SPI1_RDY
            "None",  # 64 RESET#
            "None",  # 65 VIO_H2
            "None",  # 66 PMIC_GPIO6
            "None",  # 67 TOUCH_X+
            "None",  # 68 TOUCH_X-
            "None",  # 69 TOUCH_Y+
            "None",  # 70 TOUCH_Y-
            "None",  # 71 AUXADCIN4
            "None",  # 72 AUXADCIN3
            "None",  # 73 AUXADCIN2
            "None",  # 74 AUXADCIN1
            "None",  # 75 PMIC_GPIO7
            "None",  # 76 +1v8
            "None",  # 77 RESERVED
            "None",  # 78 UART3_TXD
            "None",  # 79 UART_3_RXD
            "None",  # 80 UART2_TXD
            "None",  # 81 UART2_RXD
            "None",  # 82 UART2_RTS_KEY_COL7
            "None",  # 83 UART2_CTS_KEY_COL6
            "None",  # 84 UART1_TXD
            "None",  # 85 UART1_RXD
            "None",  # 86 UART1_RTS
            "None",  # 87 UART1_CTS
            "None",  # 88 GND
            "None",  # 89 AUD3_TXD
            "None",  # 90 AUD3_RXD
            "None",  # 91 AUD3_FS
            "None",  # 92 AUD3_CK
            "None",  # 93 GND
            "None",  # 94 AUD6_TXFS_KEY_ROW7
            "None",  # 95 AUD6_TXC_KEY_ROW6
            "None",  # 96 AUD6_RXD_KEY_ROW5
            "None",  # 97 AUD6_TXD_KEY_ROW4
            "None",  # 98 I2C2_SDA_UART3_CTS
            "None",  # 99 I2C2_SCL_UART3_RTS
            "None",  # 100 BOOT_MODE1
            "None",  # 101 PWM2
            "None",  # 102 PWM1
            "None",  # 103 GND
            "L1",  # 104 IO_L39N_M3LDQSN_3
            "L2",  # 105 IO_L39P_M3LDQS_3
            "J1",  # 106 IO_L41N_GCLK26_M3DQ5_3
            "J2",  # 107 IO_L41P_GCLK27_M3DQ4_3
            "J3",  # 108 IO_L43N_GCLK22_IRDY2_M3CASN_3
            "K4",  # 109 IO_L43P_GCLK23_M3RASN_3
            "J4",  # 110 IO_L45N_M3ODT_3
            "K5",  # 111 IO_L45P_M3A3_3
            "C1",  # 112 IO_L83N_VREF_3
            "C2",  # 113 IO_L83P_3
            "E3",  # 114 IO_L53N_M3A12_3
            "D4",  # 115 IO_L53P_M3CKE_3
            "None",  # 116 GND
            "P15",  # 117 IO_L74N_DOUT_BUSY_1
            "P14",  # 118 IO_L74P_AWAKE_1
            "N15",  # 119 IO_L47N_LDC_M1DQ1_1
            "N14",  # 120 IO_L47P_FWE_B_M1DQ0_1
            "M15",  # 121 IO_L46N_FOE_B_M1DQ3_1
            "M13",  # 122 IO_L46P_FCS_B_M1DQS2_1
            "L12",  # 123 IO_L40N_GCLK10_M1A6_1
            "K12",  # 124 IO_L40P_GCLK11_M1A5_1
            "K11",  # 125 IO_L38N_A4_M1CLKN_1
            "K10",  # 126 IO_L38P_A5_M1CLK_1
            "J13",  # 127 IO_L36N_A8_M1BA1_1
            "J11",  # 128 IO_L36P_A9_M1BA0_1
            "None",  # 129 GND
            "G13",  # 130 IO_L34N_A12_M1BA2_1_NOTLX4
            "H12",  # 131 IO_L34P_A13_M1WE_1_NOTLX4
            "H11",  # 132 IO_L32N_A16_M1A9_1_NOTLX4
            "H10",  # 133 IO_L32P_A17_M1A8_1_NOTLX4
            "F12",  # 134 IO_L31N_A18_M1A12_1_NOTLX4
            "F11",  # 135 IO_L31P_A19_M1CKE_1_NOTLX4
            "G12",  # 136 IO_L30N_A20_M1A11_1_NOTLX4
            "G11",  # 137 IO_L30P_A21_M1RESET_1_NOTLX4
            "None",  # 138 GND
            "None",  # 139 FPGA_BANK3_POWER
            "None")  # 140 FPGA_BANK3_POWER
]


class Platform(XilinxPlatform):
    default_clk_name = "clk3"
    default_clk_period = 10.526

    def __init__(self):
        XilinxPlatform.__init__(self, "xc6slx9-2csg225", _ios, _connectors)
