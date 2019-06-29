#!/usr/bin/env python3

from collections import namedtuple


SpiNorFlashOpCode = namedtuple("SpiNorFlashOpCode", "code desc")
_Op = SpiNorFlashOpCode


class SpiNorFlashOpCodes:
    """SPI NOR Flash command opcodes."""

    UNKNOWN           = _Op(0x00, "Unknown")

    # Release Power-Down / Device ID
    WREN              = _Op(0x06, "Write enable")
    RDSR              = _Op(0x05, "Read status register")
    WRSR              = _Op(0x01, "Write status register 1 byte")
    RDSR2             = _Op(0x3f, "Read status register 2")
    WRSR2             = _Op(0x3e, "Write status register 2")

    # Reading op codes
    READ              = _Op(0x03, "Read data bytes (low frequency)")
    READ_FAST         = _Op(0x0b, "Read data bytes (high frequency)")
    READ_1_1_2        = _Op(0x3b, "Read data bytes (Dual Output SPI)")
    READ_1_2_2        = _Op(0xbb, "Read data bytes (Dual I/O SPI)")
    READ_1_1_4        = _Op(0x6b, "Read data bytes (Quad Output SPI)")
    READ_1_4_4        = _Op(0xeb, "Read data bytes (Quad I/O SPI)") # Fast Read Quad
    READ_1_1_8        = _Op(0x8b, "Read data bytes (Octal Output SPI)")
    READ_1_8_8        = _Op(0xcb, "Read data bytes (Octal I/O SPI)")
    # Read opcode aliases
    FAST_READ = READ_FAST
    DQFR  = READ_1_1_2
    DIOFR = READ_1_2_2
    QOFR  = READ_1_1_4
    QUIFR = READ_1_4_4

    # FIXME: What is this?
    SET_BURST_WRAP    = _Op(0x77, "Set burst with wrap")

    # Programming op codes
    PP                = _Op(0x02, "Page program (up to 256 bytes)")
    PP_1_1_4          = _Op(0x32, "Quad page program")
    PP_1_4_4          = _Op(0x38, "Quad page program")
    PP_1_1_8          = _Op(0x82, "Octal page program")
    PP_1_8_8          = _Op(0xc2, "Octal page program")

    # Erasing op codes
    SE                = _Op(0xd8, "Sector erase (usually 64KiB)")

    BE_256            = _Op(0xdb, "Erase 256B block")
    BE_4K             = _Op(0x20, "Erase 4KiB block")
    BE_4K_PMC         = _Op(0xd7, "Erase 4KiB block on PMC chips")
    BE_32K            = _Op(0x52, "Erase 32KiB block")
    BE_ALT1           = _Op(0x50, "Erase ??? block")
    BE_ALT2           = _Op(0x81, "Erase ??? block")

    CHIP_ERASE        = _Op(0xc7, "Erase whole flash chip")
    CHIP_ERASE_ALT    = _Op(0x60, "Erase whole flash chip on some chips")
    CHIP_ERASE_ATMEL  = _Op(0x62, "Erase whole flash chip on Atmel chips")


    # Register opcodes
    RDID              = _Op(0x9f, "Read JEDEC ID")
    RDID_ATMEL        = _Op(0x15, "Read JEDEC ID on Atmel chips")
    RDSFDP            = _Op(0x5a, "Read SFDP")
    RDCR              = _Op(0x35, "Read configuration register")
    RDFSR             = _Op(0x70, "Read flag status register")
    CLFSR             = _Op(0x50, "Clear flag status register")
    RDEAR             = _Op(0xc8, "Read Extended Address Register")
    WREAR             = _Op(0xc5, "Write Extended Address Register")

    # - 10.2.29 Release Power-down / Device ID (ABh)
    # The Release from Power-down / Device ID instruction is a multi-purpose
    # instruction. It can be used to release the device from the power-down
    # state, or obtain the devices electronic identification (ID) number.
    PWRUP_RDID        = _Op(0xab, "Power up flash and read device ID")

    # - 10.2.32 Read Manufacturer / Device ID Quad I/O (94h)
    RDID_1_4_4        = _Op(0x94, "Read manufacturer and device ID (Quad I/O SPI)")
    # - 10.2.33 Read Unique ID Number (4Bh)
    RDUID             = _Op(0x4b, "Read unique ID number")

    # - 10.2.37 Read Security Registers (48h)
    RDSFR             = _Op(0x48, "Read Security Registers")
    # - Set Read Parameters (C0h), modifies behaviour of READ_FAST/READ_1_4_4/READ_FAST_4B commands.
    SET_READ_PARAMS   = _Op(0xc0, "Set read parameters")

    # 4-byte address opcodes - used on Spansion and some Macronix flashes.
    READ_4B           = _Op(0x13, "Read data bytes (low frequency)")
    READ_FAST_4B      = _Op(0x0c, "Read data bytes (high frequency)")
    READ_1_1_2_4B     = _Op(0x3c, "Read data bytes (Dual Output SPI)")
    READ_1_2_2_4B     = _Op(0xbc, "Read data bytes (Dual I/O SPI)")
    READ_1_1_4_4B     = _Op(0x6c, "Read data bytes (Quad Output SPI)")
    READ_1_4_4_4B     = _Op(0xec, "Read data bytes (Quad I/O SPI)")
    READ_1_1_8_4B     = _Op(0x7c, "Read data bytes (Octal Output SPI)")
    READ_1_8_8_4B     = _Op(0xcc, "Read data bytes (Octal I/O SPI)")

    PP_4B             = _Op(0x12, "Page program (up to 256 bytes)")
    PP_1_1_4_4B       = _Op(0x34, "Quad page program")
    PP_1_4_4_4B       = _Op(0x3e, "Quad page program")
    PP_1_1_8_4B       = _Op(0x84, "Octal page program")
    PP_1_8_8_4B       = _Op(0x8e, "Octal page program")

    BE_4K_4B          = _Op(0x21, "Erase 4KiB block")
    BE_32K_4B         = _Op(0x5c, "Erase 32KiB block")
    SE_4B             = _Op(0xdc, "Sector erase (usually 64KiB)")

    # Word Read Quad I/O - E7h
    # Address bits (A0) must equal 0
    READ_2ALIGN_1_4_4 = _Op(0xe7, "Aligned 16bit (word) read data bytes (Quad I/O SPI)")
    # Address bits (A3, A2, A1, A0) must equal 0
    READ_8ALIGN_1_4_4 = _Op(0xe3, "Aligned 128bit read data bytes (Quad I/O SPI)")

    # Double Transfer Rate opcodes - defined in JEDEC JESD216B.
    READ_1_1_1_DTR    = _Op(0x0d, "")
    READ_1_2_2_DTR    = _Op(0xbd, "")
    READ_1_4_4_DTR    = _Op(0xed, "")

    READ_1_1_1_DTR_4B = _Op(0x0e, "")
    READ_1_2_2_DTR_4B = _Op(0xbe, "")
    READ_1_4_4_DTR_4B = _Op(0xee, "")

    # Used for SST flashes only.
    BP                = _Op(0x02, "Byte program")
    WRDI              = _Op(0x04, "Write disable")

    # Used for S3AN flashes only
    XSE               = _Op(0x50, "Sector erase")
    XPP               = _Op(0x82, "Page program")
    XRDSR             = _Op(0xd7, "Read status register")

    # Used for Macronix and Winbond flashes.
    EN4B              = _Op(0xb7, "Enter 4-byte mode")
    EX4B              = _Op(0xe9, "Exit 4-byte mode")

    # Used for Spansion flashes only.
    BRWR              = _Op(0x17, "Bank register write")
    CLSR              = _Op(0x30, "Clear status register 1")

    # Used for Micron flashes only.
    RD_EVCR           = _Op(0x65, "Read EVCR register")
    WD_EVCR           = _Op(0x61, "Write EVCR register")

    # JEDEC "Auto address increment" mode.
    # - AAI supported, but opcode is 0xAF
    AAI_WP            = _Op(0xad, "Auto address increment word program")

    # JEDEC Aliases for various op codes
    JEDEC_READ              = READ          # 0x03
    JEDEC_READ_FAST         = READ_FAST     # 0x0b
    JEDEC_READ_4BA          = READ_4B       # 0x13
    JEDEC_READ_4BA_FAST     = READ_FAST_4B  # 0x0c
    JEDEC_READ_EXT_ADDR_REG = RDEAR         # 0xc8
    JEDEC_AAI_WORD_PROGRAM  = AAI_WP        # 0xad


class Features(enum.FlagEnum):
    FEATURE_ERASED_ZERO     = auto
    FEATURE_OTP             = auto
    FEATURE_WRSR_EITHER     = auto
    FEATURE_WRSR_EWSR       = auto
    FEATURE_WRSR_WREN       = auto

