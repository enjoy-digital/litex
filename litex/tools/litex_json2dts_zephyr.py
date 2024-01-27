#!/usr/bin/env python3

# Copyright (c) 2019-2021 Antmicro <www.antmicro.com>
# Copyright (c) 2021 Henk Vergonet <henk.vergonet@gmail.com>
#
# Zephyr DTS & config overlay generator for LiteX SoC.
#
# This script parses LiteX 'csr.json' file and generates DTS and config
# files overlay for Zephyr.

# Changelog:
# - 2021-07-05 Henk Vergonet <henk.vergonet@gmail.com>
#    removed dependency on intermediate interpretation layers
#    switch to JSON csr
#    fix uart size parameter
# - 2021-07-15 Henk Vergonet <henk.vergonet@gmail.com>
#    added identifier_mem handler as dna0
#    added spiflash as spi0
#

import argparse
import json


def get_registers_of(name, csr):
    registers = csr['csr_registers']

    return [
        {
            **params,
            # describe size in bytes, not number of subregisters
            'size': params['size'] * 4,
            'name': r[len(name) + 1:],
        }
        for r, params in registers.items() if r.startswith(name)
    ]


# Indentation helpers
INDENT_STR = '    '


def indent(line, levels=1):
    return INDENT_STR * levels + line


def indent_all(text, levels=1):
    return '\n'.join(map(indent, text.splitlines()))


def indent_all_but_first(text, levels=1):
    lines = text.splitlines()
    indented = indent_all('\n'.join(lines[1:]), levels)
    if indented:
        return lines[0] + '\n' + indented
    else:
        return lines[0]


# DTS formatting
def dts_open(name, parm):
    return "&{} {{\n".format(parm.get('alias', name))


def dts_close():
    return "};\n"


def dts_intr(name, csr):
    return indent("interrupts = <{} 0>;\n".format(
        hex(csr['constants'][name + '_interrupt'])
    ))


def dts_reg(regs):
    dtsi = 'reg = <'

    formatted_registers = '\n'.join(
        '0x{:x} 0x{:x}'.format(reg['addr'], reg['size'])
        for reg in regs
    )

    dtsi += indent_all_but_first(formatted_registers)
    dtsi += '>;'

    return indent_all(dtsi) + '\n'


def dts_reg_names(regs):
    dtsi = 'reg-names = '

    formatted_registers = ',\n'.join(
        '"{}"'.format(reg['name'])
        for reg in regs
    )

    dtsi += indent_all_but_first(formatted_registers)
    dtsi += ';'

    return indent_all(dtsi) + '\n'


# DTS handlers
def disabled_handler(name, parm, csr):
    return indent('status = "disabled";\n')


def ram_handler(name, parm, csr):
    mem_reg = {
        'addr': csr['memories'][name]['base'],
        'size': csr['memories'][name]['size'],
    }

    return dts_reg([mem_reg])


def ethmac_handler(name, parm, csr):
    rx_registers = get_registers_of(name + '_sram_writer', csr)
    for reg in rx_registers:
        reg['name'] = 'rx_' + reg['name']

    tx_registers = get_registers_of(name + '_sram_reader', csr)
    for reg in tx_registers:
        reg['name'] = 'tx_' + reg['name']

    eth_buffers = {
        'name': 'buffers',
        'addr': csr['memories'][name]['base'],
        'size': csr['memories'][name]['size'],
        'type': csr['memories'][name]['type'],
    }
    registers = rx_registers + tx_registers + [eth_buffers]

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)
    dtsi += dts_intr(name, csr)
    return dtsi


def i2c_handler(name, parm, csr):
    registers = get_registers_of(name, csr)
    if len(registers) == 0:
        raise KeyError

    for reg in registers:
        if reg["name"] == "w":
            reg["name"] = "write"
        elif reg["name"] == "r":
            reg["name"] = "read"

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)

    return dtsi


def i2s_handler(name, parm, csr):
    registers = get_registers_of(name, csr)
    if len(registers) == 0:
        raise KeyError

    fifo = {
        'name': 'fifo',
        'addr': csr['memories'][name]['base'],
        'size': csr['memories'][name]['size'],
        'type': csr['memories'][name]['type'],
    }
    registers.append(fifo)

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)

    try:
        dtsi += dts_intr(name, csr)
    except KeyError as e:
        print('  dtsi key', e, 'not found, no interrupt override')
    return dtsi


def peripheral_handler(name, parm, csr):
    registers = get_registers_of(name, csr)
    if len(registers) == 0:
        raise KeyError

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)

    try:
        dtsi += dts_intr(name, csr)
    except KeyError as e:
        print('  dtsi key', e, 'not found, no interrupt override')
    return dtsi


overlay_handlers = {
    'uart': {
        'handler': peripheral_handler,
        'alias': 'uart0',
        'config_entry': 'UART_LITEUART'
    },
    'timer0': {
        'handler': peripheral_handler,
        'config_entry': 'LITEX_TIMER'
    },
    'ethmac': {
        'handler': ethmac_handler,
        'alias': 'eth0',
        'config_entry': 'ETH_LITEETH'
    },
    'spiflash': {
        'handler': peripheral_handler,
        'alias': 'spi0',
        'config_entry': 'SPI_LITESPI'
    },
    'sdcard_block2mem': {
        'handler': peripheral_handler,
        'alias': 'sdcard_block2mem',
        'size': 0x18,
        'config_entry': 'SD_LITESD'
    },
    'sdcard_core': {
        'handler': peripheral_handler,
        'alias': 'sdcard_core',
        'size': 0x2C,
        'config_entry': 'SD_LITESD'
    },
    'sdcard_irq': {
        'handler': peripheral_handler,
        'alias': 'sdcard_irq',
        'size': 0x0C,
        'config_entry': 'SD_LITESD'
    },
    'sdcard_mem2block': {
        'handler': peripheral_handler,
        'alias': 'sdcard_mem2block',
        'size': 0x18,
        'config_entry': 'SD_LITESD'
    },
    'sdcard_phy': {
        'handler': peripheral_handler,
        'alias': 'sdcard_phy',
        'size': 0x10,
        'config_entry': 'SD_LITESD'
    },
    'i2c0' : {
        'handler': i2c_handler,
        'config_entry': 'I2C_LITEX'
    },
    'i2s_rx' : {
        'handler': i2s_handler,
        'config_entry': 'I2S_LITEX'
    },
    'i2s_tx' : {
        'handler': i2s_handler,
        'config_entry': 'I2S_LITEX'
    },
    'mmcm' : {
        'alias': 'clock0',
        'handler': peripheral_handler,
        'config_entry': 'CLOCK_CONTROL_LITEX'
    },
    'main_ram': {
        'handler': ram_handler,
        'alias': 'ram0',
    },
    'identifier_mem': {
        'handler': peripheral_handler,
        'alias': 'dna0',
    }
}


def generate_dts_config(csr):
    dts = cnf = ''

    for name, parm in overlay_handlers.items():
        print('Generating overlay for:',name)
        enable = 'y'
        dtsi = dts_open(name, parm)

        try:
            dtsi += parm['handler'](name, parm, csr)
        except KeyError as e:
            print('  dtsi key', e, 'not found, disable', name)
            enable = 'n'
            dtsi += disabled_handler(name, parm, csr)

        dtsi += dts_close()
        dts += dtsi
        if 'config_entry' in parm:
            cnf += ' -DCONFIG_' + parm['config_entry'] + '=' + enable 

    for name, value in csr['csr_bases'].items():
        if name not in overlay_handlers.keys():
            print('No overlay handler for:', name, 'at', hex(value))

    cnf += ' -DCONFIG_LITEX_CSR_DATA_WIDTH={}'.format(
        csr['constants']['config_csr_data_width'],
    )

    return dts, cnf


# helpers
def print_or_save(filepath, lines):
    """ Prints given string on standard output or to the file.

    Args:
        filepath (string): path to the file lines should be written to
                           or '-' to write to a standard output
        lines (string): content to be printed/written
    """
    if filepath == '-':
        print(lines)
    else:
        with open(filepath, 'w') as f:
            f.write(lines)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('conf_file',
                        help='JSON configuration generated by LiteX')
    parser.add_argument('--dts', action='store', required=True,
                        help='Output DTS overlay file')
    parser.add_argument('--config', action='store', required=True,
                        help='Output config overlay file')
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.conf_file) as f:
        csr = json.load(f)
    dts, config = generate_dts_config(csr)

    print_or_save(args.dts, dts)
    print_or_save(args.config, config)


if __name__ == '__main__':
    main()
