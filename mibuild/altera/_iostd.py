'''ALTERA I/O-Standards
'''
import collections
from mibuild.generic_platform import IOStandard

__all__ = ['IOSTD']

_LVTTL = collections.namedtuple(
    'V',
    'level1V8 level2V5 level3V0 level3V3')(
        IOStandard('1.8-V'),
        IOStandard('2.5-V'),
        IOStandard('3.0-V LVTTL'),
        IOStandard('3.3-V LVTTL'))

_LVCMOS = collections.namedtuple(
    'V',
    'level1V2 level1V5 level1V8 level2V5 level3V0 level3V3')(
        IOStandard('1.3 V'),
        IOStandard('1.5 V'),
        IOStandard('1.8 V'),
        IOStandard('2.5 V'),
        IOStandard('3.0-V LVCMOS'),
        IOStandard('3.3-V LVCMOS'))

_SSTL = collections.namedtuple(
    'V',
    'level1V5ClassI level1V5ClassII '
    'level1V8ClassI level1V8ClassII '
    'level2V0ClassI level2V0ClassII')(
        IOStandard('SSTL-15 Class I'),
        IOStandard('SSTL-15 Class II'),
        IOStandard('SSTL-18 Class I'),
        IOStandard('SSTL-18 Class II'),
        IOStandard('SSTL-2 Class I'),
        IOStandard('SSTL-2 Class II'))

_HSTL = collections.namedtuple(
    'V',
    'level1V2ClassI level1V2ClassII level1V5ClassI level1V5ClassII '
    'level1V8ClassI level1V8ClassII')(
        IOStandard('1.2-V HSTL Class I'),
        IOStandard('1.2-V HSTL Class II'),
        IOStandard('HSTL Class I'),
        IOStandard('HSTL Class II'),
        IOStandard('1.8-V HSTL Class I'),
        IOStandard('1.8-V HSTL Class II'))

_DiffSSTL = collections.namedtuple(
    'V',
    'level1V5 level1V8 level2V0')(
        IOStandard('Differential 1.5-V SSTL'),
        IOStandard('Differential 1.8-V SSTL'),
        IOStandard('Differential SSTL-2'))

_DiffHSTL = collections.namedtuple(
    'V',
    'level1V2 level1V5 level1V8')(
        IOStandard('Differential 1.2-V HSTL'),
        IOStandard('Differential 1.5-V HSTL'),
        IOStandard('Differential 1.8-V HSTL'))

_PCML = collections.namedtuple(
    'V',
    'level1V2 level1V4 level1V5 level2V5')(
        IOStandard('1.2-V PCML'),
        IOStandard('1.4-V PCML'),
        IOStandard('1.5-V PCML'),
        IOStandard('2.5-V PCML'))

IOSTD = collections.namedtuple(
    'CONST',
    'LVTTL LVCMOS PCI PCIX SSTL HSTL DiffSSTL DiffHSTL '
    'LVDS RSDS miniLVDS LVPECL DiffLVPECL BLVDS PCML DiffPCML HCSL')(
        _LVTTL,
        _LVCMOS,
        IOStandard('3.0-V PCI'),
        IOStandard('3.0-V PCI-X'),
        _SSTL,
        _HSTL,
        _DiffSSTL,
        _DiffHSTL,
        IOStandard('LVDS'),
        IOStandard('RSDS'),
        IOStandard('mini-LVDS'),
        IOStandard('LVPECL'),
        IOStandard('Differential LVPECL'),
        IOStandard('BLVDS'),
        _PCML,
        IOStandard('Differential PCML'),
        IOStandard('HCSL'))
