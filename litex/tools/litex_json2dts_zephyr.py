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
    return '\n'.join([indent(line, levels) for line in text.splitlines()])


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


def dts_intr(name, csr, levels=1):
    irq = csr['constants'].get(name + '_interrupt', None)
    return indent(f"interrupts = <{irq} 1>;\n" if irq is not None else "", levels)


def dts_reg(regs, levels=1):
    dtsi = 'reg = <'

    formatted_registers = '>,\n<'.join(
        '0x{:x} 0x{:x}'.format(reg['addr'], reg['size'])
        for reg in regs
    )

    dtsi += indent_all_but_first(formatted_registers, 1)
    dtsi += '>;'

    return indent_all(dtsi, levels) + '\n'


def dts_reg_names(regs, levels=1):
    dtsi = 'reg-names = '

    formatted_registers = ',\n'.join(
        '"{}"'.format(reg['name'])
        for reg in regs
    )

    dtsi += indent_all_but_first(formatted_registers, 1)
    dtsi += ';'

    return indent_all(dtsi, levels) + '\n'


# DTS handlers
def disabled_handler(name, parm, csr):
    return indent('status = "disabled";\n')

def cpu_handler(name, parm, csr):
    return indent("clock-frequency = <{}>;\n".format(
        csr['constants']['config_clock_frequency']
    ))

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

    eth_buffers = [{
        'name': 'rx_buffers',
        'addr': csr['memories'][name + '_rx']['base'],
        'size': csr['memories'][name + '_rx']['size'],
        'type': csr['memories'][name + '_rx']['type'],
    },
    {
        'name': 'tx_buffers',
        'addr': csr['memories'][name + '_tx']['base'],
        'size': csr['memories'][name + '_tx']['size'],
        'type': csr['memories'][name + '_tx']['type'],
    }]
    registers = rx_registers + tx_registers + eth_buffers

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)
    dtsi += dts_intr(name, csr)
    return dtsi

def ethphy_mdio_handler(name, parm, csr):
    registers = get_registers_of(name + '_mdio', csr)
    if len(registers) == 0:
        raise KeyError

    for reg in registers:
        reg["name"] = "mdio_" + reg["name"]

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)
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


def spimaster_handler(name, parm, csr):
    registers = get_registers_of(name, csr)
    if len(registers) == 0:
        raise KeyError

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)

    dtsi += indent("clock-frequency = <{}>;\n".format(
        csr['constants'][name + '_frequency']))

    dtsi += indent("data-width = <{}>;\n".format(
        csr['constants'][name + '_data_width']))

    dtsi += indent("max-cs = <{}>;\n".format(
        csr['constants'][name + '_max_cs']))

    return dtsi


def spiflash_handler(name, parm, csr):
    registers = get_registers_of(name, csr)
    if len(registers) == 0:
        raise KeyError

    # Add memory mapped region for spiflash, the linker script in zephyr expects this region to be
    # the entry with the name flash_mmap in the reg property of the spi controller.
    try:
        registers.append({
            'addr': csr['memories'][name]['base'],
            'size': csr['memories'][name]['size'],
            'name': 'flash_mmap',
        })
    except KeyError as e:
        print('memory mapped', e, 'not found')

    dtsi = dts_reg(registers)
    dtsi += dts_reg_names(registers)

    dtsi += indent("clock-frequency = <{}>;\n".format(
        csr['constants'][name + '_phy_frequency']))

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


_overlay_handlers = {
    'cpu': {
        'handler': cpu_handler,
        'alias': 'cpu0',
    },
    'ctrl': {
        'handler': peripheral_handler,
        'alias': 'ctrl0',
    },
    'uart': {
        'handler': peripheral_handler,
        'alias': 'uart0',
    },
    'timer0': {
        'handler': peripheral_handler,
    },
    'ethmac': {
        'handler': ethmac_handler,
        'alias': 'eth0',
    },
    'ethphy': {
        'handler': ethphy_mdio_handler,
        'alias': 'mdio0',
    },
    'spimaster': {
        'handler': spimaster_handler,
        'alias': 'spi0',
    },
    'spiflash': {
        'handler': spiflash_handler,
        'alias': 'spi1',
    },
    'sdcard': {
        'handler': peripheral_handler,
        'alias': 'sdhc0',
        'disable_handler': False,
    },
    'i2c0' : {
        'handler': i2c_handler,
    },
    'i2s_rx' : {
        'handler': i2s_handler,
    },
    'i2s_tx' : {
        'handler': i2s_handler,
    },
    'watchdog0': {
        'handler': peripheral_handler,
        'alias': 'wdt0',
    },
    'mmcm' : {
        'alias': 'clock0',
        'handler': peripheral_handler,
    },
    'main_ram': {
        'handler': ram_handler,
        'alias': 'ram0',
    },
    'identifier_mem': {
        'handler': peripheral_handler,
        'alias': 'dna0',
    },
    'prbs0': {
        'handler': peripheral_handler,
    }
}


def generate_dts_config(csr, overlay_handlers):
    dts = cnf = ''

    for name, parm in overlay_handlers.items():
        print('Generating overlay for:',name)
        enable = 'y'
        dtsi = dts_open(name, parm)

        try:
            dtsi += parm['handler'](name, parm, csr)
        except KeyError as e:
            enable = 'n'
            if parm.get('disable_handler', True):
                print('  dtsi key', e, 'not found, disable', name)
                dtsi += disabled_handler(name, parm, csr)
            else:
                print('  dtsi key', e, 'not found, skip', name)
                continue
        
        dtsi += dts_close()
        dts += dtsi
        if 'config_entry' in parm:
            cnf += ' -DCONFIG_' + parm['config_entry'] + '=' + enable 

    for name, value in csr['csr_bases'].items():
        if name not in overlay_handlers.keys():
            print('No overlay handler for:', name, 'at', hex(value))

    # Default CSR data width in zephyr is 32 bits
    if csr['constants']['config_csr_data_width'] != 32:
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
    if filepath == '-' or filepath is None:
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
    parser.add_argument('--config', action='store',
                        help='Output config overlay file')
    return parser.parse_args()


def main():
    args = parse_args()

    with open(args.conf_file) as f:
        csr = json.load(f)
    dts, config = generate_dts_config(csr, _overlay_handlers)

    print_or_save(args.dts, dts)
    print_or_save(args.config, config)


if __name__ == '__main__':
    main()
