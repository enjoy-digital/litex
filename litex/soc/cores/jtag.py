#
# This file is part of LiteX.
#
# Copyright (c) 2019-2022 Florent Kermarrec <florent@enjoy-digital.fr>
# Copyright (c) 2019 Antti Lukats <antti.lukats@gmail.com>
# Copyright (c) 2017 Robert Jordens <jordens@gmail.com>
# Copyright (c) 2021 Gregory Davill <greg.davill@gmail.com>
# Copyright (c) 2021 Gabriel L. Somlo <somlo@cmu.edu>
# Copyright (c) 2021 Jevin Sweval <jevinsweval@gmail.com>
# SPDX-License-Identifier: BSD-2-Clause

from migen import *
from migen.genlib.cdc import AsyncResetSynchronizer, MultiReg

from litex.gen import *

from litex.build.generic_platform import *
from litex.soc.interconnect import stream

# JTAG TAP FSM -------------------------------------------------------------------------------------

class JTAGTAPFSM(LiteXModule):
    def __init__(self, tms):
        self.fsm = fsm = FSM(reset_state="TEST_LOGIC_RESET")

        def JTAGTAPFSMState(name, transitions={}):
            logic = []

            # Transitions logic.
            nextstates = {}
            nextstates[0] = NextState(transitions.get(0, name))
            nextstates[1] = NextState(transitions.get(1, name))
            logic.append(Case(tms, nextstates))

            # Ongoing logic.
            ongoing = Signal()
            setattr(self, name, ongoing)
            logic.append(ongoing.eq(1))

            # Add logic to state.
            fsm.act(name, *logic)

        # Test-Logic-Reset.
        # -----------------
        JTAGTAPFSMState(
            name        = "TEST_LOGIC_RESET",
            transitions = {
                0 : "RUN_TEST_IDLE",
            }
        )

        # Run-Test/Idle.
        # --------------
        JTAGTAPFSMState(
            name        = "RUN_TEST_IDLE",
            transitions = {
                1 : "SELECT_DR_SCAN",
            }
        )

        # DR-Scan.
        # --------
        JTAGTAPFSMState(
            name        = "SELECT_DR_SCAN",
            transitions = {
                0 : "CAPTURE_DR",
                1 : "SELECT_IR_SCAN",
            }
        )
        JTAGTAPFSMState(
            name        = "CAPTURE_DR",
            transitions = {
                0 : "SHIFT_DR",
                1 : "EXIT1_DR",
            }
        )
        JTAGTAPFSMState(
            name        = "SHIFT_DR",
            transitions = {
                1 : "EXIT1_DR",
            }
        )
        JTAGTAPFSMState(
            name        = "EXIT1_DR",
            transitions = {
                0 : "PAUSE_DR",
                1 : "UPDATE_DR",
            }
        )
        JTAGTAPFSMState(
            name        = "PAUSE_DR",
            transitions = {
                1 : "EXIT2_DR",
            }
        )
        JTAGTAPFSMState(
            name        = "EXIT2_DR",
            transitions = {
                0 : "SHIFT_DR",
                1 : "UPDATE_DR",
            }
        )
        JTAGTAPFSMState(
            name        = "UPDATE_DR",
            transitions = {
                0 : "RUN_TEST_IDLE",
                1 : "SELECT_DR_SCAN",
            }
        )

        # IR-Scan.
        # --------
        JTAGTAPFSMState(
            name        = "SELECT_IR_SCAN",
            transitions = {
                0 : "CAPTURE_IR",
                1 : "TEST_LOGIC_RESET",
            }
        )
        JTAGTAPFSMState(
            name        = "CAPTURE_IR",
            transitions = {
                0 : "SHIFT_IR",
                1 : "EXIT1_IR",
            }
        )
        JTAGTAPFSMState(
            name        = "SHIFT_IR",
            transitions = {
                1 : "EXIT1_IR",
            }
        )
        JTAGTAPFSMState(
            name        = "EXIT1_IR",
            transitions = {
                0 : "PAUSE_IR",
                1 : "UPDATE_IR",
            }
        )
        JTAGTAPFSMState(
            name        = "PAUSE_IR",
            transitions = {
                1 : "EXIT2_IR",
            }
        )
        JTAGTAPFSMState(
            name        = "EXIT2_IR",
            transitions = {
                0 : "SHIFT_IR",
                1 : "UPDATE_IR",
            }
        )
        JTAGTAPFSMState(
            name        = "UPDATE_IR",
            transitions = {
                0 : "RUN_TEST_IDLE",
                1 : "SELECT_DR_SCAN",
            }
        )

# Altera JTAG --------------------------------------------------------------------------------------

class AlteraJTAG(LiteXModule):
    def __init__(self, primitive, pads):
        # Common with Xilinx.
        self.reset   = reset   = Signal() # Provided by our own TAP FSM.
        self.capture = capture = Signal() # Provided by our own TAP FSM.
        self.shift   = shift   = Signal()
        self.update  = update  = Signal()
        # Unique to Altera.
        self.runtest = runtest = Signal()
        self.drck    = drck    = Signal()
        self.sel     = sel     = Signal()

        self.tck = tck = Signal()
        self.tms = tms = Signal()
        self.tdi = tdi = Signal()
        self.tdo = tdo = Signal()

        # Magic reserved signals that have to be routed to the top module.
        self.altera_reserved_tck = rtck = Signal()
        self.altera_reserved_tms = rtms = Signal()
        self.altera_reserved_tdi = rtdi = Signal()
        self.altera_reserved_tdo = rtdo = Signal()

        # Inputs.
        self.tdouser = tdouser = Signal()

        # Outputs.
        self.tmsutap = tmsutap = Signal()
        self.tckutap = tckutap = Signal()
        self.tdiutap = tdiutap = Signal()

        # # #

        # Create falling-edge JTAG clock domain for TAP FSM.
        self.cd_jtag_inv = cd_jtag_inv = ClockDomain("jtag_inv")
        self.comb += ClockSignal("jtag_inv").eq(~ClockSignal("jtag"))
        self.comb += ResetSignal("jtag_inv").eq(ResetSignal("jtag"))

        # Connect the TAP state signals that LiteX expects but the HW IP doesn't provide.
        self.tap_fsm = ClockDomainsRenamer("jtag")(JTAGTAPFSM(tms))
        self.sync.jtag_inv += reset.eq(self.tap_fsm.TEST_LOGIC_RESET)
        self.sync.jtag_inv += capture.eq(self.tap_fsm.CAPTURE_DR)

        self.specials += Instance(primitive,
            # HW TAP FSM states.
            o_shiftuser   = shift,
            o_updateuser  = update,
            o_runidleuser = runtest,
            o_clkdruser   = drck,
            o_usr1user    = sel,
            # JTAG TAP IO.
            i_tdouser     = tdouser,
            o_tmsutap     = tmsutap,
            o_tckutap     = tckutap,
            o_tdiutap     = tdiutap,
            # Reserved pins.
            i_tms         = rtms,
            i_tck         = rtck,
            i_tdi         = rtdi,
            o_tdo         = rtdo,
        )

        # connect magical reserved signals to top level pads
        self.comb += [
            rtms.eq(pads["altera_reserved_tms"]),
            rtck.eq(pads["altera_reserved_tck"]),
            rtdi.eq(pads["altera_reserved_tdi"]),
            pads["altera_reserved_tdo"].eq(rtdo),
        ]

        # Connect TAP IO.
        self.comb += [
            tck.eq(tckutap),
            tms.eq(tmsutap),
            tdi.eq(tdiutap),
        ]
        self.sync.jtag_inv += tdouser.eq(tdo)

    @staticmethod
    def get_primitive(device):
        # TODO: Add support for Stratix 10, Arria 10 SoC and Agilex devices.
        prim_dict = {
            # Primitive Name                Ðevice (startswith)
            "arriaii_jtag"                : ["ep2a"],
            "arriaiigz_jtag"              : ["ep2agz"],
            "arriav_jtag"                 : ["5a"],
            "arriavgz_jtag"               : ["5agz"],
            "cyclone_jtag"                : ["ep1c"],
            "cyclone10lp_jtag"            : ["10cl"],
            "cycloneii_jtag"              : ["ep2c"],
            "cycloneiii_jtag"             : ["ep3c"],
            "cycloneiiils_jtag"           : ["ep3cls"],
            "cycloneiv_jtag"              : ["ep4cgx"],
            "cycloneive_jtag"             : ["ep4ce"],
            "cyclonev_jtag"               : ["5c"],
            "fiftyfivenm_jtag"            : ["10m"], # MAX 10 series
            "maxii_jtag"                  : ["epm1", "epm2", "epm5"],
            "maxv_jtag"                   : ["5m"],
            "stratix_jtag"                : ["ep1s"],
            "stratixgx_jtag"              : ["ep1sgx"],
            "stratixii_jtag"              : ["ep2s"],
            "stratixiigx_jtag"            : ["ep2sgx"],
            "stratixiii_jtag"             : ["ep3s"],
            "stratixiv_jtag"              : ["ep4s"],
            "stratixv_jtag"               : ["5s"],
            "twentynm_jtagblock"          : [], # Arria 10 series
            "twentynm_jtag"               : ["10a"],
            "twentynm_hps_interface_jtag" : [],
        }

        matching_prims = {}

        for prim, prim_devs in prim_dict.items():
            for prim_dev in prim_devs:
                if device.lower().startswith(prim_dev):
                    matching_prims[prim_dev] = prim

        # get the closest match
        best_device = ""

        for dev, prim in matching_prims.items():
            if len(dev) > len(best_device):
                best_device = dev

        return matching_prims.get(best_device)

# Xilinx JTAG --------------------------------------------------------------------------------------

class XilinxJTAG(LiteXModule):
    def __init__(self, primitive, chain=1):
        self.reset   = Signal()
        self.capture = Signal()
        self.shift   = Signal()
        self.update  = Signal()

        self.tck = Signal()
        self.tms = Signal()
        self.tdi = Signal()
        self.tdo = Signal()

        # # #

        self.specials += Instance(primitive,
            p_JTAG_CHAIN = chain,

            o_RESET   = self.reset,
            o_CAPTURE = self.capture,
            o_SHIFT   = self.shift,
            o_UPDATE  = self.update,

            o_TCK = self.tck,
            o_TMS = self.tms,
            o_TDI = self.tdi,
            i_TDO = self.tdo,
        )

    @staticmethod
    def get_primitive(device):
        prim_dict = {
            # Primitive Name   Ðevice (startswith)
            "BSCAN_SPARTAN6" : ["xc6"],
            "BSCANE2"        : ["xc7a", "xc7k", "xc7v", "xc7z"] +  ["xcau", "xcku", "xcvu", "xczu"],
        }
        for prim, prim_devs in prim_dict.items():
            for prim_dev in prim_devs:
                if device.lower().startswith(prim_dev):
                    return prim
        return None

    @staticmethod
    def get_tdi_delay(device):
        # Input delay if 1 TCK on TDI on Zynq/ZynqMPSoC devices.
        delay_dict = {"xc7z" : 1, "xczu" : 1}
        for dev, delay in delay_dict.items():
            if device.lower().startswith(dev):
                return 1
        return 0

# ECP5 JTAG ----------------------------------------------------------------------------------------

class ECP5JTAG(LiteXModule):
    def __init__(self, tck_delay_luts=8):
        self.reset   = Signal()
        self.capture = Signal()
        self.shift   = Signal()
        self.update  = Signal()

        self.tck = Signal()
        self.tdi = Signal()
        self.tdo = Signal()

        # # #

        rst_n  = Signal()
        tck    = Signal()
        jce1   = Signal()
        jce1_d = Signal()

        self.sync.jtag += jce1_d.eq(jce1)
        self.comb += self.capture.eq(jce1 & ~jce1_d) # First cycle jce1 is high we're in Capture-DR.
        self.comb += self.reset.eq(~rst_n)

        self.specials += Instance("JTAGG",
            o_JRSTN   = rst_n,
            o_JSHIFT  = self.shift,
            o_JUPDATE = self.update,

            o_JTCK  = tck,
            o_JTDI  = self.tdi, # JTDI = FF(posedge TCK, TDI)
            o_JCE1  = jce1,     # (FSM==Capture-DR || Shift-DR) & (IR==0x32)
            i_JTDO1 = self.tdo, # FF(negedge TCK, JTDO1) if (IR==0x32 && FSM==Shift-DR)
        )

        # TDI/TCK are synchronous on JTAGG output (TDI being registered with TCK). Introduce a delay
        # on TCK with multiple LUT4s to allow its use as the JTAG Clk.
        for i in range(tck_delay_luts):
            new_tck = Signal()
            self.specials += Instance("LUT4",
                attr   = {"keep"},
                p_INIT = 2,
                i_A = tck,
                i_B = 0,
                i_C = 0,
                i_D = 0,
                o_Z = new_tck
            )
            tck = new_tck
        self.comb += self.tck.eq(tck)

# JTAG PHY -----------------------------------------------------------------------------------------

class JTAGPHY(LiteXModule):
    def __init__(self, jtag=None, device=None, data_width=8, clock_domain="sys", chain=1, platform=None):
        """JTAG PHY

        Provides a simple JTAG to LiteX stream module to easily stream data to/from the FPGA
        over JTAG.

        Wire format: data_width + 2 bits, LSB first.

        Host to Target:
          - TX ready : bit 0
          - RX data: : bit 1 to data_width
          - RX valid : bit data_width + 1

        Target to Host:
          - RX ready : bit 0
          - TX data  : bit 1 to data_width
          - TX valid : bit data_width + 1
        """
        self.sink   =   sink = stream.Endpoint([("data", data_width)])
        self.source = source = stream.Endpoint([("data", data_width)])

        # # #


        # JTAG TAP ---------------------------------------------------------------------------------
        if jtag is None:
            jtag_tdi_delay = 0
            # Xilinx.
            if XilinxJTAG.get_primitive(device) is not None:
                jtag = XilinxJTAG(primitive=XilinxJTAG.get_primitive(device), chain=chain)
                jtag_tdi_delay = XilinxJTAG.get_tdi_delay(device)
            # Lattice.
            elif device[:5] == "LFE5U":
                jtag = ECP5JTAG()
            # Altera/Intel.
            elif AlteraJTAG.get_primitive(device) is not None:
                platform.add_reserved_jtag_decls()
                jtag = AlteraJTAG(
                    primitive = AlteraJTAG.get_primitive(device),
                    pads      = platform.get_reserved_jtag_pads()
                )
            else:
                print(device)
                raise NotImplementedError
            self.jtag = jtag

        # JTAG clock domain ------------------------------------------------------------------------
        self.cd_jtag = ClockDomain()
        self.comb += ClockSignal("jtag").eq(jtag.tck)
        self.specials += AsyncResetSynchronizer(self.cd_jtag, ResetSignal(clock_domain))

        # JTAG clock domain crossing ---------------------------------------------------------------
        if clock_domain != "jtag":
            tx_cdc = stream.AsyncFIFO([("data", data_width)], 4)
            tx_cdc = ClockDomainsRenamer({"write": clock_domain, "read": "jtag"})(tx_cdc)
            rx_cdc = stream.AsyncFIFO([("data", data_width)], 4)
            rx_cdc = ClockDomainsRenamer({"write": "jtag", "read": clock_domain})(rx_cdc)
            self.tx_cdc = tx_cdc
            self.rx_cdc = rx_cdc
            self.comb += [
                sink.connect(tx_cdc.sink),
                rx_cdc.source.connect(source)
            ]
            sink, source = tx_cdc.source, rx_cdc.sink

        # JTAG TDI/TDO Delay -----------------------------------------------------------------------
        jtag_tdi = jtag.tdi
        jtag_tdo = jtag.tdo
        if jtag_tdi_delay:
            jtag_tdi_sr = Signal(data_width + 2 - jtag_tdi_delay)
            self.sync.jtag += If(jtag.shift, jtag_tdi_sr.eq(Cat(jtag.tdi, jtag_tdi_sr)))
            jtag_tdi = jtag_tdi_sr[-1]

        # JTAG Xfer FSM ----------------------------------------------------------------------------
        valid = Signal()
        ready = Signal()
        data  = Signal(data_width)
        count = Signal(max=data_width)

        fsm = FSM(reset_state="XFER-READY")
        fsm = ClockDomainsRenamer("jtag")(fsm)
        fsm = ResetInserter()(fsm)
        self.submodules += fsm
        self.comb += fsm.reset.eq(jtag.reset | jtag.capture)
        fsm.act("XFER-READY",
            jtag_tdo.eq(ready),
            If(jtag.shift,
                sink.ready.eq(jtag_tdi),
                NextValue(valid, sink.valid),
                NextValue(data,  sink.data),
                NextValue(count, 0),
                NextState("XFER-DATA")
            )
        )
        fsm.act("XFER-DATA",
            jtag_tdo.eq(data),
            If(jtag.shift,
                NextValue(count, count + 1),
                NextValue(data, Cat(data[1:], jtag_tdi)),
                If(count == (data_width - 1),
                    NextState("XFER-VALID")
                )
            )
        )
        fsm.act("XFER-VALID",
            jtag_tdo.eq(valid),
            If(jtag.shift,
                source.valid.eq(jtag_tdi),
                source.data.eq(data),
                NextValue(ready, source.ready),
                NextState("XFER-READY")
            )
        )

# Efinix / TRION -----------------------------------------------------------------------------------

class EfinixJTAG(LiteXModule):
    # id refer to the JTAG_USER{id}
    def __init__(self, platform, id=1):
        self.name     = f"jtag_{id}"
        self.platform = platform
        self.id       = id

        _io = [
            (self.name, 0,
                Subsignal("CAPTURE", Pins(1)),
                Subsignal("DRCK",    Pins(1)),
                Subsignal("RESET",   Pins(1)),
                Subsignal("RUNTEST", Pins(1)),
                Subsignal("SEL",     Pins(1)),
                Subsignal("SHIFT",   Pins(1)),
                Subsignal("TCK",     Pins(1)),
                Subsignal("TDI",     Pins(1)),
                Subsignal("TMS",     Pins(1)),
                Subsignal("UPDATE",  Pins(1)),
                Subsignal("TDO",     Pins(1)),
            ),
        ]
        platform.add_extension(_io)

        self.pins = pins = platform.request(self.name)
        for pin in pins.flatten():
            self.platform.toolchain.excluded_ios.append(pin.backtrace[-1][0])

        block = {}
        block["type"] = "JTAG"
        block["name"] = self.name
        block["id"]   = self.id
        block["pins"] = pins
        self.platform.toolchain.ifacewriter.blocks.append(block)

    def bind_vexriscv_smp(self, cpu):
        self.comb += [
            # JTAG -> CPU.
            cpu.jtag_clk.eq(     self.pins.TCK),
            cpu.jtag_enable.eq(  self.pins.SEL),
            cpu.jtag_capture.eq( self.pins.CAPTURE),
            cpu.jtag_shift.eq(   self.pins.SHIFT),
            cpu.jtag_update.eq(  self.pins.UPDATE),
            cpu.jtag_reset.eq(   self.pins.RESET),
            cpu.jtag_tdi.eq(     self.pins.TDI),

            # CPU -> JTAG.
            self.pins.TDO.eq(cpu.jtag_tdo),
        ]
