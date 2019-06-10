
# https://github.com/torvalds/linux/blob/master/drivers/mtd/spi-nor/spi-nor.c#L2428
# * spi_nor_read_sfdp() - read Serial Flash Discoverable Parameters.
# Whatever the actual numbers of bytes for address and dummy cycles are
# for (Fast) Read commands, the Read SFDP (5Ah) instruction is always
# followed by a 3-byte address and 8 dummy clock cycles.

# https://github.com/torvalds/linux/blob/master/drivers/mtd/spi-nor/spi-nor.c#L2749
# The Basic Flash Parameter Table is the main and only mandatory table as
# defined by the SFDP (JESD216) specification.
#
# It provides us with the total size (memory density) of the data array and
# the number of address bytes for Fast Read, Page Program and Sector Erase
# commands.
#
# For Fast READ commands, it also gives the number of mode clock cycles and
# wait states (regrouped in the number of dummy clock cycles) for each
# supported instruction op code.
#
# For Page Program, the page size is now available since JESD216 rev A, however
# the supported instruction op codes are still not provided.
#
# For Sector Erase commands, this table stores the supported instruction op
# codes and the associated sector sizes.
#
# Finally, the Quad Enable Requirements (QER) are also available since JESD216
# rev A. The QER bits encode the manufacturer dependent procedure to be
# executed to set the Quad Enable (QE) bit in some internal register of the
# Quad SPI memory. Indeed the QE bit, when it exists, must be set before
# sending any Quad SPI command to the memory. Actually, setting the QE bit
# tells the memory to reassign its WP# and HOLD#/RESET# pins to functions IO2
# and IO3 hence enabling 4 (Quad) I/O lines.


# Configure the SPI memory:
# - select op codes for (Fast) Read, Page Program and Sector Erase.
# - set the number of dummy cycles (mode cycles + wait states).
# - set the SPI protocols for register and memory accesses.
# - set the Quad Enable bit if needed (required by SPI x-y-4 protos).


# Clock frequency for QPI Read instructions;`
#  * 0x0b READ_FAST
#  * 0xeb READ_1_4_4
#  * 0x0c READ_FAST_4B
# with 2/4/6/8 dummy clocks 30/50/ 80/104
# with 2/4/6/8 dummy clocks 30/80/104/104 - A<1:0>=0,0
# Publication Release Date: May 22, 2014 (Revision E)
W25OpCodeDummy = {
    # The dummy clocks for various Fast Read instructions in
    # Standard/Dual/Quad SPI mode are fixed, when QPI is enabled the value
    # changes.

    # - 10.2.12 Fast Read (0Bh)
    # (when in QPI Mode - dynamic, default: 2)
    SpiNorFlashOpCodes.READ_FAST: 8,
    # - 10.2.13 Fast Read Dual Output (3Bh)
    SpiNorFlashOpCodes.READ_1_1_2: 8,
    # - 10.2.14 Fast Read Quad Output (6Bh)
    SpiNorFlashOpCodes.READ_1_1_4: 8,

    # - 10.2.16 Fast Read Quad I/O (EBh)
    # (when in QPI Mode - dynamic, default: 2)
    SpiNorFlashOpCodes.READ_1_4_4: 4,
    # - 10.2.17 Word Read Quad I/O (E7h)
    SpiNorFlashOpCodes.READ_2ALIGN_1_4_4: 2,
    # - 10.2.18 Octal Word Read Quad I/O (E3h)
    SpiNorFlashOpCodes.READ_8ALIGN_1_4_4: 0,
    # - 10.2.19 Set Burst with Wrap (77h)
    SpiNorFlashOpCodes.SET_BURST_WRAP: 24,
    # - 10.2.29 Release Power-down / Device ID (ABh) - 3 dummy bytes
    SpiNorFlashOpCodes.PWRUP_RDID: 3 * 8,
    # - 10.2.32 Read Manufacturer / Device ID Quad I/O (94h) - 4 dummy, 24bit addr = 0
    SpiNorFlashOpCodes.RDID_1_4_4: 4,
    # - 10.2.33 Read Unique ID Number (4Bh) - 4 dummy bytes
    SpiNorFlashOpCodes.RDUID: 4 * 8,
    # - 10.2.37 Read Security Registers (48h)
    SpiNorFlashOpCodes.RDSFR: 8,
}

# -------------------------------------------------------------------------------

"""
6.2.1 Dummy clock cycles NV configuration bits (NVCR bits from 15 to 12)

Table 4. Maximum allowed frequency (MHz)
Dummy Clock,FASTREAD,DOFR,DIOFR,QOFR,QIOFR
 1, 50, 50, 39, 43, 20
 2, 95, 85, 59, 56, 39
 3,105, 95, 75, 70, 49
 4,108,105, 88, 83, 59
 5,108,108, 94, 94, 69
 6,108,108,105,105, 78
 7,108,108,108,108, 86
 8,108,108,108,108, 95
 9,108,108,108,108,105
10,108,108,108,108,108

Table 3. Non-Volatile Configuration Register
NVCR<15:12> Dummy clock cycles
    0000 As '1111'
    0001 1
    0010 2
    0011 3
    0100 4
    0101 5
    0110 6
    0111 7
    1000 8
    1001 9
    1010 10
    1011 11
    1100 12
    1101 13
    1110 14
    1111 Target on maximum allowed frequency fc (108MHz) and to guarantee
         backward compatibility (default).

NVCR<3> Enable Quad Input Command
NVCR<2> Enable Dual Input Command
"""
required_dummy_clock = {
    SpiNorFlashOpCodes.FASTREAD: {
         50 * MHz: 1,
         95 * MHz: 2,
        105 * MHz: 3,
        108 * MHz: 4,
    },
    SpiNorFlashOpCodes.DOFR: {
         50 * MHz: 1,
         85 * MHz: 2,
         95 * MHz: 3,
        105 * MHz: 4,
        108 * MHz: 5,
    },
    SpiNorFlashOpCodes.DIOFR: {
         39 * MHz: 1,
         59 * MHz: 2,
         75 * MHz: 3,
         88 * MHz: 4,
         94 * MHz: 5,
        105 * MHz: 6,
        108 * MHz: 7,
    },
    SpiNorFlashOpCodes.QOFR: {
         43 * MHz: 1,
         56 * MHz: 2,
         70 * MHz: 3,
         83 * MHz: 4,
         94 * MHz: 5,
        105 * MHz: 6,
        108 * MHz: 7,
    },
    SpiNorFlashOpCodes.QIOFR: {
        20 * MHz: 1,
        39 * MHz: 2,
        49 * MHz: 3,
        59 * MHz: 4,
        69 * MHz: 5,
        78 * MHz: 6,
        86 * MHz: 7,
        95 * MHz: 8,
       105 * MHz: 9,
       108 * MHz: 10,
    },
}

