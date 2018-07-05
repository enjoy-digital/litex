import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStatus, CSRStorage


class VexRiscv(Module, AutoCSR):
    def __init__(self, platform, cpu_reset_address, variant=None):
        assert variant in (None, "debug"), "Unsupported variant %s" % variant
        self.ibus = i = wishbone.Interface()
        self.dbus = d = wishbone.Interface()

        self.interrupt = Signal(32)

        # Output reset signal -- set to 1 when CPU reset is asserted
        self.debug_reset = Signal()

        if variant == None:
            cpu_reset = ResetSignal()
            cpu_args = {}
            cpu_filename = "VexRiscv.v"
        elif variant == "debug":
            cpu_reset = Signal()
            cpu_args = {}
            cpu_filename = "VexRiscv-Debug.v"
            # Create four debug registers:
            #   DEBUG_CORE:    The contents of the debug core register
            #   DEBUG_DATA:    Write an instruction into the pipeline, or read the result.
            #   DEBUG_REFRESH: Write 0x00 or 0x04 here to update either CORE or DATA
            #   DEBUG_COUNT:   An incrementing value that can be used to detect packet loss.
            #                  Updated on a successful WRITE to CORE, DATA, or REFRESH.
            self.debug_core = debug_core = CSRStorage(32, name="debug_core", write_from_dev=True)
            self.debug_data = debug_data = CSRStorage(32, name="debug_data", write_from_dev=True)
            self.debug_refresh = debug_refresh = CSRStorage(8, name="debug_refresh")
            self.debug_counter = debug_counter = CSRStatus(32, name="debug_counter")

            # # #

            debug_bus_cmd_payload_wr = Signal()
            debug_bus_cmd_payload_address = Signal(8)
            debug_bus_cmd_payload_data = Signal(32)
            debug_bus_cmd_ready = Signal()
            debug_bus_rsp_data = Signal(32)
            debug_start_cmd = Signal()
            debug_update_pending = Signal()
            debug_write_pending = Signal()
            debug_reset_out = Signal()
            debug_reset_counter = Signal(16)

            # A bit to indicate whether we're REFRESHing the CORE or DATA register
            refreshing_data = Signal()

            self.sync += [
                # If the core asserts reset_out, set debug_reset for 2**16 cycles.
                If(debug_reset_out,
                    debug_reset_counter.eq(0),
                    self.debug_reset.eq(1)
                ).Elif(debug_reset_counter != (2**16-1),
                    debug_reset_counter.eq(debug_reset_counter + 1)
                ).Else(
                    self.debug_reset.eq(0)
                ),

                # Reset the CPU if debug_reset is asserted and none of the
                # Wishbone buses are in use
                cpu_reset.eq((~i.cyc & ~d.cyc & ~d.stb & ~i.stb &
                             self.debug_reset) | ResetSignal()),

                # If there's a Wishbone write on the CORE register, write to
                # debug register address 0.
                If(debug_core.re,
                    debug_bus_cmd_payload_address.eq(0x00),
                    debug_bus_cmd_payload_data.eq(debug_core.storage),

                    debug_bus_cmd_payload_wr.eq(1),
                    debug_start_cmd.eq(1),
                    debug_write_pending.eq(1),

                    debug_core.we.eq(0),
                    debug_data.we.eq(0)
                # Or, if there's a write to the DATA register, write to
                # debug register address 4.
                ).Elif(debug_data.re,
                    debug_bus_cmd_payload_address.eq(0x04),
                    debug_bus_cmd_payload_data.eq(debug_data.storage),

                    debug_bus_cmd_payload_wr.eq(1),
                    debug_start_cmd.eq(1),
                    debug_write_pending.eq(1),

                    debug_core.we.eq(0),
                    debug_data.we.eq(0)
                # A write to the REFRESH register indicates which register
                # (DATA or CORE) we want to update from the CPU.
                ).Elif(debug_refresh.re,
                    If(~debug_refresh.storage,
                        refreshing_data.eq(0),
                        debug_bus_cmd_payload_address.eq(0)
                    ).Else(
                        refreshing_data.eq(1),
                        debug_bus_cmd_payload_address.eq(4)
                    ),
                    # Data can be anything, since it's a "read"
                    debug_bus_cmd_payload_data.eq(0),

                    # Start a "Read" command with the "Write" bit set to 0
                    debug_bus_cmd_payload_wr.eq(0),
                    debug_start_cmd.eq(1),

                    # The data will be ready when debug_bus_cmd_ready == 1,
                    # so set the pending bit to look for it on future cycles.
                    debug_update_pending.eq(1),

                    debug_core.we.eq(0),
                    debug_data.we.eq(0)
                # If the pending bit is set, check to see if the cmd_ready
                # bit from the debug bus is 1, indicating the CPU has finished
                # its operation and is in the idle state.
                ).Elif(debug_update_pending,
                    If(debug_bus_cmd_ready,
                        debug_bus_cmd_payload_wr.eq(0),
                        debug_update_pending.eq(0),
                        debug_write_pending.eq(0),
                        debug_start_cmd.eq(0),
                        debug_counter.status.eq(debug_counter.status + 1),
                        # Depending on whether we were asked to update the CORE
                        # or DATA register, copy the response data to the correct CSR.
                        If(~refreshing_data,
                            debug_core.dat_w.eq(debug_bus_rsp_data),
                            debug_core.we.eq(1),
                            debug_data.we.eq(0)
                        ).Else(
                            debug_data.dat_w.eq(debug_bus_rsp_data),
                            debug_core.we.eq(0),
                            debug_data.we.eq(1)
                        )
                    )
                # If there's a pending write to CORE or DATA, increment the
                # packet counter once the operation has finished.
                ).Elif(debug_write_pending,
                    If(debug_bus_cmd_ready,
                        # When debug_bus_cmd_ready goes 1,
                        debug_counter.status.eq(debug_counter.status + 1),
                        debug_update_pending.eq(0),
                        debug_write_pending.eq(0),
                        debug_start_cmd.eq(0),
                        debug_data.we.eq(0),
                        debug_core.we.eq(0)
                    )
                # Otherwise, ensure the Write Enable bits on the registers
                # are 0, so we're not constantly loading floating values.
                ).Else(
                    debug_core.we.eq(0),
                    debug_data.we.eq(0)
                )
            ]

            cpu_args.update({
                "i_debugReset": ResetSignal(),
                "i_debug_bus_cmd_valid": debug_start_cmd,
                "i_debug_bus_cmd_payload_wr": debug_bus_cmd_payload_wr,
                "i_debug_bus_cmd_payload_address": debug_bus_cmd_payload_address,
                "i_debug_bus_cmd_payload_data": debug_bus_cmd_payload_data,
                "o_debug_bus_cmd_ready": debug_bus_cmd_ready,
                "o_debug_bus_rsp_data": debug_bus_rsp_data,
                "o_debug_resetOut": debug_reset_out
            })

        self.specials += Instance("VexRiscv",
                **cpu_args,

                i_clk=ClockSignal(),
                i_reset=cpu_reset,

                i_externalResetVector=cpu_reset_address,
                i_externalInterruptArray=self.interrupt,
                i_timerInterrupt=0,

                o_iBusWishbone_ADR=i.adr,
                o_iBusWishbone_DAT_MOSI=i.dat_w,
                o_iBusWishbone_SEL=i.sel,
                o_iBusWishbone_CYC=i.cyc,
                o_iBusWishbone_STB=i.stb,
                o_iBusWishbone_WE=i.we,
                o_iBusWishbone_CTI=i.cti,
                o_iBusWishbone_BTE=i.bte,
                i_iBusWishbone_DAT_MISO=i.dat_r,
                i_iBusWishbone_ACK=i.ack,
                i_iBusWishbone_ERR=i.err,

                o_dBusWishbone_ADR=d.adr,
                o_dBusWishbone_DAT_MOSI=d.dat_w,
                o_dBusWishbone_SEL=d.sel,
                o_dBusWishbone_CYC=d.cyc,
                o_dBusWishbone_STB=d.stb,
                o_dBusWishbone_WE=d.we,
                o_dBusWishbone_CTI=d.cti,
                o_dBusWishbone_BTE=d.bte,
                i_dBusWishbone_DAT_MISO=d.dat_r,
                i_dBusWishbone_ACK=d.ack,
                i_dBusWishbone_ERR=d.err)

        # add verilog sources
        self.add_sources(platform, cpu_filename)

    @staticmethod
    def add_sources(platform, cpu_filename):
        vdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_sources(os.path.join(vdir), cpu_filename)
        platform.add_verilog_include_path(vdir)
