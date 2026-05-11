#
# This file is part of LiteX.
#
# Copyright (c) 2026 Florent Kermarrec <florent@enjoy-digital.fr>
# SPDX-License-Identifier: BSD-2-Clause

from dataclasses import dataclass


@dataclass(frozen=True)
class RAMCapabilities:
    vendor:       str
    primitive:    str
    data_widths:  tuple
    sizes:        tuple
    byte_enable:  bool
    init:         bool
    read_latency: int
    ports:        str


CPU_RAM_IMPLEMENTATIONS = {
    "1w_1rs": {
        "generic": "Ram_1w_1rs_Generic.v",
        "intel":   "Ram_1w_1rs_Intel.v",
        "efinix":  "Ram_1w_1rs_Efinix.v",
    },
    "1w_1ra": {
        "generic": "Ram_1w_1ra_Generic.v",
    },
}

RAM_CAPABILITIES = {
    "up5k_spram": RAMCapabilities(
        vendor       = "lattice_ice40",
        primitive    = "SB_SPRAM256KA",
        data_widths  = (16, 32, 64),
        sizes        = (32*1024, 64*1024, 128*1024),
        byte_enable  = True,
        init         = False,
        read_latency = 1,
        ports        = "1rw",
    ),
    "nx_lram": RAMCapabilities(
        vendor       = "lattice_nx",
        primitive    = "SP512K",
        data_widths  = (32, 64),
        sizes        = (64*1024, 128*1024, 192*1024, 256*1024, 320*1024),
        byte_enable  = True,
        init         = True,
        read_latency = 1,
        ports        = "1rw",
    ),
    "fifo_sync_macro": RAMCapabilities(
        vendor       = "xilinx",
        primitive    = "FIFO_SYNC_MACRO",
        data_widths  = tuple(range(1, 73)),
        sizes        = ("18Kb", "36Kb"),
        byte_enable  = False,
        init         = False,
        read_latency = 0,
        ports        = "fifo",
    ),
}


def check_value(name, value, allowed):
    if value not in allowed:
        raise ValueError("Unsupported {}: {}.".format(name, value))


def platform_ram_vendor(platform):
    from litex.build.altera import AlteraPlatform
    from litex.build.efinix import EfinixPlatform

    if isinstance(platform, AlteraPlatform):
        return "intel"
    if isinstance(platform, EfinixPlatform):
        return "efinix"
    return "generic"


def get_cpu_ram_filename(platform, kind="1w_1rs"):
    if kind not in CPU_RAM_IMPLEMENTATIONS:
        raise ValueError("Unsupported CPU RAM kind: {}.".format(kind))

    filenames = CPU_RAM_IMPLEMENTATIONS[kind]
    return filenames.get(platform_ram_vendor(platform), filenames["generic"])


def split_init_data(data, data_width, block_data_width, block_words, depth_cascading, width_cascading):
    if data_width != block_data_width*width_cascading:
        raise ValueError("RAM data width does not match block width cascading.")

    data = list(data)
    max_word = 2**data_width
    for i, word in enumerate(data):
        if not isinstance(word, int) or not 0 <= word < max_word:
            raise ValueError("RAM init word {} does not fit in {} bits: {}.".format(i, data_width, word))

    total_words = block_words*depth_cascading
    if len(data) > total_words:
        raise ValueError("RAM init length exceeds RAM size: {} > {}.".format(len(data), total_words))
    data += [0]*(total_words - len(data))

    mask = 2**block_data_width - 1
    chunks = []
    for d in range(depth_cascading):
        chunks.append([])
        offset = d*block_words
        for w in range(width_cascading):
            shift = block_data_width*w
            chunks[d].append([
                (word >> shift) & mask
                for word in data[offset:offset + block_words]
            ])
    return chunks
