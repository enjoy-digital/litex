import os

from migen import *

from litex.soc.interconnect import wishbone
from litex.soc.interconnect.csr import AutoCSR, CSRStatus, CSRStorage


class VexRiscv(Module, AutoCSR):
    def __init__(self, platform, cpu_reset_address, cpu_debugging=False):
        self.ibus = i = wishbone.Interface()
        self.dbus = d = wishbone.Interface()

        self.interrupt = Signal(32)

        # Output reset signal -- set to 1 when CPU reset is asserted
        self.debug_reset = Signal()

        i_debug_bus_cmd_payload_wr = Signal()
        i_debug_bus_cmd_payload_address = Signal(8)
        i_debug_bus_cmd_payload_data = Signal(32)
        o_debug_bus_cmd_ready = Signal()
        o_debug_bus_rsp_data = Signal(32)
        debug_start_cmd = Signal()

        # If debugging is requested, create a bus that contains four registers:
        #   DEBUG_CORE: The contents of the debug core register
        #   DEBUG_DATA: Write an instruction into the pipeline, or read the result.
        #   DEBUG_REFRESH: Write 0x00 or 0x04 here to update either CORE or DATA
        #   DEBUG_COUNT: An incrementing value that can be used to detect packet loss.
        #               Updated on a successful WRITE to CORE, DATA, or REFRESH.
        if cpu_debugging:
            debug_update_pending = Signal()
            debug_write_pending = Signal()
            self.debug_core_reg = CSRStorage(
                32, name="debug_core", write_from_dev=True)
            self.debug_data_reg = CSRStorage(
                32, name="debug_data", write_from_dev=True)
            self.debug_refresh_reg = CSRStorage(8, name="debug_refresh")
            self.debug_packet_counter = CSRStatus(
                32, name="debug_counter")

            # OR the global reset together with the result of debug_resetOut.
            debug_resetOut = Signal()
            debug_resetCounter = Signal(16)
            i_reset = Signal()

            # A bit to indicate whether we're REFRESHing the CORE or DATA register
            refreshing_data = Signal()

            self.sync += [
                # If the core asserts resetOut, set debug_reset for 65535 cycles.
                If(debug_resetOut, debug_resetCounter.eq(
                    0), self.debug_reset.eq(1))
                .Elif(debug_resetCounter < 65534, debug_resetCounter.eq(debug_resetCounter + 1))
                .Else(self.debug_reset.eq(0)),

                # Reset the CPU if debug_reset is asserted and none of the
                # Wishbone buses are in use
                i_reset.eq((~i.cyc & ~d.cyc & ~d.stb & ~i.stb &
                            self.debug_reset) | ResetSignal()),

                # If there's a Wishbone write on the CORE register, write to
                # debug register address 0.
                If(self.debug_core_reg.re,
                    i_debug_bus_cmd_payload_address.eq(0x00),
                    i_debug_bus_cmd_payload_data.eq(self.debug_core_reg.storage),

                    i_debug_bus_cmd_payload_wr.eq(1),
                    debug_start_cmd.eq(1),
                    debug_write_pending.eq(1),

                    self.debug_core_reg.we.eq(0),
                    self.debug_data_reg.we.eq(0)
                # Or, if there's a write to the DATA register, write to
                # debug register address 4.
                ).Elif(self.debug_data_reg.re,
                    i_debug_bus_cmd_payload_address.eq(0x04),
                    i_debug_bus_cmd_payload_data.eq(self.debug_data_reg.storage),

                    i_debug_bus_cmd_payload_wr.eq(1),
                    debug_start_cmd.eq(1),
                    debug_write_pending.eq(1),

                    self.debug_core_reg.we.eq(0),
                    self.debug_data_reg.we.eq(0)
                # A write to the REFRESH register indicates which register
                # (DATA or CORE) we want to update from the CPU.
                ).Elif(self.debug_refresh_reg.re,
                    If(self.debug_refresh_reg.storage == 0,
                        refreshing_data.eq(0),
                        i_debug_bus_cmd_payload_address.eq(0)
                    ).Else(
                        refreshing_data.eq(1),
                        i_debug_bus_cmd_payload_address.eq(4)
                    ),
                    # Data can be anything, since it's a "read"
                    i_debug_bus_cmd_payload_data.eq(0),

                    # Start a "Read" command with the "Write" bit set to 0
                    i_debug_bus_cmd_payload_wr.eq(0),
                    debug_start_cmd.eq(1),

                    # The data will be ready when o_debug_bus_cmd_ready == 1,
                    # so set the pending bit to look for it on future cycles.
                    debug_update_pending.eq(1),

                    self.debug_core_reg.we.eq(0),
                    self.debug_data_reg.we.eq(0)
                # If the pending bit is set, check to see if the cmd_ready
                # bit from the debug bus is 1, indicating the CPU has finished
                # its operation and is in the idle state.
                ).Elif(debug_update_pending == 1,
                    If(o_debug_bus_cmd_ready == 1,
                        i_debug_bus_cmd_payload_wr.eq(0),
                        debug_update_pending.eq(0),
                        debug_write_pending.eq(0),
                        debug_start_cmd.eq(0),
                        self.debug_packet_counter.status.eq(
                            self.debug_packet_counter.status + 1),
                        # Depending on whether we were asked to update the CORE
                        # or DATA register, copy the response data to the correct CSR.
                        If(refreshing_data == 0,
                            self.debug_core_reg.dat_w.eq(o_debug_bus_rsp_data),
                            self.debug_core_reg.we.eq(1),
                            self.debug_data_reg.we.eq(0)
                        ).Else(
                            self.debug_data_reg.dat_w.eq(o_debug_bus_rsp_data),
                            self.debug_core_reg.we.eq(0),
                            self.debug_data_reg.we.eq(1)
                        )
                    )
                # If there's a pending write to CORE or DATA, increment the
                # packet counter once the operation has finished.
                ).Elif(debug_write_pending == 1,
                    If(o_debug_bus_cmd_ready == 1,
                        # When o_debug_bus_cmd_ready goes 1,
                        self.debug_packet_counter.status.eq(
                            self.debug_packet_counter.status + 1),
                        debug_update_pending.eq(0),
                        debug_write_pending.eq(0),
                        debug_start_cmd.eq(0),
                        self.debug_data_reg.we.eq(0),
                        self.debug_core_reg.we.eq(0)
                    )
                # Otherwise, ensure the Write Enable bits on the registers
                # are 0, so we're not constantly loading floating values.
                ).Else(
                    self.debug_core_reg.we.eq(0),
                    self.debug_data_reg.we.eq(0)
                )
            ]

            kwargs = {
                'i_debugReset': ResetSignal(),
                'i_debug_bus_cmd_valid': debug_start_cmd,
                'i_debug_bus_cmd_payload_wr': i_debug_bus_cmd_payload_wr,
                'i_debug_bus_cmd_payload_address': i_debug_bus_cmd_payload_address,
                'i_debug_bus_cmd_payload_data': i_debug_bus_cmd_payload_data,
                'o_debug_bus_cmd_ready': o_debug_bus_cmd_ready,
                'o_debug_bus_rsp_data': o_debug_bus_rsp_data,
                'o_debug_resetOut': debug_resetOut
            }
            source_file = "VexRiscv-Debug.v"
        else:
            kwargs = {}
            source_file = "VexRiscv.v"
            # Ordinarily this is a reset signal.  However, in debug mode,
            # this is ORed with the output of debug_resetOut as well.
            i_reset = ResetSignal()
            self.comb += self.debug_reset.eq(0)

        self.specials += Instance("VexRiscv",
                i_clk=ClockSignal(),
                i_reset=i_reset,

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
                i_dBusWishbone_ERR=d.err,
                **kwargs)

        # add verilog sources
        self.add_sources(platform, source_file)

    @staticmethod
    def add_sources(platform, source_file):
        vdir = os.path.join(os.path.abspath(os.path.dirname(__file__)), "verilog")
        platform.add_sources(os.path.join(vdir), source_file)
        platform.add_verilog_include_path(vdir)
