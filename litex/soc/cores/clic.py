#
# This file is part of LiteX.
#
# Copyright (c) 2025 LiteX Contributors
# SPDX-License-Identifier: BSD-2-Clause

"""
Simplified RISC-V Core Local Interrupt Controller (CLIC) implementation
with software interrupt trigger support for testing
"""

from migen import *
from litex.gen import *
from litex.soc.interconnect.csr import *

class CLIC(LiteXModule, AutoCSR):
    """Simplified CLIC implementation with software trigger support"""
    
    def __init__(self, num_interrupts=64, num_harts=1, ipriolen=8):
        self.num_interrupts = num_interrupts
        self.num_harts = num_harts
        self.ipriolen = ipriolen

        # External interrupt inputs
        self.interrupt_inputs = Signal(num_interrupts, name="interrupt_inputs")

        # Interrupt outputs to CPU (per HART) - VexRiscv compatible names
        self.clicInterrupt = Signal(num_harts, name="clicInterrupt")
        self.clicInterruptId = Array([Signal(12, name=f"clicInterruptId_hart{i}")
                                     for i in range(num_harts)])
        self.clicInterruptPriority = Array([Signal(8, name=f"clicInterruptPriority_hart{i}")
                                           for i in range(num_harts)])
        
        # Interrupt acknowledge inputs from CPU (per HART)
        self.clicClaim = Signal(num_harts, name="clicClaim")
        self.clicThreshold = Array([Signal(8, name=f"clicThreshold_hart{i}")
                                   for i in range(num_harts)])

        # Per-interrupt configuration registers
        self.clicintattr = Array([Signal(8, name=f"clicintattr_{i}")
                                 for i in range(num_interrupts)])
        self.cliciprio = Array([Signal(8, name=f"cliciprio_{i}")
                               for i in range(num_interrupts)])
        self.clicintip = Array([Signal(name=f"clicintip_{i}")
                               for i in range(num_interrupts)])
        self.clicintie = Array([Signal(name=f"clicintie_{i}")
                               for i in range(num_interrupts)])

        # Track number of CSR-controlled interrupts
        self.num_csr_interrupts = min(16, num_interrupts)

        # Internal signals
        interrupt_pending = Array([Signal(name=f"int_pending_{i}")
                                  for i in range(num_interrupts)])
        interrupt_enabled = Array([Signal(name=f"int_enabled_{i}")
                                  for i in range(num_interrupts)])
        interrupt_active = Array([Signal(name=f"int_active_{i}")
                                 for i in range(num_interrupts)])

        # Process interrupt inputs based on attributes
        for i in range(num_interrupts):
            # Extract trigger type from attributes
            trig_type = Signal(2)
            self.comb += trig_type.eq(self.clicintattr[i][:2])

            # For CSR-controlled interrupts, pending bits are directly controlled
            if i < self.num_csr_interrupts:
                # CSR controls pending bit directly - no hardware trigger logic
                pass
            else:
                # Non-CSR interrupts follow hardware inputs
                edge_detect = Signal()
                prev_input = Signal()
                
                self.sync += prev_input.eq(self.interrupt_inputs[i])
                
                # Edge detection logic
                self.comb += [
                    If(trig_type[0],  # Edge triggered
                        If(trig_type[1],  # Negative edge
                            edge_detect.eq(prev_input & ~self.interrupt_inputs[i])
                        ).Else(  # Positive edge
                            edge_detect.eq(~prev_input & self.interrupt_inputs[i])
                        )
                    )
                ]
                
                # Update pending bits based on trigger type
                self.sync += [
                    If(trig_type[0],  # Edge triggered
                        If(edge_detect,
                            self.clicintip[i].eq(1)
                        )
                    ).Else(  # Level triggered
                        If(trig_type[1],  # Negative level
                            self.clicintip[i].eq(~self.interrupt_inputs[i])
                        ).Else(  # Positive level
                            self.clicintip[i].eq(self.interrupt_inputs[i])
                        )
                    )
                ]

            # Determine if interrupt is active
            self.comb += [
                interrupt_pending[i].eq(self.clicintip[i]),
                interrupt_enabled[i].eq(self.clicintie[i]),
                interrupt_active[i].eq(interrupt_pending[i] & interrupt_enabled[i])
            ]

        # Priority arbitration logic (per HART)
        for hart in range(num_harts):
            # Find highest priority active interrupt
            highest_priority = Signal(ipriolen, reset=2**ipriolen - 1)
            highest_id = Signal(max=num_interrupts)
            active_interrupt = Signal()

            # Priority comparison logic
            # Lower priority number = higher priority
            for i in range(num_interrupts):
                prio = Signal(ipriolen)
                self.comb += prio.eq(self.cliciprio[i][:ipriolen])

                self.comb += [
                    # Check if this interrupt should preempt
                    If(interrupt_active[i] & (prio < highest_priority),
                        highest_priority.eq(prio),
                        highest_id.eq(i),
                        active_interrupt.eq(1)
                    )
                ]

            # Output highest priority interrupt
            self.comb += [
                self.clicInterrupt[hart].eq(active_interrupt),
                self.clicInterruptId[hart].eq(highest_id),
                self.clicInterruptPriority[hart].eq(highest_priority)
            ]

    def add_csr_interface(self, soc, base_addr=None):
        """Add CSR interface for CLIC configuration registers"""
        # For first few interrupts, create CSR interface
        for i in range(self.num_csr_interrupts):
            # Interrupt enable
            ie = CSRStorage(1, name=f"clicintie{i}",
                           description=f"Interrupt {i} enable")
            setattr(self, f"_clicintie{i}", ie)
            self.comb += self.clicintie[i].eq(ie.storage)

            # Interrupt pending - use CSRStorage for software control
            ip = CSRStorage(1, name=f"clicintip{i}",
                           description=f"Interrupt {i} pending")
            setattr(self, f"_clicintip{i}", ip)
            # For CSR interrupts, pending bit is directly controlled by storage
            self.comb += self.clicintip[i].eq(ip.storage)

            # Interrupt priority
            iprio = CSRStorage(8, name=f"cliciprio{i}",
                              description=f"Interrupt {i} priority")
            setattr(self, f"_cliciprio{i}", iprio)
            self.comb += self.cliciprio[i].eq(iprio.storage)

            # Interrupt attributes
            iattr = CSRStorage(8, name=f"clicintattr{i}",
                              description=f"Interrupt {i} attributes")
            setattr(self, f"_clicintattr{i}", iattr)
            self.comb += self.clicintattr[i].eq(iattr.storage)

    def add_to_soc(self, soc, name="clic", base_addr=None):
        """Helper method to add CLIC to a SoC"""
        # First add CSR interface to create the CSR attributes
        self.add_csr_interface(soc, base_addr)
        
        # Note: The SoC's add_clic method already calls add_module, 
        # so we don't need to do it here

        # Connect to CPU if it has CLIC support
        if hasattr(soc, "cpu"):
            if hasattr(soc.cpu, "clic_interrupt"):
                soc.comb += soc.cpu.clic_interrupt.eq(self.clicInterrupt[0])
            if hasattr(soc.cpu, "clic_interrupt_id"):
                soc.comb += soc.cpu.clic_interrupt_id.eq(self.clicInterruptId[0])
            if hasattr(soc.cpu, "clic_interrupt_priority"):
                soc.comb += soc.cpu.clic_interrupt_priority.eq(self.clicInterruptPriority[0])
            # Connect CPU outputs to CLIC inputs
            if hasattr(soc.cpu, "clic_claim"):
                soc.comb += self.clicClaim[0].eq(soc.cpu.clic_claim)
            if hasattr(soc.cpu, "clic_threshold"):
                soc.comb += self.clicThreshold[0].eq(soc.cpu.clic_threshold)