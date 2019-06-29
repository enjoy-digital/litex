#!/usr/bin/env python3

import json
import os
import re
import urllib.request
import pprint

regex_id = re.compile(r'#define\s+([^\s]+)\s+([^\s]+)\s*(/\* (.*) \*/)?$')
regex_key_replace = re.compile(r'(\s*)\.([a-z_]+)\s+=[\s\n]+([^,{\[]*)', re.MULTILINE)
regex_enum = re.compile(":\s*([A-Z][A-Z0-9_]*),")
regex_func = re.compile(":\s*([a-z][a-z0-9_]*),")
regex_comment = re.compile(r'/\*(.*?)\*/([^\n]*?)$', re.DOTALL|re.MULTILINE)
regex_model = re.compile("'model_id': ([^,]*),")
regex_name = re.compile("'name':\\s*\"([^\"]*)\",\\s*?(#[^#]*?)?$", re.MULTILINE)

regex_list = re.compile('{([^:{},]+)([^:{}]*?)}', re.DOTALL)
regex_list_begin = re.compile('{(\\s*){')
regex_list_end = re.compile('}([,\\s]*)}')


import enum
class SpiNorFeatures(enum.Flag):
    FEATURE_ERASED_ZERO     = enum.auto()
    """Erasing flash ends up with 0x00 rather than 0xff."""

    FEATURE_OTP             = enum.auto()
    """Has a one time programming area."""

    FEATURE_WRSR_EWSR       = enum.auto()
    """Before sending the WRSR instruction the Enable-Write-Status-Register must be written too."""

    FEATURE_WRSR_WREN       = enum.auto()
    """Before sending WRSR instruction, the Write Enable (WREN) instruction must be decoded and executed to set the Write Enable Latch (WEL) bit in advance."""

    FEATURE_WRSR_EITHER     = FEATURE_WRSR_EWSR | FEATURE_WRSR_WREN

    FEATURE_QPI             = enum.auto()
    """Supports Quad-SPI-mode - ???"""

    FEATURE_4BA_ENTER       = enum.auto()
    """Can enter/exit 4BA mode with instructions 0xb7/0xe9 w/o WREN."""

    FEATURE_4BA_ENTER_WREN  = enum.auto()
    """Can enter/exit 4BA mode with instructions 0xb7/0xe9 after WREN."""

    FEATURE_4BA_ENTER_EAR7  = enum.auto()
    """Can enter/exit 4BA mode by setting bit7 of the ext addr reg."""

    FEATURE_4BA_EXT_ADDR    = enum.auto()
    """Regular 3-byte operations can be used by writing the most significant address byte into an extended address register."""

    FEATURE_4BA_READ        = enum.auto()
    """Native 4BA read instruction (0x13) is supported."""

    FEATURE_4BA_FAST_READ   = enum.auto()
    """Native 4BA fast read instruction (0x0c) is supported."""

    FEATURE_4BA_WRITE       = enum.auto()
    """Native 4BA byte program (0x12) is supported."""

    # 4BA Shorthands
    FEATURE_4BA_NATIVE	= (FEATURE_4BA_READ | FEATURE_4BA_FAST_READ | FEATURE_4BA_WRITE)
    FEATURE_4BA		= (FEATURE_4BA_ENTER | FEATURE_4BA_EXT_ADDR | FEATURE_4BA_NATIVE)
    FEATURE_4BA_WREN	= (FEATURE_4BA_ENTER_WREN | FEATURE_4BA_EXT_ADDR | FEATURE_4BA_NATIVE)
    FEATURE_4BA_EAR7	= (FEATURE_4BA_ENTER_EAR7 | FEATURE_4BA_EXT_ADDR | FEATURE_4BA_NATIVE)



# spi_block_erase_d8
function_mapping = {
    'Features': SpiNorFeatures,
    'BUS_SPI': 'BUS_SPI',
    'NULL': None,
    # Testing values
    'OK':   'Tested and working',
    'NT':   'Not tested',
    'NA':   'Not applicable (e.g. write support on ROM chips)',
    'BAD':  'Known not to work',
    'DEP':  'Support depends on configuration (e.g. Intel flash descriptor)',

    # JEDEC_BYTE_PROGRAM_4BA : JEDEC_BYTE_PROGRAM
    'config':                                             'SpiNorFlashOpCodes.UNKNOWN',

    # Erase - Page
    # Erase - Sector
    # Erase - Chip

    'edi_chip_block_erase':                               'SpiNorFlashOpCodes.BE_4K',                  # 0x20 - ENE_XBI_EFCMD_ERASE

    'spi_block_erase_d8':                                 'SpiNorFlashOpCodes.SE',                     # 0xd8 - Sector Erase - size is usually, 64k for Macronix, 32k for SST, 4-32k non-uniform for EON
    # Erase - Block
    'spi_block_erase_db':                                 'SpiNorFlashOpCodes.BE_256',                 # 0xdb - usually 256B blocks
    'spi_block_erase_20':                                 'SpiNorFlashOpCodes.BE_4K',                  # 0x20 - Sector size is usually 4k, though Macronix eliteflash has 64k
    'spi_block_erase_d7':                                 'SpiNorFlashOpCodes.BE_4K_PMC',              # 0xd7 - 4k for PMC
    'spi_block_erase_50':                                 'SpiNorFlashOpCodes.BE_ALT1',                # 0x50 - ???
    'spi_erase_at45db_block':                             'SpiNorFlashOpCodes.BE_ALT1',                # 0x50 - ???
    'spi_block_erase_52':                                 'SpiNorFlashOpCodes.BE_32K',                 # 0x52 - ???
    'spi_block_erase_81':                                 'SpiNorFlashOpCodes.BE_ALT2',                # 0x81 - ???

    'spi_block_erase_21':                                 'SpiNorFlashOpCodes.BE_4K_4B',               # 0x21 - Erase 4 KB of flash with 4-bytes address from ANY mode (3-bytes or 4-bytes)
    'spi_block_erase_5c':                                 'SpiNorFlashOpCodes.BE_32K_4B',              # 0x5c - Erase 32 KB of flash with 4-bytes address from ANY mode (3-bytes or 4-bytes)
    'spi_block_erase_dc':                                 'SpiNorFlashOpCodes.SE_4B',                  # 0xdc - Erase 64 KB of flash with 4-bytes address from ANY mode (3-bytes or 4-bytes)

    'spi_erase_at45cs_sector':                            'SpiNorFlashOpCodes.UNKNOWN',                # 0x7c - Used for all but sector 0a.
    'spi_erase_at45db_sector':                            'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_erase_at45db_page':                              'SpiNorFlashOpCodes.UNKNOWN',                # 0x81

    # Whole Chip Erase
    'spi_block_erase_60':                                 'SpiNorFlashOpCodes.CHIP_ERASE_ALT',         # 0x60
    'spi_block_erase_62':                                 'SpiNorFlashOpCodes.CHIP_ERASE_ATMEL',       # 0x62
    'spi_block_erase_c7':                                 'SpiNorFlashOpCodes.CHIP_ERASE',             # 0xc7
    'spi_erase_at45db_chip':                              'SpiNorFlashOpCodes.CHIP_ERASE',             # 0x7c - FIXME: Is this really backwards?

    # Read
    'spi_chip_read':                                      'SpiNorFlashOpCodes.READ',                   # 0x03
    'spi_read_at45db':                                    'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_read_at45db_e8':                                 'SpiNorFlashOpCodes.UNKNOWN',                # Legacy continuous read, used where spi_read_at45db() is not available. The first 4 (dummy) bytes read need to be discarded.
    'edi_chip_read':                                      'SpiNorFlashOpCodes.UNKNOWN',                # 0x30

    # Write
    'spi_aai_write':                                      'SpiNorFlashOpCodes.JEDEC_AAI_WORD_PROGRAM', # 0xad
    'spi_chip_write_1':                                   'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_chip_write_256':                                 'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_write_at45db':                                   'SpiNorFlashOpCodes.UNKNOWN',                #
    'write_gran_1056bytes':                               'SpiNorFlashOpCodes.UNKNOWN',                #
    'write_gran_128bytes':                                'SpiNorFlashOpCodes.UNKNOWN',                #
    'write_gran_528bytes':                                'SpiNorFlashOpCodes.UNKNOWN',                #
    'edi_chip_write':                                     'SpiNorFlashOpCodes.UNKNOWN',                # 0x40
                                                                                                       #
    # Probe                                                                                            #
    'probe_spi_rdid':                                     'SpiNorFlashOpCodes.UNKNOWN',                #
    'probe_spi_rdid4':                                    'SpiNorFlashOpCodes.UNKNOWN',                #
    'probe_spi_rems':                                     'SpiNorFlashOpCodes.UNKNOWN',                #
    'probe_spi_res1':                                     'SpiNorFlashOpCodes.UNKNOWN',                #
    'probe_spi_res2':                                     'SpiNorFlashOpCodes.UNKNOWN',                #
    'probe_spi_sfdp':                                     'SpiNorFlashOpCodes.UNKNOWN',                #
    'probe_spi_at25f':                                    'SpiNorFlashOpCodes.RDID_ATMEL',             #
    'probe_spi_at45db':                                   'SpiNorFlashOpCodes.UNKNOWN',                #
    'edi_probe_kb9012':                                   'SpiNorFlashOpCodes.UNKNOWN',                #

    # Disable Block Protect
    'spi_disable_blockprotect':                           'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at25f':                     'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at25f512a':                 'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at25f512b':                 'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at25fs010':                 'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at25fs040':                 'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at2x_global_unprotect':     'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at2x_global_unprotect_sec': 'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_at45db':                    'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_bp1_srwd':                  'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_bp2_ep_srwd':               'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_bp2_srwd':                  'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_bp3_srwd':                  'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_bp4_srwd':                  'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_n25q':                      'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_disable_blockprotect_sst26_global_unprotect':    'SpiNorFlashOpCodes.UNKNOWN',                #

    # Status Registers
    'spi_prettyprint_status_register_plain':              'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_amic_a25l032':       'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25df':             'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25df_sec':         'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25f':              'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25f4096':          'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25f512a':          'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25f512b':          'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25fs010':          'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at25fs040':          'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at26df081a':         'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_at45db':             'SpiNorFlashOpCodes.UNKNOWN',                # 0xD7
    'spi_prettyprint_status_register_bp1_srwd':           'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_bp2_bpl':            'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_bp2_ep_srwd':        'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_bp2_srwd':           'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_bp2_tb_bpl':         'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_bp3_srwd':           'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_bp4_srwd':           'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_default_welwip':     'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_en25s_wp':           'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_n25q':               'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_sst25':              'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_sst25vf016':         'SpiNorFlashOpCodes.UNKNOWN',                #
    'spi_prettyprint_status_register_sst25vf040b':        'SpiNorFlashOpCodes.UNKNOWN',                #
}

users = {
    "M25P16": ["MimasV2", "TinyFPGA BX"], # ST_M25P16
    "M25L6405": ["minispartan6"], # MACRONIX_MX25L6405
    "N25Q32": [
        "upduino_v1",
        "Digilent Cmod-A7", # N25Q032A13EF440F              - 0x0016ba20
        "ice40_hx8k_b_env",
    ],
    # EON_EN25Q128
    # ST_N25Q128__1E
    # ST_N25Q128__3E
    "N25Q128": [
        "Digilent Atlys",          # N25Q12-F8 or N25Q12-SF
        "Picoevb",                 # ????
        "Neso (n25q128a13)",       # N25Q128A13ESF40               - 0x0018ba20
        "Opsis",                   # W25Q128FVEIG
        "Digilent Nexys Video",
        "Arty (n25q128a13)",       # N25Q128A13ESF40               - 0x0018ba20
        "Galatea",                 # W25Q128FVEIG (component U3)   - 0x0018ba 20
        "Digilent Basys3",         # N25Q128A13ESF40
        "Pipistrello",             # N25Q128                       - 0x0018ba20
        "icebreaker",              # ????                          - Dummy bits 8?
    ],
    # ST_N25Q256__3E
    "N25Q256": [
        "NeTV2",                   # (Maybe?)
    ],
}


# Get the files
for fname in ['flashchips.h', 'flashchips.c']:
    uf = urllib.request.urlopen("https://review.coreboot.org/cgit/flashrom.git/plain/"+fname)
    wf = open('.'+fname, 'wb')
    wf.write(uf.read())
    wf.close()
    uf.close()


def parse_header():
    flash_ids = [('???', '???', None, [])]

    f = open('.flashchips.h', 'r')
    for l in f.readlines():
        l = l.strip()
        if not l.startswith('#define '):
            continue
        m = regex_id.match(l)
        if not m:
            print("Bad line?:", l)
            continue
        name_id, hex_id, _, comment = m.groups()
        if 'xx' in hex_id:
            hex_id = hex_id.replace('xx', '')

        hex_id = int(hex_id, 16)
        manufacturer, part = name_id.split('_', 1)
        if part in ('ID', 'ID_PREFIX'):
            flash_ids.append((manufacturer, hex_id, comment, []))
        else:
            flash_ids[-1][-1].append((part, hex_id, comment))

    return flash_ids


def parse_c():
    f = open('.flashchips.c', 'r')
    lines = iter(f.readlines())
    for l in lines:
        l = l.strip()
        if l == 'const struct flashchip flashchips[] = {':
            break

    all_enums = set()
    all_funcs = set()

    parts = {}
    current = []
    comment = False
    for l in lines:
        ls = l.strip()
        if not ls:
            continue

        if ls.startswith('/*'):
            comment = True

        if comment:
            if '*/' in ls:
                comment = False
            continue

        current.append(l)

        if not ls.endswith(','):
            continue

        s = ''.join(current)

        opening = s.count('{')
        closing = s.count('}')
        if opening > closing:
            continue

        current = []
        if 'BUS_SPI' not in s:
            continue

        p = s
        p = regex_comment.sub(r"\2#\1", p)
        assert p.startswith('\t{'), repr(p)
        assert p.endswith('\t},\n'), repr(p)
        p = p[2:-4]

        p = regex_key_replace.sub(r"\1'\2': \3", p)
        while regex_list.search(p):
            p = regex_list.sub(r"[\1\2]", p)
        while regex_list_begin.search(p):
            p = regex_list_begin.sub(r"[\1{", p)
        while regex_list_end.search(p):
            p = regex_list_end.sub(r"}\1]", p)
        enums = regex_enum.findall(p)
        for e in enums:
            all_enums.add(e)
        funcs = regex_func.findall(p)
        for f in funcs:
            all_funcs.add(f)

        ps = '\t{\n'+p+'\t}\n'

        model_id = regex_model.search(ps)
        if not model_id:
            print()
            print('Error, no model_id found in:')
            print('-'*75)
            print(ps)
            print('-'*75)
        else:
            parts[model_id.group(1)] = ps

    for f in SpiNorFeatures:
        all_enums.add(f.name)
    all_enums = list(all_enums)
    all_enums.sort()

    all_funcs = list(all_funcs)
    all_funcs.sort()

    return all_enums, all_funcs, parts


def eval_data(data, all_enums):
    for e in all_enums:
        if e.startswith('FEATURE_'):
            o = "Features."+e
        else:
            o = "'{}'".format(e)
        if e not in data:
            continue
        data = re.sub('(\\s+){}([\\s,]+)'.format(e), r"\1{}\2".format(o), data)
    try:
        return eval(data, globals(), function_mapping)
    except Exception:
        print('-'*75)
        print(data)
        print('-'*75)
        raise


def main():
    flash_ids = parse_header()
    all_enums, all_funcs, all_parts = parse_c()

    print("\nEnums\n", "="*75)
    pprint.pprint(all_enums)
    print("\nFunctions\n", "="*75)
    for f in all_funcs:
        print(f)
    print("\nParts\n", "="*75)
    for p in all_parts.values():
        print(p)
        print("-"*75)
    print("-"*75)

    spi_ids = []
    spi_parts = {}

    for man, man_id, desc, parts in flash_ids[3:]:
        man_alt = None
        man_alt_id = None
        cmt = ''
        if parts[0][0] == 'ID_NOPREFIX':
            s, man_alt_id, cmt = parts.pop(0)
            assert s == 'ID_NOPREFIX', s

        if isinstance(man_id, int):
            mid = man_id

        if isinstance(man_alt_id, int):
            mid = man_alt_id

        if man+'_ID' not in all_enums:
            continue

        assert man not in spi_ids

        spi_parts[man] = {}
        for part_name, part_id, part_cmt in parts:
            full_name = man+'_'+part_name
            if full_name not in all_parts:
                print('Unknown part?', full_name)
                continue
            part_data = all_parts[full_name]
            if "'bustype': BUS_SPI" not in part_data:
                print("Skipping non SPI part", full_name)
                continue
            spi_parts[man][part_name] = (part_id, part_cmt, part_data)

        spi_ids.append((man, mid, cmt))

    pprint.pprint(spi_parts)

    print()
    print('''\
class SpiNorFlashManufacturerIDs(enum.Enum):
    """Manufacturer IDs for SPI NOR flash chips.

    The first byte returned from the flash after sending opcode SPINor_OP_RDID.
    Sometimes these are the same as CFI IDs, but sometimes they aren't.
    """
''')
    for man, mid, cmt in spi_ids:
        print("    %-20s = 0x%04x" % (man, mid), end="")
        if cmt:
            print(' # '+ cmt)
        else:
            print()
    print()

    for man, mid, mcmt in spi_ids:
        print()
        print('# 0x{:04x} - {} parts{}'.format(mid, man, mcmt or ''))
        print('#'*75)
        print()
        for part_name, (part_id, part_cmt, part_data) in spi_parts[man].items():

            if 'AT45CS1282' in part_data:
                continue

            fn = regex_name.search(part_data)
            assert fn, repr(part_data)
            part_fullname, part_fullname_comment = fn.groups()
            if part_fullname_comment:
                assert part_fullname_comment.startswith('#'), part_fullname_comment
                part_fullname_comment = part_fullname_comment[1:].strip()

            if part_cmt:
                part_cmt = part_cmt.replace('; ', '\n')

            part_eval_data = eval_data(part_data, all_enums)
            if 'voltage' not in part_eval_data:
                part_eval_data['voltage'] = [-1, -1]

            """
# Constants in our use case...
.bustype         = BUS_SPI     = Supported flash bus types (Parallel, LPC...)
.probe_timing    = TIMING_ZERO = Probe function delay

# Details
.vendor          = Vendor name
.name            = Chip name
.manufacture_id  = Manufacturer chip ID
.model_id        = Model chip ID

# Random?
.tested          = Test status

# Sizes
.total_size      = Total size in (binary) kbytes
.page_size       = Page or eraseblock(?) size in bytes

.voltage         = Voltage range in millivolt

# Functions
.probe           = Probe function
.block_erasers[] = Array of erase layouts and erase functions
{
     .eraseblocks[]     = Array of { blocksize, blockcount }
     .block_erase       = Block erase function
}
.printlock       = Chip lock status function
.unlock          = Chip unlock function
.write           = Chip write function
.read            = Chip read function

            """

            print('''
class {pn}(SpiNorFlashModule):
    """{pfn} by {ven}

{pcmt}
{pfn_cmt}

{pr}
    """
    manufacturer_id = SpiNorFlashManufacturerIDs.{mid}
    device_id = 0x{pid:04x}
    name = "{pfn}"

    total_size = {ts:10d}   # bytes
    page_size  = {ps:10d}   # bytes

    voltage_min = {vmin:1.02f} # volts
    voltage_max = {vmax:1.02f} # volts

    features = '' #

    opcode_read   = ''
    opcode_probe  = ''
    opcode_unlock = ''
    opcode_write  = ''
    opcode_erase  = ''

    # status_register_structure
'''.format(
        pn=part_name,
        pfn=part_fullname,
        pfn_cmt=part_fullname_comment or '',
        pcmt=part_cmt or '',
        mid=man, pid=part_id,
        pd=part_data,
        pr=pprint.pformat(part_eval_data),

        ven=part_eval_data['vendor'],
        ts=part_eval_data['total_size']*1024,
        ps=part_eval_data['page_size'],
        vmin = part_eval_data['voltage'][0]/1000.0,
        vmax = part_eval_data['voltage'][1]/1000.0,
    ))
            print('')
            print('')


if __name__ == "__main__":
    main()
