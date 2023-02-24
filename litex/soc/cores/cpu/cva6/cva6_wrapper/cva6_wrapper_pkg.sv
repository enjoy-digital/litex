// Copyright 2018 ETH Zurich and University of Bologna.
// Copyright and related rights are licensed under the Solderpad Hardware
// License, Version 0.51 (the "License"); you may not use this file except in
// compliance with the License.  You may obtain a copy of the License at
// http://solderpad.org/licenses/SHL-0.51. Unless required by applicable law
// or agreed to in writing, software, hardware and materials distributed under
// this License is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
// CONDITIONS OF ANY KIND, either express or implied. See the License for the
// specific language governing permissions and limitations under the License.

package cva6_wrapper_pkg;
  // M-Mode Hart, S-Mode Hart
  localparam int unsigned NumTargets = 2;
  // Uart, SPI, Ethernet, reserved
  localparam int unsigned NumSources = 32;
  localparam int unsigned MaxPriority = 7;

  // 24 MByte in 8 byte words
  localparam NBSlave = 2; // debug, cva6
  localparam NBMaster = 4; // debug, plic, clint, external
  localparam AxiAddrWidth = 64;
  localparam AxiDataWidth = 64;
  localparam AxiIdWidthMaster = $clog2(NBMaster);
  localparam AxiIdWidthSlaves = AxiIdWidthMaster + $clog2(NBSlave);
  localparam AxiUserWidth = 1;

  typedef enum int unsigned {
    External = 0,
    PLIC     = 1,
    CLINT    = 2,
    Debug    = 3
  } axi_slaves_t;

  localparam logic[63:0] DebugLength    = 64'h1000;
  localparam logic[63:0] CLINTLength    = 64'hC0000;
  localparam logic[63:0] PLICLength     = 64'h3FF_FFFF;
  localparam logic[63:0] ExternalLength = 64'hEFFF_FFFF;

  // Instantiate AXI protocol checkers
  localparam bit GenProtocolChecker = 1'b0;

  typedef enum logic [63:0] {
    DebugBase    = 64'h0000_0000,
    CLINTBase    = 64'h0200_0000,
    PLICBase     = 64'h0C00_0000,
    ExternalBase = 64'h1000_0000
  } soc_bus_start_t;

  localparam NrRegion = 1;

  localparam ariane_pkg::ariane_cfg_t CVA6Cfg = '{
    RASDepth: 2,
    BTBEntries: 32,
    BHTEntries: 128,
    // idempotent region
    NrNonIdempotentRules:  1,
    NonIdempotentAddrBase: {64'b0},
    NonIdempotentLength:   {ExternalBase},
    NrExecuteRegionRules:  2,
    ExecuteRegionAddrBase: {DebugBase, ExternalBase},
    ExecuteRegionLength:   {DebugLength, ExternalLength},
    // cached region
    NrCachedRegionRules:    1,
    CachedRegionAddrBase:  {ExternalBase},
    CachedRegionLength:    {64'h7000_0000},
    //  cache config
    AxiCompliant:      1'b1,
    SwapEndianess:          1'b0,
    // debug
    DmBaseAddress:          DebugBase,
    NrPMPEntries:           8
  };

endpackage
