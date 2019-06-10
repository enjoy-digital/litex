#!/usr/bin/env python3

from dataclasses import dataclass

from .ids import SpiNorFlashManufacturerIDs
from .protocol import SpiProtocol
from .opcodes import SpiNorFlashOpCode, SpiNorFlashOpCodes


def bit2bytes(bits):
    return bits / 8


kbytes = 1024

Mbit = 1024 * 1024
Gbit = 1024 * 1024 * 1024

MHz = 1000 * 1000


class MetaSizes(type):
    def _table(self, mod_name, name):
        size_name  = "{}_size".format(name)
        total_name = "total_{}s".format(name)
        ts_name    = "total_size"

        provided_size_per_unit   = getattr(self, "provided_"+size_name)
        provided_number_of_units = getattr(self, "provided_"+total_name)
        provided_total_size      = getattr(self, "provided_total_size")

        size_per_unit   = getattr(self, size_name)
        number_of_units = getattr(self, total_name)
        total_size = self.total_size

        calc_size_per_unit   = int(total_size / number_of_units)
        calc_number_of_units = int(total_size / size_per_unit)
        calc_total_size      = int(size_per_unit * number_of_units)

        def check(a, b):
            if a is not None and a != b:
                return '!='
            return '=='

        def si(a, f=str):
            if a is None:
                return ''
            else:
                return f(int(a))

        return """

| {mod_name:14s}                 |     Provided == Calculated   |     Hex    |
|-----------------|--------------|------------------------------|------------|
|   size_per_unit | {size_name_:>12s} | {p_size_:>12s} {size__check} {c_size_:<12s} | {h_size_:>10s} | {p_tsize:>10s} / {p_units:10s} ({ts_name___:>10s} / {total_name:10s})
| number_of_units | {total_name:>12s} | {p_units:>12s} {units_check} {c_units:<12s} | {h_units:>10s} | {p_tsize:>10s} / {p_size_:10s} ({ts_name___:>10s} / {size_name_:10s})
|      total_size | {ts_name___:>12s} | {p_tsize:>12s} {tsize_check} {c_tsize:<12s} | {h_tsize:>10s} | {p_size_:>10s} * {p_units:10s} ({size_name_:>10s} * {ts_name___:10s})
""".format(
    mod_name = mod_name,
    name = name,
    size_name_ = size_name,
    total_name = total_name,
    ts_name___ = ts_name,
    size__check = check(provided_size_per_unit,   calc_size_per_unit  ),
    units_check = check(provided_number_of_units, calc_number_of_units),
    tsize_check = check(provided_total_size,      calc_total_size     ),
    p_size_ = si(provided_size_per_unit),
    p_units = si(provided_number_of_units),
    p_tsize = si(provided_total_size),
    c_size_ = si(calc_size_per_unit),
    c_units = si(calc_number_of_units),
    c_tsize = si(calc_total_size),
    h_size_ = si(calc_size_per_unit, hex),
    h_units = si(calc_number_of_units, hex),
    h_tsize = si(calc_total_size, hex),
)

    def _fix_and_check_sized(self, mod_name, name):
        """Makes sure that XXX_size, XXX_total and total_size match.

        IE If XXX == pages then, page_size * total_pages == total_size
        """
        size_name  = "{}_size".format(name)
        total_name = "total_{}s".format(name)

        provided_size_per_unit   = getattr(self, size_name,    None)
        provided_number_of_units = getattr(self, total_name,   None)
        provided_total_size      = getattr(self, "total_size", None)
        setattr(self, "provided_"+size_name,   provided_size_per_unit)
        setattr(self, "provided_"+total_name,  provided_number_of_units)

        provided = 0
        if provided_size_per_unit is not None:
            provided += 1
        if provided_number_of_units is not None:
            provided += 1
        if provided_total_size is not None:
            provided += 1

        assert provided >= 2, """\
{mod_name}: Must provide two of {name}_size={} (size_per_unit), total_{name}s={} (number_of_units), total_size={}
""".format(provided_size_per_unit, provided_number_of_units, provided_total_size, mod_name=mod_name, name=name)

        if provided_size_per_unit is None:
            size_per_unit = int(provided_total_size / provided_number_of_units)
        else:
            size_per_unit = int(provided_size_per_unit)

        if provided_number_of_units is None:
            number_of_units = int(provided_total_size / provided_size_per_unit)
        else:
            number_of_units = int(provided_number_of_units)

        if provided_total_size is None:
            total_size = int(provided_size_per_unit * provided_number_of_units)
        else:
            total_size = int(provided_total_size)

        setattr(self, size_name,  size_per_unit)
        setattr(self, total_name, number_of_units)

        assert   size_per_unit ==    total_size / number_of_units, self._table(mod_name, name)
        assert number_of_units ==    total_size / size_per_unit,   self._table(mod_name, name)
        assert      total_size == size_per_unit * number_of_units, self._table(mod_name, name)
        if provided_total_size is not None:
            assert provided_total_size == total_size, """\
{mod_name}: Tried to set size to {} but size was already set to {}
""".format(provided_total_size, self.total_size, mod_name=mod_name)

    def __init__(self, name, *args, **kw):
        if name == "SpiNorFlashModule":
           return
        setattr(self, "provided_total_size", getattr(self, "total_size", None))
        self._fix_and_check_sized(name, "page")
        #self._fix_and_check_sized(name, "sector")
        self.total_size = self.page_size * self.total_pages
        self.table = lambda x: self._table(name, x)



@dataclass
class SpiNorFlashModule(metaclass=MetaSizes):
    """Structure for defining the SPI Nor flash layer."""

    name: str
    device_id: int

    """spi-nor part JDEC MFR id"""
    manufacturer_id: SpiNorFlashManufacturerIDs

    # op codes for talking to the flash
    """the opcode for erasing a sector"""
    erase_opcode: SpiNorFlashOpCode

    """the read opcode"""
    read_opcode: SpiNorFlashOpCode

    """the program opcode"""
    program_opcode: SpiNorFlashOpCode

    """the dummy needed by the read operation"""
    read_dummy: int

    # Protocols for talking to the flash.
    """the SPI protocol for read operations"""
    read_proto: SpiProtocol

    """the SPI protocol for write operations"""
    write_proto: SpiProtocol

    """the SPI protocol for read_reg/write_reg/erase operations"""
    reg_proto: SpiProtocol

    # fmax

    # Sizes
    """number of address bytes"""
    addr_width: int

    """the page size (bytes) of the SPI Nor"""
    page_size:   int = None

    """the sector size (bytes) of the SPI Nor"""
    sector_size: int = None

    """Total size in bytes."""
    total_size:  int = None

    total_pages: int = None
    total_sectors: int = None

    #erase_size: int
    #write_size: int




# ST SPI Nor Flash
##########################################################################


class M25P05(SpiNorFlashModule):
    name = "m25p05"
    device_id = 0x00102020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 128
    sector_size = 0x8000
    total_pages = 0x10000


class M25P10(SpiNorFlashModule):
    name = "m25p10"
    device_id = 0x00112020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 128
    sector_size = 0x8000
    total_pages = 0x20000



class M25P20(SpiNorFlashModule):
    name = "m25p20"
    device_id = 0x00122020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x40000


class M25P40(SpiNorFlashModule):
    name = "m25p40"
    device_id = 0x00132020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x80000


class M25P80(SpiNorFlashModule):
    name = "m25p80"
    device_id = 0x00142020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x100000


class M25P16(SpiNorFlashModule):
    # Used by:
    # * MimasV2
    # * TinyFPGA BX
    name = "m25p16"
    device_id = 0x00152020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    dummy_bits = 8

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x200000


class M25P32(SpiNorFlashModule):
    name = "m25p32"
    device_id = 0x00162020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x400000


class M25P64(SpiNorFlashModule):
    name = "m25p64"
    device_id = 0x00172020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x800000


class M25P128(SpiNorFlashModule):
    name = "m25p128"
    device_id = 0x00182020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x40000
    total_pages = 0x1000000


class M45PE10(SpiNorFlashModule):
    name = "m45pe10"
    device_id = 0x00114020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.SE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x20000


class M45PE20(SpiNorFlashModule):
    name = "m45pe20"
    device_id = 0x00124020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.SE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x40000


class M45PE40(SpiNorFlashModule):
    name = "m45pe40"
    device_id = 0x00134020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.SE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x80000


class M45PE80(SpiNorFlashModule):
    name = "m45pe80"
    device_id = 0x00144020
    manufacturer_id   = SpiNorFlashManufacturerIDs.ST

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.SE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x100000


# Spansion SPI Nor Flash
##########################################################################

class S25FL256S(SpiNorFlashModule):
    # Used on
    #  * Numato Mimas A7
    #  * Digilent Nexys Video   - Spansion S25FL256S    - 0x00190201

    name = "S25FL256S"
    device_id = 0x00190201
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    # OpCodes

    read_dummy_bits = 10

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_size  = bit2bytes(256 * Mbit)


class S25FL004(SpiNorFlashModule):
    name = "s25fl004"
    device_id = 0x00120201
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x80000


class S25FL008(SpiNorFlashModule):
    name = "s25fl008"
    device_id = 0x00130201
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x100000


class S25FL016(SpiNorFlashModule):
    name = "s25fl016"
    device_id = 0x00140201
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x200000


class S25FL032(SpiNorFlashModule):
    name = "s25fl032"
    device_id = 0x00150201
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x400000


class S25FL064(SpiNorFlashModule):
    name = "s25fl064"
    device_id = 0x00160201
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x800000


# Atmel SPI Nor Flash
##########################################################################


class A25F512(SpiNorFlashModule):
    name = "25f512"
    device_id = 0x0065001f
    manufacturer_id   = SpiNorFlashManufacturerIDs.ATMEL

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.BE_32K
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 128
    sector_size = 0x8000
    total_pages = 0x10000


class A25F1024(SpiNorFlashModule):
    name = "25f1024"
    device_id = 0x0060001f
    manufacturer_id   = SpiNorFlashManufacturerIDs.ATMEL

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.BE_32K
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE_ATMEL

    # Sizes
    page_size   = 256
    sector_size = 0x8000
    total_pages = 0x20000


class A25F2048(SpiNorFlashModule):
    name = "25f2048"
    device_id = 0x0063001f
    manufacturer_id   = SpiNorFlashManufacturerIDs.ATMEL

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.BE_32K
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE_ATMEL

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x40000


class A25F4096(SpiNorFlashModule):
    name = "25f4096"
    device_id = 0x0064001f
    manufacturer_id   = SpiNorFlashManufacturerIDs.ATMEL

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.BE_32K
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE_ATMEL

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x80000


class A25FS040(SpiNorFlashModule):
    name = "25fs040"
    device_id = 0x0004661f
    manufacturer_id   = SpiNorFlashManufacturerIDs.ATMEL

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.BE_4K_PMC
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x80000


class AT25QF641(SpiNorFlashModule):
    """Adestotech."""

    """
    Adesto is Atmel?
      Manufacturer ID   Adesto      1Fh     90h, 92h, 94h, 9Fh
            Device ID   AT25QF641   16h     90h, 92h, 94h, ABh
       Memory Type ID   SPI / QPI   32h     9Fh
     Capacity Type ID   64M         17h     9Fh
    """

    name = "25fs040"
    device_id = 0x0004661f
    manufacturer_id   = SpiNorFlashManufacturerIDs.ATMEL

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.BE_4K_PMC
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    #total_pages = 65536

    total_size = bit2bytes(64 * Mbit)

    fmax = 104 * MHz

    # 7.10 Fast Read in QPI Mode
    #  4, or 6 or 8 - default is 4
    # 7.11 Fast Read Dual Output (3Bh)
    # 7.12 Fast Read Quad Output (6Bh)
    #  eight “dummy” clocks
    # 7.30 Word Read Quad I/O (E7h)
    #  only two dummy clocks
    # 7.35 Read Serial Flash Discovery Parameter (5Ah)
    #  8 dummy clock cycles

    # P5,P4 Dummy   fmax
    # 00      4     80MHz
    # 01      4     80MHz
    # 10      6     104MHz


# Macronix SPI Nor Flash
##########################################################################


class M25L512(SpiNorFlashModule):
    name = "25l512"
    device_id = 0x001020c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 16
    sector_size = 0x10000
    total_pages = 0x10000


class M25L1005(SpiNorFlashModule):
    name = "25l1005"
    device_id = 0x001120c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.SE

    # Sizes
    page_size   = 16
    sector_size = 0x10000
    total_pages = 0x20000


class M25L2005(SpiNorFlashModule):
    name = "25l2005"
    device_id = 0x001220c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 16
    sector_size = 0x10000
    total_pages = 0x40000


class M25L4005(SpiNorFlashModule):
    name = "25l4005"
    device_id = 0x001320c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 16
    sector_size = 0x10000
    total_pages = 0x80000


class M25L8005(SpiNorFlashModule):
    name = "25l8005"
    device_id = 0x001420c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 16
    sector_size = 0x10000
    total_pages = 0x100000


class M25L1605(SpiNorFlashModule):
    name = "25l1605"
    device_id = 0x001520c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x200000


class M25L3205(SpiNorFlashModule):
    name = "25l3205"
    device_id = 0x001620c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x400000


class M25L6405(SpiNorFlashModule):
    # Used by
    # * minispartan6
    name = "25l6405"
    device_id = 0x001720c2
    manufacturer_id   = SpiNorFlashManufacturerIDs.MACRONIX

    dummy_bits = 4

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x800000


# GD25VE32C - 32M-bit Serial Flash


# Winbond SPI Nor Flash
##########################################################################


class W25Q32DW(SpiNorFlashModule):
    name = "w25q32dw"
    device_id = 0x001660ef
    manufacturer_id   = SpiNorFlashManufacturerIDs.WINBOND

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE
    opcodes_dummy     = W25OpCodeDummy

    # Sizes
    page_size   = 256
    sector_size = 4 * kbytes
    total_pages = 16384
    total_size  = bit2bytes(32 * Mbit)



class W25Q64CV(SpiNorFlashModule):
    name = "w25q64cv"
    device_id = 0x001740ef
    manufacturer_id   = SpiNorFlashManufacturerIDs.WINBOND

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE
    opcodes_dummy     = W25OpCodeDummy

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x8000
    total_size  = bit2bytes(64 * Mbit)


# For fast read instructions
# - Fast Read
# - Dual Command fast read
# the number of dummy clock cycles is configurable by using VCR bits [7:4] or
# NVCR bits [15:12].

class N25Q32(SpiNorFlashModule):
    # Used by
    # * upduino v1
    # * Digilent CMod-A7        - N25Q032A13EF440F              - 0x0016ba20
    # * ice40_hx8k_b_env

    name = "n25q32"
    device_id = 0x0
    manufacturer_id   = SpiNorFlashManufacturerIDs.SPANSION

    read_dummy_bits = 8

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 16384
    total_size  = bit2bytes(32 * Mbit) # 128 Mbit (16Mb x 8)

    fmax = 108 * MHz


class N25Q128(SpiNorFlashModule):
    """Numonyx 128-mbit 3V, multiple IO, serial flash memory."""

    # Used by
    # * Digilent Atlys          - N25Q12-F8 or N25Q12-SF
    # * Picoevb                 - ????
    # * Neso (n25q128a13)       - N25Q128A13ESF40               - 0x0018ba20
    # * Opsis                   - W25Q128FVEIG
    # * Digilent Nexys Video
    # * Arty (n25q128a13)       - N25Q128A13ESF40               - 0x0018ba20
    # * Galatea                 - W25Q128FVEIG (component U3)   - 0x0018ba 20
    # * Digilent Basys3         - N25Q128A13ESF40
    # * Pipistrello             - N25Q128                       - 0x0018ba20
    # * icebreaker              - ????                          - Dummy bits 8?

    name = "n25q128"
    device_id = 0x00ba18
    manufacturer_id   = SpiNorFlashManufacturerIDs.MICRON

    read_dummy_bits = 10
    fmax = 108 * MHz

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_pages = 0x10000
    total_size  = bit2bytes(128 * Mbit)


class N25Q256(SpiNorFlashModule):
    """Numonyx (Micron) 256-mbit 3V, multiple IO, serial flash memory."""

    # Used by,
    # * NeTV2? (Maybe?)

    name = "n25q256"
    device_id = 0x00ba19
    manufacturer_id   = SpiNorFlashManufacturerIDs.MICRON # 20h 2c?

    dummy_bits = 10
    fmax = 108 * MHz

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_size  = bit2bytes(256 * Mbit)


class N25Q00(SpiNorFlashModule):
    """Numonyx 1-gbit 3V, multiple IO, serial flash memory."""

    name = "n25q00"
    device_id = 0x00ba18
    #device_id = 0x001740ef
    manufacturer_id   = SpiNorFlashManufacturerIDs.MICRON

    dummy_bits = 10
    fmax = 108 * MHz

    # OpCodes
    erase_opcode      = SpiNorFlashOpCodes.SE
    chip_erase_opcode = SpiNorFlashOpCodes.CHIP_ERASE

    # Sizes
    page_size   = 256
    sector_size = 0x10000
    total_size  = bit2bytes(1 * Gbit)


def print_modules():
    for name, obj in globals().items():
        if type(obj) != MetaSizes:
            continue
        if not issubclass(obj, SpiNorFlashModule):
            continue
        if name == 'SpiNorFlashModule':
            continue
        print(obj.table("page"))


if __name__ == "__main__":
    print_modules()
