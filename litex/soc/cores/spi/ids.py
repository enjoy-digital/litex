#!/usr/bin/env python3


import enum


class CFIManufacturerIDs(enum.Enum):
    """Manufacturer IDs from the CFI standard.

    Common Flash Interface (CFI) is a standard introduced by the Joint Electron
    Device Engineering Council (JEDEC) to allow in-system or programmer reading
    of flash device characteristics, which is equivalent to having data sheet
    parameters located in the device.
    """
    AMD      = 0x0001
    AMIC     = 0x0037
    ATMEL    = 0x001F
    EON      = 0x001C
    FUJITSU  = 0x0004
    HYUNDAI  = 0x00AD
    INTEL    = 0x0089
    MACRONIX = 0x00C2
    NEC      = 0x0010
    PMC      = 0x009D
    SAMSUNG  = 0x00EC
    SHARP    = 0x00B0
    SST      = 0x00BF
    ST       = 0x0020 # STMicroelectronics
    MICRON   = 0x002C
    TOSHIBA  = 0x0098
    WINBOND  = 0x00DA


class SpiNorFlashManufacturerIDs(enum.Enum):
    """Manufacturer IDs for SPI NOR flash chips.

    The first byte returned from the flash after sending opcode SPINor_OP_RDID.
    Sometimes these are the same as CFI IDs, but sometimes they aren't.
    """
    ATMEL      = CFIManufacturerIDs.ATMEL
    GIGADEVICE = 0xc8
    INTEL      = CFIManufacturerIDs.INTEL
    ST         = CFIManufacturerIDs.ST
    MICRON     = CFIManufacturerIDs.MICRON
    MACRONIX   = CFIManufacturerIDs.MACRONIX
    SPANSION   = CFIManufacturerIDs.AMD
    SST        = CFIManufacturerIDs.SST
    WINBOND    = 0xef # Also used by some Spansion
