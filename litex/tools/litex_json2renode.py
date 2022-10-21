#!/usr/bin/env python3
"""
Copyright (c) 2019-2022 Antmicro <www.antmicro.com>

Renode platform definition (repl) and script (resc) generator for LiteX SoC.

This script parses LiteX 'csr.json' file and generates scripts for Renode
necessary to emulate the given configuration of the LiteX SoC.
"""

import os
import sys
import json
import pprint
import zlib
import argparse


# those memory regions are handled in a special way
# and should not be generated automatically
non_generated_mem_regions = ['ethmac', 'csr']

def get_soc_interrupt_parent(csr):
    '''
        We assume that for multi-core setups plic will be used hence cpu0 is enough
    '''
    if 'plic' in csr['memories']:
        return 'plic'
    else:
        return 'cpu0'

def get_descriptor(csr, name, size=None):
    res = { 'base': csr['csr_bases'][name], 'constants': {} }

    for c in csr['constants']:
        if c.startswith('{}_'.format(name)):
            res['constants'][c[len(name) + 1:]] = csr['constants'][c]

    if size:
        res['size'] = size

    return res


def generate_sysbus_registration(descriptor,
                                 skip_braces=False, region=None, skip_size=False):
    """ Generates system bus registration information
    consisting of a base address and an optional shadow
    address.

    Args:
        descriptor (dict): dictionary containing 'address',
                          'shadowed_address' (might be None) and
                          optionally 'size' fields
        skip_braces (bool): determines if the registration info should
                            be put in braces
        region (str or None): name of the region, if None the default
                              one is assumed
        skip_size (bool): if set to true do not set size

    Returns:
        string: registration information
    """

    def generate_registration_entry(address, size=None, name=None):
        if name:
            if not size:
                raise Exception('Size must be provided when registering non-default region')
            return 'sysbus new Bus.BusMultiRegistration {{ address: {}; size: {}; region: "{}" }}'.format(hex(address), hex(size), name)
        if size:
            return "sysbus <{}, +{}>".format(hex(address), hex(size))
        return "sysbus {}".format(hex(address))

    address = descriptor['base']
    size = descriptor['size'] if 'size' in descriptor and not skip_size else None

    if 'shadowed_address' in descriptor:
        result = "{}; {}".format(
            generate_registration_entry(address, size, region),
            generate_registration_entry(descriptor['shadowed_address'], size, region))
    else:
        result = generate_registration_entry(address, size, region)

    if not skip_braces:
        result = "{{ {} }}".format(result)

    return result


def generate_ethmac(csr, name, **kwargs):
    """ Generates definition of 'ethmac' peripheral.

    Args:
        csr (dict): LiteX configuration
        name (string): name of the peripheral
        kwargs (dict): additional parameters, including 'buffer'

    Returns:
        string: repl definition of the peripheral
    """
    buf = csr['memories']['ethmac']
    phy = get_descriptor(csr, 'ethphy', 0x800)
    peripheral = get_descriptor(csr, name)

    result = """
ethmac: Network.LiteX_Ethernet{} @ {{
    {};
    {};
    {}
}}
""".format('_CSR32' if csr['constants']['config_csr_data_width'] == 32 else '',
           generate_sysbus_registration(peripheral,
                                        skip_braces=True),
           generate_sysbus_registration(buf,
                                        skip_braces=True, region='buffer'),
           generate_sysbus_registration(phy,
                                        skip_braces=True, region='phy'))

    interrupt_name = '{}_interrupt'.format(name)
    if interrupt_name in csr['constants']:
        result += '    -> {}@{}\n'.format(
            get_soc_interrupt_parent(csr),
            csr['constants'][interrupt_name])

    result += """

ethphy: Network.EthernetPhysicalLayer @ ethmac 0
    VendorSpecific1: 0x4400 // MDIO status: 100Mbps + link up
"""

    return result


def generate_memory_region(region_descriptor):
    """ Generates definition of memory region.

    Args:
        region_descriptor (dict): memory region description

    Returns:
        string: repl definition of the memory region
    """

    result = ""

    if 'original_address' in region_descriptor:
        result += """
This memory region's base address has been
realigned to allow to simulate it -
Renode currently supports memory regions
with base address aligned to 0x1000.

The original base address of this memory region
was {}.
""".format(hex(region_descriptor['original_address']))

    if 'original_size' in region_descriptor:
        result += """
This memory region's size has been
extended to allow to simulate it -
Renode currently supports memory regions
of size being a multiple of 0x1000.

The original size of this memory region
was {} bytes.
""".format(hex(region_descriptor['original_size']))

    if result != "":
        result = """
/* WARNING:
{}
*/""".format(result)

    result += """
{}: Memory.MappedMemory @ {}
    size: {}
""".format(region_descriptor['name'],
           generate_sysbus_registration(region_descriptor, skip_size=True, skip_braces=True),
           hex(region_descriptor['size']))

    return result


def generate_silencer(csr, name, **kwargs):
    """ Silences access to a memory region.

    Args:
        csr (dict): LiteX configuration
        name (string): name of the peripheral
        kwargs (dict): additional parameters, not used

    Returns:
        string: repl definition of the silencer
    """
    return """
sysbus:
    init add:
        SilenceRange <0x{:08x} 0x200> # {}
""".format(csr['csr_bases'][name], name)


def get_cpu_type(csr):
    kind = None
    variant = None

    config_cpu_type = next((k for k in csr['constants'].keys() if k.startswith('config_cpu_type_')), None)
    if config_cpu_type:
        kind = config_cpu_type[len('config_cpu_type_'):]

    config_cpu_variant = next((k for k in csr['constants'].keys() if k.startswith('config_cpu_variant_')), None)
    if config_cpu_variant:
        variant = config_cpu_variant[len('config_cpu_variant_'):]

    return (kind, variant)

def get_cpu_count(csr):
    return csr['constants']['config_cpu_count']

vexriscv_common_kind = {
    'name': 'VexRiscv',
    'variants': {
        'linux': {
             'properties': ['cpuType: "rv32ima"', 'privilegeArchitecture: PrivilegeArchitecture.Priv1_10'],
        },
        'i': {
             'properties': ['cpuType: "rv32i"'], 
        },
        'im': {
             'properties': ['cpuType: "rv32im"'], 
        },
        'ima': {
             'properties': ['cpuType: "rv32ima"'], 
        },
        'imac': {
             'properties': ['cpuType: "rv32imac"'], 
        },
        'others': {
             'properties': ['cpuType: "rv32im"'],
        }
    },
    'supports_time_provider': True,
}
cpu_kinds = {
    'vexriscv': vexriscv_common_kind,
    'vexriscv_smp': vexriscv_common_kind,
    'picorv32': {
        'name': 'PicoRV32',
        'properties': ['cpuType: "rv32imc"'],
    },
    'minerva': {
        'name': 'Minerva',
    },
    'ibex': {
        'name': 'IbexRiscV32',
    },
    'cv32e40p': {
        'name': 'CV32E40P',
        'supports_time_provider': True,
        'properties': ['cpuType: "rv32imc"'],
    }
}

def generate_cpu(csr, time_provider, number_of_cores):
    """ Generates definition of a CPU.

    Returns:
        string: repl definition of the CPU
    """
    kind, variant = get_cpu_type(csr)

    try:
        cpu = cpu_kinds[kind]

        cpu_string = f'{cpu["name"]} @ sysbus\n'
        
        def unpack_properties(prop_list):
            return ''.join([f'    {prop}\n' for prop in prop_list])

        if 'properties' in cpu:
            cpu_string += unpack_properties(cpu["properties"])

        if 'variants' in cpu:
            variant = cpu['variants'].get(variant)

            if variant is None:
                variant = cpu['variants'].get('others', [])

            if 'properties' in variant:
                cpu_string += unpack_properties(variant["properties"])

    except KeyError:
        raise Exception(f'Unsupported cpu type: {kind}')

    result = ''
    for cpu_id in range(0, number_of_cores):
        result += f"""
cpu{cpu_id}: CPU.{cpu_string.strip()}
    hartId: {cpu_id}
"""
        if cpu.get('supports_time_provider', False):
            result += f'    timeProvider: {time_provider}\n'

    return result

def generate_peripheral(csr, name, **kwargs):
    """ Generates definition of a peripheral.

    Args:
        csr (dict): LiteX configuration
        name (string): name of the peripheral
        kwargs (dict): additional parameterss, including
                       'model' and 'properties'

    Returns:
        string: repl definition of the peripheral
    """

    peripheral = get_descriptor(csr, name)

    model = kwargs['model']
    if csr['constants']['config_csr_data_width'] == 32 and 'model_CSR32' in kwargs:
        model = kwargs['model_CSR32']

    result = '\n{}: {} @ {}\n'.format(
        kwargs['name'] if 'name' in kwargs else name,
        model,
        generate_sysbus_registration(peripheral))

    for constant, val in peripheral['constants'].items():
        if 'ignored_constants' not in kwargs or constant not in kwargs['ignored_constants']:
            if constant == 'interrupt':
                result += '    -> {}@{}\n'.format(get_soc_interrupt_parent(csr), val)
            else:
                result += '    {}: {}\n'.format(constant, val)

    if 'properties' in kwargs:
        for prop, val in kwargs['properties'].items():
            result += '    {}: {}\n'.format(prop, val(csr))

    if 'interrupts' in kwargs:
        for prop, val in kwargs['interrupts'].items():
            result += '    {} -> {}\n'.format(prop, val())

    return result


def generate_spiflash(csr, name, **kwargs):
    """ Generates definition of an SPI controller with attached flash memory.

    Args:
        csr (dict): LiteX configuration
        name (string): name of the peripheral
        kwargs (dict): additional parameterss, including
                       'model' and 'properties'

    Returns:
        string: repl definition of the peripheral
    """

    peripheral = get_descriptor(csr, name)

    result = """
spi_flash: SPI.LiteX_SPI_Flash @ {{
    {}
}}

mt25q: SPI.Micron_MT25Q @ spi_flash
    underlyingMemory: spiflash
""".format(
        generate_sysbus_registration(peripheral, skip_braces=True))
    return result


def generate_cas(csr, name, **kwargs):
    result = generate_peripheral(csr, name, model='GPIOPort.LiteX_ControlAndStatus', ignored_constants=['leds_count', 'switches_count', 'buttons_count'])

    peripheral = get_descriptor(csr, name)

    leds_count = int(peripheral['constants']['leds_count'])
    switches_count = int(peripheral['constants']['switches_count'])
    buttons_count = int(peripheral['constants']['buttons_count'])

    for i in range(leds_count):
        result += """
    {} -> led{}@0
""".format(i, i)

    for i in range(leds_count):
        result += """
led{}: Miscellaneous.LED @ cas {}
""".format(i, i)

    for i in range(switches_count):
        result += """
switch{}: Miscellaneous.Button @ cas {}
    -> cas@{}
""".format(i, i + 32, i + 32)

    for i in range(buttons_count):
        result += """
button{}: Miscellaneous.Button @ cas {}
    -> cas@{}
""".format(i, i + 64, i + 64)

    return result


def generate_mmc(csr, name, **kwargs):
    """ Generates definition of 'mmc' peripheral.

    Args:
        csr (dict): LiteX configuration
        name (string): name of the peripheral
        kwargs (dict): additional parameters, including 'core', 'reader' and 'writer'

    Returns:
        string: repl definition of the peripheral
    """

    # FIXME: Get litex to generate CSR region size into output information
    # currently only a base address is present
    peripheral = get_descriptor(csr, name)
    core = get_descriptor(csr, 'sdcore', 0x100)
    reader = get_descriptor(csr, 'sdblock2mem', 0x100)
    writer = get_descriptor(csr, 'sdmem2block', 0x100)

    result = """
mmc_controller: SD.LiteSDCard{} @ {{
    {}; // phy
    {};
    {};
    {}
}}
""".format('_CSR32' if csr['constants']['config_csr_data_width'] == 32 else '',
           generate_sysbus_registration(peripheral,
                                        skip_braces=True),
           generate_sysbus_registration(core,
                                        skip_braces=True, region='core'),
           generate_sysbus_registration(reader,
                                        skip_braces=True, region='reader'),
           generate_sysbus_registration(writer,
                                        skip_braces=True, region='writer'))

    return result


def generate_clint(clint, frequency, number_of_cores):
    # TODO: this is configuration for VexRiscv - add support for other CPU types
    result = """
clint: IRQControllers.CoreLevelInterruptor @ {}
    frequency: {}
    numberOfTargets: {}
""".format(generate_sysbus_registration(clint,
                                        skip_braces=True,
                                        skip_size=True),
           frequency, number_of_cores)

    for cpu_id in range(0, number_of_cores):
        result += f"    [{2 * cpu_id}, {2 * cpu_id + 1}] -> cpu{cpu_id}@[101, 100]\n"

    return result


def generate_plic(plic, number_of_cores):
    # TODO: this is configuration for linux-on-litex-vexriscv - add support for other CPU types
    result = """
plic: IRQControllers.PlatformLevelInterruptController @ {}
    numberOfSources: 31
    numberOfContexts: {}
    prioritiesEnabled: false
""".format(generate_sysbus_registration(plic,
                                        skip_braces=True,
                                        skip_size=True),
           2 * number_of_cores)

    for cpu_id in range(0, number_of_cores):
        result += f"    [{2 * cpu_id}, {2 * cpu_id + 1}] -> cpu{cpu_id}@[11, 9]\n"

    return result


def generate_video_framebuffer(csr, name, **kwargs):
    peripheral = get_descriptor(csr, name, 0xc) # This is simultaneously the "dma" region
    vtg = get_descriptor(csr, name + "_vtg", 0x24)

    constants = peripheral['constants']

    hres = int(constants['hres'])
    vres = int(constants['vres'])
    base = int(constants['base'])

    memory = find_memory_region(csr['filtered_memories'], base)
    if memory is None:
        raise Exception("Framebuffer base does not belong to a memory region")

    offset = base - memory['base']

    result = """
litex_video: Video.LiteX_Framebuffer_CSR32 @ {{
    {};
    {}
}}
    format: PixelFormat.XBGR8888
    memory: {}
    offset: 0x{:08x}
    hres: {}
    vres: {}
""".format(generate_sysbus_registration(peripheral,
                                        skip_braces=True, region='dma'),
           generate_sysbus_registration(vtg,
                                        skip_braces=True, region='vtg'),
           memory['name'], offset, hres, vres)

    return result


def get_clock_frequency(csr):
    """
    Args:
        csr (dict): LiteX configuration

    Returns:
        int: system clock frequency
    """
    # in different LiteX versions this property
    # has different names
    return csr['constants']['config_clock_frequency' if 'config_clock_frequency' in csr['constants'] else 'system_clock_frequency']

def generate_gpio_port(csr, name, **kwargs):
    peripheral = get_descriptor(csr, name)

    ints = ''
    if 'interrupt' in kwargs:
        ints += f'    IRQ -> {get_soc_interrupt_parent(csr)}@{kwargs["interrupt"]}'
    if 'connections' in kwargs:
        for irq, target in zip(kwargs['connections'], kwargs['connections_targets']):
            ints += f'    {irq} -> {target}\n'
    
    result = """
gpio_{}: GPIOPort.LiteX_GPIO @ {}
    type: {}
    enableIrq: {}
{}
""".format(name, 
           generate_sysbus_registration(peripheral, skip_braces=True),
           kwargs['type'], 
           'true' if kwargs['type'] != 'Type.Out' else 'false',
           ints)

    return result

def generate_switches(csr, name, **kwargs):
    interrupt_name = '{}_interrupt'.format(name)
    result = generate_gpio_port(csr, name, **{'type': 'Type.In', 'interrupt': csr['constants'][interrupt_name], **kwargs})

    # Litex puts 4 by default into dts (litex_json2dts)
    count = int(csr['constants'].get(f'{name}_ngpio', 4))

    for i in range(0, count):
        result += """
{name}_{i}: Miscellaneous.Button @ {periph} {i}
    -> {periph}@{i}
""".format(name=name, periph=f"gpio_{name}", i=i)

    return result

def generate_leds(csr, name, **kwargs):
    # Litex puts 4 by default into dts (litex_json2dts)
    count = int(csr['constants'].get(f'{name}_ngpio', 4))
    
    result = generate_gpio_port(csr, name,  
        **{'type': 'Type.Out',
           'connections': [*range(0, count)],
           'connections_targets': [f'leds_{i}@0' for i in range(0, count)],
            **kwargs})

    for i in range(0, count):
        result += """
{name}_{i}: Miscellaneous.LED @ {periph} {i}
""".format(name=name, periph=f"gpio_{name}", i=i)

    return result

def handled_peripheral(csr, name, **kwargs):
    """
        Use this to silence warnings about unsupported peripherals, that are in reality emulated by other peripheral
        e. g. mmc, ethmac
    """
    return ''

peripherals_handlers = {
    'uart': {
        'handler': generate_peripheral,
        'model': 'UART.LiteX_UART',
        'ignored_constants': ['polling']
    },
    'timer0': {
        'handler': generate_peripheral,
        'model': 'Timers.LiteX_Timer',
        'model_CSR32': 'Timers.LiteX_Timer_CSR32',
        'properties': {
            'frequency':
                lambda c: get_clock_frequency(c)
        }
    },
    'ethmac': {
        'handler': generate_ethmac,
    },
    'cas': {
        'handler': generate_cas,
    },
    'cpu': {
        'name': 'cpu_timer',
        'handler': generate_peripheral,
        'model': 'Timers.LiteX_CPUTimer',
        'properties': {
            'frequency':
                lambda c: get_clock_frequency(c)
        },
        'interrupts': {
            # IRQ #100 in Renode's VexRiscv model is mapped to Machine Timer Interrupt
            'IRQ': lambda: 'cpu0@100'
        }
    },
    'ddrphy': {
        'handler': generate_silencer
    },
    'sdram': {
        'handler': generate_silencer
    },
    'spiflash': {
        'handler': generate_spiflash
    },
    'spi': {
        'handler': generate_peripheral,
        'model': 'SPI.LiteX_SPI',
        'ignored_constants': ['interrupt'] # model in Renode currently doesn't support interrupts
    },
    'ctrl': {
        'handler': generate_peripheral,
        'model': 'Miscellaneous.LiteX_SoC_Controller',
        'model_CSR32': 'Miscellaneous.LiteX_SoC_Controller_CSR32'
    },
    'i2c0': {
        'handler': generate_peripheral,
        'model': 'I2C.LiteX_I2C'
    },
    'sdphy': {
        'handler': generate_mmc,
    },
    'spisdcard': {
        'handler': generate_peripheral,
        'model': 'SPI.LiteX_SPI',
        'ignored_constants': ['interrupt'] # model in Renode currently doesn't support interrupts
    },
    'video_framebuffer': {
        'handler': generate_video_framebuffer,
    },
    'video_framebuffer_vtg': {
        'handler': handled_peripheral, # This is handled by generate_video_framebuffer
    },
    'leds': {
        'handler': generate_leds,
    },
    'switches': {
        'handler': generate_switches,
    },
    'mmcm': {
        'handler': generate_peripheral,
        'model': 'Miscellaneous.LiteX_MMCM',
        'model_CSR32': 'Miscellaneous.LiteX_MMCM_CSR32',
        'ignored_constants': ['lock_timeout', 'drdy_timeout'],
    },
    'ethphy': {
        'handler': handled_peripheral # by generate_ethmac
    },
    # handled by generate_mmc
    'sdblock2mem': {
        'handler': handled_peripheral
    },
    'sdmem2block': {
        'handler': handled_peripheral
    },
    'sdcore': {
        'handler': handled_peripheral
    },
}


def generate_etherbone_bridge(name, address, port):
    # FIXME: for now the width is fixed to 0x800
    return """
{}: EtherboneBridge @ sysbus <{}, +0x800>
    port: {}
""".format(name, hex(address), port)


def generate_repl(csr, etherbone_peripherals, autoalign, number_of_cores):
    """ Generates platform definition.

    Args:
        csr (dict): LiteX configuration

        etherbone_peripherals (dict): collection of peripherals
            that should not be simulated directly in Renode,
            but connected to it over an etherbone bridge on
            a provided port number

        autoalign (list): list of memory regions names that
                          should be automatically re-aligned

    Returns:
        string: platform defition containing all supported
                peripherals and memory regions
    """
    result = ""

    # RISC-V CPU in Renode requires memory region size
    # to be a multiple of 4KB - this is a known limitation
    # (not a bug) and there are no plans to handle smaller
    # memory regions for now
    memories = []
    for m in csr['memories']:
        x = dict(csr['memories'][m])
        x['name'] = m
        memories.append(x)

    filtered_memories = list(filter_memory_regions(memories, alignment=0x1000, autoalign=autoalign))
    csr['filtered_memories'] = filtered_memories # Save for use by peripheral generators

    for mem_region in filtered_memories:
        result += generate_memory_region(mem_region)

    time_provider = None
    if 'clint' in csr['memories']:
        result += generate_clint(csr['memories']['clint'], csr['constants']['config_clock_frequency'], number_of_cores)
        time_provider = 'clint'

    if 'plic' in csr['memories']:
        result += generate_plic(csr['memories']['plic'], number_of_cores)

    if not time_provider and 'cpu' in csr['csr_bases']:
        time_provider = 'cpu_timer'

    result += generate_cpu(csr, time_provider, number_of_cores)

    for name, address in csr['csr_bases'].items():
        if name not in peripherals_handlers:
            print('Skipping unsupported peripheral `{}` at {}'
                  .format(name, hex(address)))
            continue

        if name in etherbone_peripherals:
            # generate an etherbone bridge for the peripheral
            port = etherbone_peripherals[name]
            result += generate_etherbone_bridge(name, address, port)
            pass
        else:
            # generate an actual model of the peripheral
            h = peripherals_handlers[name]
            result += h['handler'](csr, name, **h)

    return result


def filter_memory_regions(raw_regions, alignment=None, autoalign=[]):
    """ Filters memory regions, skipping those that are included
        in each other, those that have size equal to 0
        and those from `non_generated_mem_regions` list
        and verifying if they have proper size and do not overlap.

        Args:
            raw_regions (list): list of memory regions parsed from
                                the configuration file
            alignment (int or None): memory size boundary

            autoalign (list): list of memory regions names that
                              should be automatically re-aligned
        Returns:
            list: reduced, sorted list of memory regions to be generated
                  in a repl file
    """
    previous_region = None

    raw_regions.sort(key=lambda x: x['base'])
    for r in raw_regions:
        if 'io' in r['type']:
            print('Skipping io region: {}'.format(r['name']))
            continue

        if r['name'] in non_generated_mem_regions:
            print('Skipping pre-defined memory region: {}'.format(r['name']))
            continue

        if alignment is not None:
            size_mismatch = r['size'] % alignment
            address_mismatch = r['base'] % alignment

            def print_autoalign_hint():
                print('Hint: use "--auto-align {}" to force automatic alignement of the region'.format(r['name']))
            if address_mismatch != 0:
                if r['name'] in autoalign:
                    r['original_address'] = r['base']
                    r['base'] -= address_mismatch
                    print('Re-aligning `{}` memory region base address from {} to {} due to limitations in Renode'.format(r['name'], hex(r['original_address']), hex(r['base'])))
                else:
                    print('Error: `{}` memory region base address ({}) is not aligned to {}. This configuration cannot be currently simulated in Renode'.format(r['name'], hex(r['size']), hex(alignment)))
                    print_autoalign_hint()
                    sys.exit(1)

            if size_mismatch != 0:
                if r['name'] in autoalign:
                    r['original_size'] = r['size']
                    r['size'] += alignment - size_mismatch
                    print('Extending `{}` memory region size from {} to {} due to limitations in Renode'.format(r['name'], hex(r['original_size']), hex(r['size'])))
                else:
                    print('Error: `{}` memory region size ({}) is not aligned to {}. This configuration cannot be currently simulated in Renode'.format(r['name'], hex(r['size']), hex(alignment)))
                    print_autoalign_hint()
                    sys.exit(1)

        if r['size'] == 0:
            print('Skipping `{}` due to size equal to 0'.format(r['name']))
            continue

        if previous_region is not None and r['base'] >= previous_region['base'] and r['base'] + r['size'] <= previous_region['base'] + previous_region['size']:
            print('Skipping `{}` since it is included in `{}`'.format(r['name'], previous_region['name']))
            continue

        if previous_region is not None and r['base'] < previous_region['base'] + previous_region['size'] and r['base'] + r['size'] > previous_region['base'] + previous_region['size']:
            print('Error: `{}` overlaps with `{}` - this configuration cannot be currently simulated in Renode'.format(r['name'], previous_region['name']))
            sys.exit(1)

        previous_region = r
        yield r


def find_memory_region(memory_regions, address):
    """ Finds the memory region containing the specified address.

        Args:
            memory_regions (list): list of memory regions filtered
                                   with filter_memory_regions
            address (int): the address to find

        Returns:
            dict or None: the region from `memory_regions` that contains
                          `address` or None if none of them do
    """
    for r in memory_regions:
        base, size = r['base'], r['size']
        end = base + size

        if base <= address < end:
            return r

    return None


def generate_resc(csr, number_of_cores, args, flash_binaries={}, tftp_binaries={}):
    """ Generates platform definition.

    Args:
        csr (dict): LiteX configuration
        args (object): configuration
        flash_binaries (dict): dictionary with paths and offsets of files
                               to load into flash
        tftp_binaries (dict): dictionary with paths and names of files
                               to serve with the built-in TFTP server

    Returns:
        string: platform defition containing all supported peripherals
                and memory regions
    """
    cpu_type, _ = get_cpu_type(csr)

    result = """
using sysbus
mach create "litex-{}"
machine LoadPlatformDescription @{}
machine StartGdbServer 10001
showAnalyzer sysbus.uart
showAnalyzer sysbus.uart Antmicro.Renode.Analyzers.LoggingUartAnalyzer
""".format(cpu_type, args.repl)

    opensbi_base = csr['memories']['opensbi']['base'] if 'opensbi' in csr['memories'] else None
    if opensbi_base is not None and args.bios_binary:
        # load LiteX BIOS to ROM
        result += """
sysbus LoadBinary @{} {}
""".format(args.bios_binary, hex(opensbi_base))

    for cpu_id in range(0, number_of_cores):
        result += f"cpu{cpu_id} PC {hex(opensbi_base)}\n"

    if args.tftp_ip:
        result += """

emulation CreateNetworkServer "server" "{}"
server StartTFTP {}
""".format(args.tftp_ip, args.tftp_port)

        for name, path in tftp_binaries.items():
            result += """
server.tftp ServeFile @{} "{}" """.format(path, name)

        result += """

emulation CreateSwitch "switch"
connector Connect ethmac switch
connector Connect server switch
"""

    elif args.configure_network:
        # configure network to allow netboot
        result += """
emulation CreateSwitch "switch"
emulation CreateTap "{}" "tap"
connector Connect ethmac switch
connector Connect host.tap switch
""".format(args.configure_network)
    elif flash_binaries:
        if 'spiflash' not in csr['memories']:
            print('Warning! There is no flash memory to load binaries to')
        else:
            # load binaries to spiflash to boot from there

            for offset in flash_binaries:
                path = flash_binaries[offset]
                flash_boot_address = int(csr['memories']['spiflash']['base']) + offset

                firmware_data = open(os.path.expanduser(path), 'rb').read()
                crc32 = zlib.crc32(firmware_data)

                result += 'sysbus WriteDoubleWord {} {}\n'.format(hex(flash_boot_address), hex(len(firmware_data)))
                result += 'sysbus WriteDoubleWord {} {}\n'.format(hex(flash_boot_address + 4), hex(crc32))
                result += 'sysbus LoadBinary @{} {}\n'.format(path, hex(flash_boot_address + 8))

    return result


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


def parse_flash_binaries(csr, args):
    flash_binaries = {}

    if args.firmware_binary:
        flash_binaries[0] = args.firmware_binary

    if args.flash_binaries_args:
        for entry in args.flash_binaries_args:
            path, separator, offset_or_label = entry.rpartition(':')
            if separator == '':
                print("Flash binary '{}' is in a wrong format. It should be 'path:offset'".format(entry))
                sys.exit(1)

            # offset can be either a number or one of the constants from the configuration
            try:
                # try a number first...
                offset = int(offset_or_label, 0)
            except ValueError:
                # ... if it didn't work, check constants
                if offset_or_label in csr['constants']:
                    offset = int(csr['constants'][offset_or_label], 0)
                else:
                    print("Offset is in a wrong format. It should be either a number or one of the constants from the configuration file:")
                    print("\n".join("\t{}".format(c) for c in csr['constants'].keys()))
                    sys.exit(1)
            
            flash_binaries[offset] = path

    return flash_binaries


def check_tftp_binaries(args):
    """
        Expected format is:
            * path_to_the_binary
            * path_to_the_binary:alternative_name
    """

    if args.tftp_ip is None and len(args.tftp_binaries_args) > 0:
        print('The TFPT server IP address must be provided')
        sys.exit(1)

    tftp_binaries = {}

    for entry in args.tftp_binaries_args:
        path, separator, name = entry.rpartition(':')
        if separator == '':
            # this means that no alternative name is provided, so we use the original one
            name = os.path.basename(entry)
            path = entry

        if name in tftp_binaries:
            print('File with name {} specified more than one - please check your configuration.'.format(name))
            sys.exit(1)

        tftp_binaries[name] = path

    return tftp_binaries


def check_etherbone_peripherals(peripherals):
    result = {}
    for p in peripherals:

        name, separator, port = p.rpartition(':')
        if separator == '':
            print("Etherbone peripheral `{}` is in a wrong format. It should be in 'name:port'".format(p))
            sys.exit(1)

        if name not in peripherals_handlers:
            print("Unsupported peripheral '{}'. Available ones:\n".format(name))
            print("\n".join("\t{}".format(c) for c in peripherals_handlers.keys()))
            sys.exit(1)
            
        if name == 'cpu':
            print("CPU must be simulated in Renode")
            sys.exit(1)

        result[name] = port

    return result


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument('conf_file',
                        help='JSON configuration generated by LiteX')
    parser.add_argument('--resc', action='store',
                        help='Output script file')
    parser.add_argument('--repl', action='store',
                        help='Output platform definition file')
    parser.add_argument('--configure-network', action='store',
                        help='Generate virtual network and connect it to host')
    parser.add_argument('--bios-binary', action='store',
                        help='Path to the BIOS binary')
    parser.add_argument('--firmware-binary', action='store',
                        help='Path to the binary to load into boot flash')
    parser.add_argument('--flash-binary', action='append', dest='flash_binaries_args',
                        help='Path and an address of the binary to load into boot flash')
    parser.add_argument('--etherbone', action='append', dest='etherbone_peripherals',
                        default=[],
                        help='Peripheral to connect over etherbone bridge')
    parser.add_argument('--auto-align', action='append', dest='autoalign_memor_regions',
                        default=[],
                        help='List of memory regions to align automatically (necessary due to limitations in Renode)')
    parser.add_argument('--tftp-binary', action='append', dest='tftp_binaries_args', default=[],
                        help='Path and an optional alternative name of the binary to serve by the TFTP server')
    parser.add_argument('--tftp-server-ip', action='store', dest='tftp_ip',
                        help='The IP address of the TFTP server')
    parser.add_argument('--tftp-server-port', action='store', default=69, type=int, dest='tftp_port',
                        help='The port number of the TFTP server')
    args = parser.parse_args()

    return args


def main():
    args = parse_args()

    with open(args.conf_file) as f:
        csr = json.load(f)

    etherbone_peripherals = check_etherbone_peripherals(args.etherbone_peripherals)

    number_of_cores = get_cpu_count(csr)

    if args.repl:
        print_or_save(args.repl, generate_repl(csr, etherbone_peripherals, args.autoalign_memor_regions, number_of_cores))

    if args.resc:
        if not args.repl:
            print("REPL is needed when generating RESC file")
            sys.exit(1)
        else:
            flash_binaries = parse_flash_binaries(csr, args)
            tftp_binaries = check_tftp_binaries(args)
            
            print_or_save(args.resc, generate_resc(csr, number_of_cores, args,
                                                   flash_binaries,
                                                   tftp_binaries))


if __name__ == '__main__':
    main()
