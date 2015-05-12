import math

from migen.fhdl.std import *
from migen.fhdl.decorators import ModuleTransformer
from migen.genlib.resetsync import *
from migen.genlib.fsm import *
from migen.genlib.record import *
from migen.genlib.misc import chooser, optree, Counter, WaitTimer
from migen.genlib.cdc import *
from migen.flow.actor import *
from migen.flow.plumbing import Multiplexer, Demultiplexer
from migen.actorlib.fifo import *
from migen.actorlib.structuring import Pipeline, Converter
from migen.actorlib.packet import Buffer
from migen.actorlib.misc import BufferizeEndpoints
from migen.actorlib.packet import HeaderField, Header

bitrates = {
    "sata_gen3": 6.0,
    "sata_gen2": 3.0,
    "sata_gen1": 1.5,
}

frequencies = {
    "sata_gen3": 150.0,
    "sata_gen2": 75.0,
    "sata_gen1": 37.5,
}

# PHY / Link Layers
primitives = {
    "ALIGN":  0x7B4A4ABC,
    "CONT":   0X9999AA7C,
    "SYNC":   0xB5B5957C,
    "R_RDY":  0x4A4A957C,
    "R_OK":   0x3535B57C,
    "R_ERR":  0x5656B57C,
    "R_IP":   0X5555B57C,
    "X_RDY":  0x5757B57C,
    "CONT":   0x9999AA7C,
    "WTRM":   0x5858B57C,
    "SOF":    0x3737B57C,
    "EOF":    0xD5D5B57C,
    "HOLD":   0xD5D5AA7C,
    "HOLDA":  0X9595AA7C
}


def is_primitive(dword):
    for k, v in primitives.items():
        if dword == v:
            return True
    return False


def decode_primitive(dword):
    for k, v in primitives.items():
        if dword == v:
            return k
    return ""


def phy_description(dw):
    layout = [
        ("data", dw),
        ("charisk", dw//8),
    ]
    return EndpointDescription(layout, packetized=False)


def link_description(dw):
    layout = [
        ("d", dw),
        ("error", 1)
    ]
    return EndpointDescription(layout, packetized=True)

# Transport Layer
fis_max_dwords = 2048

fis_types = {
    "REG_H2D":          0x27,
    "REG_D2H":          0x34,
    "DMA_ACTIVATE_D2H": 0x39,
    "PIO_SETUP_D2H":    0x5F,
    "DATA":             0x46
}

fis_reg_h2d_header_length = 5
fis_reg_h2d_header_fields = {
    "type":         HeaderField(0*4,  0, 8),
    "pm_port":      HeaderField(0*4,  8, 4),
    "c":            HeaderField(0*4, 15, 1),
    "command":      HeaderField(0*4, 16, 8),
    "features_lsb": HeaderField(0*4, 24, 8),

    "lba_lsb":      HeaderField(1*4, 0, 24),
    "device":       HeaderField(1*4, 24, 8),

    "lba_msb":      HeaderField(2*4, 0, 24),
    "features_msb": HeaderField(2*4, 24, 8),

    "count":        HeaderField(3*4, 0, 16),
    "icc":          HeaderField(3*4, 16, 8),
    "control":      HeaderField(3*4, 24, 8)
}
fis_reg_h2d_header = Header(fis_reg_h2d_header_fields,
                            fis_reg_h2d_header_length,
                            swap_field_bytes=False)

fis_reg_d2h_header_length = 5
fis_reg_d2h_header_fields = {
    "type":    HeaderField(0*4,  0, 8),
    "pm_port": HeaderField(0*4,  8, 4),
    "i":       HeaderField(0*4, 14, 1),
    "status":  HeaderField(0*4, 16, 8),
    "error":   HeaderField(0*4, 24, 8),

    "lba_lsb": HeaderField(1*4, 0, 24),
    "device":  HeaderField(1*4, 24, 8),

    "lba_msb": HeaderField(2*4, 0, 24),

    "count":   HeaderField(3*4, 0, 16)
}
fis_reg_d2h_header = Header(fis_reg_d2h_header_fields,
                            fis_reg_d2h_header_length,
                            swap_field_bytes=False)

fis_dma_activate_d2h_header_length = 1
fis_dma_activate_d2h_header_fields = {
    "type":    HeaderField(0*4,  0, 8),
    "pm_port": HeaderField(0*4,  8, 4)
}
fis_dma_activate_d2h_header = Header(fis_dma_activate_d2h_header_fields,
                                     fis_dma_activate_d2h_header_length,
                                     swap_field_bytes=False)

fis_pio_setup_d2h_header_length = 5
fis_pio_setup_d2h_header_fields = {
    "type":           HeaderField(0*4,  0, 8),
    "pm_port":        HeaderField(0*4,  8, 4),
    "d":              HeaderField(0*4, 13, 1),
    "i":              HeaderField(0*4, 14, 1),
    "status":         HeaderField(0*4, 16, 8),
    "error":          HeaderField(0*4, 24, 8),

    "lba_lsb":        HeaderField(1*4, 0, 24),

    "lba_msb":        HeaderField(2*4, 0, 24),

    "count":          HeaderField(3*4, 0, 16),

    "transfer_count": HeaderField(4*4, 0, 16),
}
fis_pio_setup_d2h_header = Header(fis_pio_setup_d2h_header_fields,
                                  fis_pio_setup_d2h_header_length,
                                  swap_field_bytes=False)

fis_data_header_length = 1
fis_data_header_fields = {
    "type": HeaderField(0,  0, 8)
}
fis_data_header = Header(fis_data_header_fields,
                         fis_data_header_length,
                         swap_field_bytes=False)


def transport_tx_description(dw):
    layout = [
        ("type", 8),
        ("pm_port", 4),
        ("c", 1),
        ("command", 8),
        ("features", 16),
        ("lba", 48),
        ("device", 8),
        ("count", 16),
        ("icc", 8),
        ("control", 8),
        ("data", dw)
    ]
    return EndpointDescription(layout, packetized=True)


def transport_rx_description(dw):
    layout = [
        ("type", 8),
        ("pm_port", 4),
        ("r", 1),
        ("d", 1),
        ("i", 1),
        ("status", 8),
        ("errors", 8),
        ("lba", 48),
        ("device", 8),
        ("count", 16),
        ("transfer_count", 16),
        ("data", dw),
        ("error", 1)
    ]
    return EndpointDescription(layout, packetized=True)

# Command Layer
regs = {
    "WRITE_DMA_EXT":   0x35,
    "READ_DMA_EXT":    0x25,
    "IDENTIFY_DEVICE": 0xEC
}

reg_d2h_status = {
    "bsy":  7,
    "drdy": 6,
    "df":   5,
    "se":   5,
    "dwe":  4,
    "drq":  3,
    "ae":   2,
    "sns":  1,
    "cc":   0,
    "err":  0
}


def command_tx_description(dw):
    layout = [
        ("write", 1),
        ("read", 1),
        ("identify", 1),
        ("sector", 48),
        ("count", 16),
        ("data", dw)
    ]
    return EndpointDescription(layout, packetized=True)


def command_rx_description(dw):
    layout = [
        ("write", 1),
        ("read", 1),
        ("identify", 1),
        ("last", 1),
        ("failed", 1),
        ("data", dw)
    ]
    return EndpointDescription(layout, packetized=True)


def command_rx_cmd_description(dw):
    layout = [
        ("write", 1),
        ("read", 1),
        ("identify", 1),
        ("last", 1),
        ("failed", 1)
    ]
    return EndpointDescription(layout, packetized=False)


def command_rx_data_description(dw):
    layout = [
        ("data", dw)
    ]
    return EndpointDescription(layout, packetized=True)

# HDD
logical_sector_size = 512  # constant since all HDDs use this


def dwords2sectors(n):
    return math.ceil(n*4/logical_sector_size)


def sectors2dwords(n):
    return n*logical_sector_size//4
