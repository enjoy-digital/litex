#
# This file is part of LiteX.
#
# Copyright (c) 2025 LiteX Contributors
# SPDX-License-Identifier: BSD-2-Clause

"""
RISC-V Core Local Interruptor (CLINT) implementation

Implements CLINT as per RISC-V ACLINT specification providing:
- Machine Timer (MTIMER) functionality
- Machine Software Interrupts (MSWI)
"""

from migen import *

from litex.gen import *

from litex.soc.interconnect.csr import *
from litex.soc.integration.doc import ModuleDoc

# CLINT --------------------------------------------------------------------------------------------

class CLINT(LiteXModule):
    """RISC-V Core Local Interruptor

    Provides CLINT functionality as per RISC-V ACLINT specification including:
    - MTIME: 64-bit machine timer counter
    - MTIMECMP: Timer compare registers (one per HART)
    - MSIP: Software interrupt pending bits (one per HART)
    - Timer and software interrupt outputs for each HART
    """

    def __init__(self, num_harts=1):
        self.intro = ModuleDoc("""RISC-V Core Local Interruptor (CLINT)

        Implements the RISC-V Core Local Interruptor as per the ACLINT specification.

        The CLINT provides two main functions:

        1. **Machine Timer (MTIMER)**:
           - Single 64-bit MTIME counter shared by all HARTs
           - Per-HART MTIMECMP registers for timer comparison
           - Generates timer interrupts when MTIME >= MTIMECMP

        2. **Machine Software Interrupts (MSWI)**:
           - Per-HART MSIP bits for software-triggered interrupts
           - Allows inter-processor interrupts in multi-HART systems

        Memory Map (relative to CLINT base address):
        - 0x0000-0x3FF8: MSIP registers (4 bytes per HART)
        - 0x4000-0x7FF8: MTIMECMP registers (8 bytes per HART)
        - 0xBFF8-0xBFFF: MTIME register (8 bytes)

        Interrupt outputs:
        - timer_interrupts: Timer interrupt signals (one per HART)
        - sw_interrupts: Software interrupt signals (one per HART)
        """)

        self.num_harts = num_harts

        # Interrupt outputs (one signal per HART)
        self.timer_interrupts = Signal(num_harts, name="timer_interrupts")
        self.sw_interrupts = Signal(num_harts, name="sw_interrupts")

        # MTIME - 64-bit counter (single instance shared by all HARTs)
        self._mtime_low = CSRStatus(32, name="mtime_low",
                                   description="Machine Timer lower 32 bits")
        self._mtime_high = CSRStatus(32, name="mtime_high",
                                    description="Machine Timer upper 32 bits")

        # Optional MTIME write access (for initialization)
        self._mtime_low_write = CSRStorage(32, name="mtime_low_write",
                                          description="Write access to MTIME lower 32 bits")
        self._mtime_high_write = CSRStorage(32, name="mtime_high_write",
                                           description="Write access to MTIME upper 32 bits")
        self._mtime_write_en = CSRStorage(1, name="mtime_write_en",
                                         description="Enable MTIME write (default: auto-increment)")

        # MTIMECMP - 64-bit compare registers (one per HART)
        self.mtimecmp_low = []
        self.mtimecmp_high = []
        for i in range(num_harts):
            # Initialize MTIMECMP to maximum value to prevent spurious timer interrupts
            mtimecmp_low = CSRStorage(32, name=f"mtimecmp{i}_low",
                                     description=f"MTIMECMP for HART{i} lower 32 bits",
                                     reset=0xFFFFFFFF)
            mtimecmp_high = CSRStorage(32, name=f"mtimecmp{i}_high",
                                      description=f"MTIMECMP for HART{i} upper 32 bits",
                                      reset=0xFFFFFFFF)
            setattr(self, f"_mtimecmp{i}_low", mtimecmp_low)
            setattr(self, f"_mtimecmp{i}_high", mtimecmp_high)
            self.mtimecmp_low.append(mtimecmp_low)
            self.mtimecmp_high.append(mtimecmp_high)

        # MSIP - Machine Software Interrupt Pending (one bit per HART)
        self._msip = CSRStorage(num_harts, name="msip",
                               description="Machine Software Interrupt Pending bits")

        # Internal 64-bit MTIME counter
        mtime = Signal(64, name="mtime_counter")

        # MTIME counter logic
        self.sync += [
            If(self._mtime_write_en.storage,
                # Allow writing to MTIME when enabled
                mtime[:32].eq(self._mtime_low_write.storage),
                mtime[32:].eq(self._mtime_high_write.storage)
            ).Else(
                # Normal operation: increment MTIME
                mtime.eq(mtime + 1)
            )
        ]

        # Connect MTIME to status registers for reading
        self.comb += [
            self._mtime_low.status.eq(mtime[:32]),
            self._mtime_high.status.eq(mtime[32:])
        ]

        # Generate timer interrupts for each HART
        for i in range(num_harts):
            # Combine MTIMECMP high and low parts
            mtimecmp = Signal(64, name=f"mtimecmp{i}")
            self.comb += [
                mtimecmp[:32].eq(self.mtimecmp_low[i].storage),
                mtimecmp[32:].eq(self.mtimecmp_high[i].storage),
                # Timer interrupt when MTIME >= MTIMECMP
                self.timer_interrupts[i].eq(mtime >= mtimecmp)
            ]

        # Software interrupts - add register stage for better timing
        # Note: These signals need to be stable for CPU to sample them
        if num_harts == 1:
            # For single hart, add register stage to improve timing
            sw_interrupts_reg = Signal(num_harts, name="sw_interrupts_reg")
            self.sync += sw_interrupts_reg.eq(self._msip.storage)
            self.comb += self.sw_interrupts.eq(sw_interrupts_reg)
        else:
            # Multi-hart keeps direct connection for now
            self.comb += self.sw_interrupts.eq(self._msip.storage)

    def add_to_soc(self, soc, name="clint", base_addr=0x02000000):
        """Helper method to add CLINT to a SoC

        Args:
            soc: The SoC to add the CLINT to
            name: Name for the CLINT instance (default: "clint")
            base_addr: Base address for CLINT memory map (default: 0x02000000)
        """
        # Add CLINT as a submodule
        soc.submodules += self

        # Add to memory map
        soc.add_csr(name, base_addr)

        # Connect interrupts to CPUs if they have timer_interrupt inputs
        # This is just an example - actual connection depends on CPU implementation
        if hasattr(soc, "cpu") and hasattr(soc.cpu, "timer_interrupt"):
            soc.comb += soc.cpu.timer_interrupt.eq(self.timer_interrupts[0])