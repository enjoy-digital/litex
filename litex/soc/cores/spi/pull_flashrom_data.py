#!/usr/bin/env python3

import json
import os
import re
import urllib.request
import pprint

regex_id = re.compile(r'#define\s+([^\s]+)\s+([^\s]+)\s*(/\* (.*) \*/)?$')
regex_key_replace = re.compile(r'^(\s*)\.([^\s]+)\s+=[\s\n]+([^,\[]*)', re.MULTILINE)
regex_enum = re.compile(":\s*([A-Z][A-Z0-9_]*),")
regex_func = re.compile(":\s*([a-z][a-z0-9_]*),")
regex_comment = re.compile(r'/\*(.*?)\*/', re.DOTALL)

# spi_block_erase_d8
function_mapping = {
    # JEDEC_BYTE_PROGRAM_4BA : JEDEC_BYTE_PROGRAM
    'config':                                             'SpiNorFlashOpCodes.',

    # Erase - Page
    # Erase - Block
    # Erase - Sector
    # Erase - Chip

    'edi_chip_block_erase':                               'SpiNorFlashOpCodes.BE_4K',               # 0x20 - ENE_XBI_EFCMD_ERASE

    'spi_block_erase_52':                                 'SpiNorFlashOpCodes.BE_32K',              # 0x52
    'spi_block_erase_d8':                                 'SpiNorFlashOpCodes.SE',                  # 0xd8 - Sector Erase - size is usually, 64k for Macronix, 32k for SST, 4-32k non-uniform for EON
    'spi_block_erase_d7':                                 'SpiNorFlashOpCodes.BE_4K_PMC',           # 0xd7 - 4k for PMC
    'spi_block_erase_db':                                 'SpiNorFlashOpCodes.',                    # 0xdb - usually 256B blocks
    'spi_block_erase_20':                                 'SpiNorFlashOpCodes.BE_4K',               # 0x20 - Sector size is usually 4k, though Macronix eliteflash has 64k
    'spi_block_erase_50':                                 'SpiNorFlashOpCodes.CLFSR',               # 0x50 - Clear Flag Status Register?
    'spi_block_erase_81':                                 'SpiNorFlashOpCodes.',                    # 0x81

    'spi_block_erase_21':                                 'SpiNorFlashOpCodes.BE_4K_4B',            # 0x21 - Erase 4 KB of flash with 4-bytes address from ANY mode (3-bytes or 4-bytes)
    'spi_block_erase_5c':                                 'SpiNorFlashOpCodes.BE_32K_4B',           # 0x5c - Erase 32 KB of flash with 4-bytes address from ANY mode (3-bytes or 4-bytes)
    'spi_block_erase_dc':                                 'SpiNorFlashOpCodes.SE_4B',               # 0xdc - Erase 64 KB of flash with 4-bytes address from ANY mode (3-bytes or 4-bytes)

    'spi_erase_at45cs_sector':                            'SpiNorFlashOpCodes.',                    # 0x7c - Used for all but sector 0a.
    'spi_erase_at45db_block':                             'SpiNorFlashOpCodes.',                    # 0x50
    'spi_erase_at45db_page':                              'SpiNorFlashOpCodes.',                    # 0x81
    # Whole Chip Erase
    'spi_block_erase_60':                                 'SpiNorFlashOpCodes.CHIP_ERASE_ALT',      # 0x60
    'spi_block_erase_62':                                 'SpiNorFlashOpCodes.CHIP_ERASE_ATMEL',    # 0x62
    'spi_block_erase_c7':                                 'SpiNorFlashOpCodes.CHIP_ERASE',          # 0xc7
    'spi_erase_at45db_chip':                              'SpiNorFlashOpCodes.CHIP_ERASE',          # 0x7c -- FIXME: Is this really backwards?

    # Read
    'spi_chip_read':                                      'SpiNorFlashOpCodes.READ',                # 0x03
    'spi_read_at45db':                                    'SpiNorFlashOpCodes.',                    #
    'spi_read_at45db_e8':                                 'SpiNorFlashOpCodes.',                    # Legacy continuous read, used where spi_read_at45db() is not available. The first 4 (dummy) bytes read need to be discarded.
    'edi_chip_read':                                      'SpiNorFlashOpCodes.',                    # 0x30

    # Write
    'spi_aai_write':                                      'SpiNorFlashOpCodes.',                    #
    'spi_chip_write_1':                                   'SpiNorFlashOpCodes.',                    #
    'spi_chip_write_256':                                 'SpiNorFlashOpCodes.',                    #
    'spi_write_at45db':                                   'SpiNorFlashOpCodes.',                    #
    'write_gran_1056bytes':                               'SpiNorFlashOpCodes.',                    #
    'write_gran_128bytes':                                'SpiNorFlashOpCodes.',                    #
    'write_gran_528bytes':                                'SpiNorFlashOpCodes.',                    #
    'edi_chip_write':                                     'SpiNorFlashOpCodes.',                    # 0x40
                                                                                                    #
    # Probe                                                                                         #
    'probe_spi_at25f':                                    'SpiNorFlashOpCodes.',                    #
    'probe_spi_at45db':                                   'SpiNorFlashOpCodes.',                    #
    'probe_spi_rdid':                                     'SpiNorFlashOpCodes.',                    #
    'probe_spi_rdid4':                                    'SpiNorFlashOpCodes.',                    #
    'probe_spi_rems':                                     'SpiNorFlashOpCodes.',                    #
    'probe_spi_res1':                                     'SpiNorFlashOpCodes.',                    #
    'probe_spi_res2':                                     'SpiNorFlashOpCodes.',                    #
    'probe_spi_sfdp':                                     'SpiNorFlashOpCodes.',                    #
    'edi_probe_kb9012':                                   'SpiNorFlashOpCodes.',                    #

    # Disable Block Protect
    'spi_disable_blockprotect':                           'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at25f':                     'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at25f512a':                 'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at25f512b':                 'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at25fs010':                 'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at25fs040':                 'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at2x_global_unprotect':     'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at2x_global_unprotect_sec': 'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_at45db':                    'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_bp1_srwd':                  'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_bp2_ep_srwd':               'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_bp2_srwd':                  'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_bp3_srwd':                  'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_bp4_srwd':                  'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_n25q':                      'SpiNorFlashOpCodes.',                    #
    'spi_disable_blockprotect_sst26_global_unprotect':    'SpiNorFlashOpCodes.',                    #

    # Status Registers
    'spi_prettyprint_status_register_plain':              'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_amic_a25l032':       'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25df':             'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25df_sec':         'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25f':              'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25f4096':          'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25f512a':          'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25f512b':          'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25fs010':          'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at25fs040':          'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at26df081a':         'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_at45db':             'SpiNorFlashOpCodes.',                    # 0xD7
    'spi_prettyprint_status_register_bp1_srwd':           'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_bp2_bpl':            'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_bp2_ep_srwd':        'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_bp2_srwd':           'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_bp2_tb_bpl':         'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_bp3_srwd':           'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_bp4_srwd':           'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_default_welwip':     'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_en25s_wp':           'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_n25q':               'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_sst25':              'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_sst25vf016':         'SpiNorFlashOpCodes.',                    #
    'spi_prettyprint_status_register_sst25vf040b':        'SpiNorFlashOpCodes.',                    #
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

    parts = []
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
        p = regex_comment.sub(r"#\1", p)
        assert p.startswith('\t{'), repr(p)
        assert p.endswith('\t},\n'), repr(p)
        p = p[2:-4]

        p = p.replace('{', '[').replace('}', ']')
        p = regex_key_replace.sub(r"\1'\2': \3", p)
        enums = regex_enum.findall(p)
        for e in enums:
            all_enums.add(e)
        funcs = regex_func.findall(p)
        for f in funcs:
            all_funcs.add(f)

        ps = '\t{\n'+p+'\t}\n'
        print('-'*75)
        print(ps)
        print('-'*75)
        parts.append(ps)

    all_enums = list(all_enums)
    all_enums.sort()

    all_funcs = list(all_funcs)
    all_funcs.sort()

    return all_enums, all_funcs, parts


def main():
    flash_ids = parse_header()
    all_enums, all_funcs, parts = parse_c()

    print("\nEnums\n", "="*75)
    pprint.pprint(all_enums)
    print("\nFunctions\n", "="*75)
    for f in all_funcs:
        print(f)
    print("\nParts\n", "="*75)
    for p in parts:
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
        spi_parts[man] = {a:("0x%02x" % b, c) for a,b,c in parts}

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

    for man in spi_parts:
        print()
        print('# %s parts' % man)
        print('#'*75)
        print()
        for pname, (pid, pcmt) in spi_parts[man].items():
            print('''
class %s(SpiNorFlashModule):
    """%s by %s
    %s
    """
    manufacturer_id = %s
    device_id = %s
''' % (pname, pname, man, pcmt or '', pid))
            print('')
            print('')


if __name__ == "__main__":
    main()
