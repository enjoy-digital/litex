// SPDX-License-Identifier: Apache-2.0
// Copyright 2019 Western Digital Corporation or its affiliates.
//
// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at
//
// http://www.apache.org/licenses/LICENSE-2.0
//
// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.

//********************************************************************************
// $Id$
//
// Function: Top wrapper file with veer/mem instantiated inside
// Comments:
//
//********************************************************************************
`default_nettype wire
`include "build.h"
//`include "def.sv"
module veer_wrapper_dmi
   import veer_types::*;
(
   input logic                       clk,
   input logic                       rst_l,
   input logic                       dbg_rst_l,
   input logic [31:1]                rst_vec,
   input logic                       nmi_int,
   input logic [31:1]                nmi_vec,


   output logic [63:0] trace_rv_i_insn_ip,
   output logic [63:0] trace_rv_i_address_ip,
   output logic [2:0]  trace_rv_i_valid_ip,
   output logic [2:0]  trace_rv_i_exception_ip,
   output logic [4:0]  trace_rv_i_ecause_ip,
   output logic [2:0]  trace_rv_i_interrupt_ip,
   output logic [31:0] trace_rv_i_tval_ip,

   // Bus signals

   //-------------------------- LSU AXI signals--------------------------
   // AXI Write Channels
   output logic                            lsu_axi_awvalid,
   input  logic                            lsu_axi_awready,
   output logic [`RV_LSU_BUS_TAG-1:0]      lsu_axi_awid,
   output logic [31:0]                     lsu_axi_awaddr,
   output logic [3:0]                      lsu_axi_awregion,
   output logic [7:0]                      lsu_axi_awlen,
   output logic [2:0]                      lsu_axi_awsize,
   output logic [1:0]                      lsu_axi_awburst,
   output logic                            lsu_axi_awlock,
   output logic [3:0]                      lsu_axi_awcache,
   output logic [2:0]                      lsu_axi_awprot,
   output logic [3:0]                      lsu_axi_awqos,

   output logic                            lsu_axi_wvalid,
   input  logic                            lsu_axi_wready,
   output logic [63:0]                     lsu_axi_wdata,
   output logic [7:0]                      lsu_axi_wstrb,
   output logic                            lsu_axi_wlast,

   input  logic                            lsu_axi_bvalid,
   output logic                            lsu_axi_bready,
   input  logic [1:0]                      lsu_axi_bresp,
   input  logic [`RV_LSU_BUS_TAG-1:0]      lsu_axi_bid,

   // AXI Read Channels
   output logic                            lsu_axi_arvalid,
   input  logic                            lsu_axi_arready,
   output logic [`RV_LSU_BUS_TAG-1:0]      lsu_axi_arid,
   output logic [31:0]                     lsu_axi_araddr,
   output logic [3:0]                      lsu_axi_arregion,
   output logic [7:0]                      lsu_axi_arlen,
   output logic [2:0]                      lsu_axi_arsize,
   output logic [1:0]                      lsu_axi_arburst,
   output logic                            lsu_axi_arlock,
   output logic [3:0]                      lsu_axi_arcache,
   output logic [2:0]                      lsu_axi_arprot,
   output logic [3:0]                      lsu_axi_arqos,

   input  logic                            lsu_axi_rvalid,
   output logic                            lsu_axi_rready,
   input  logic [`RV_LSU_BUS_TAG-1:0]      lsu_axi_rid,
   input  logic [63:0]                     lsu_axi_rdata,
   input  logic [1:0]                      lsu_axi_rresp,
   input  logic                            lsu_axi_rlast,

   //-------------------------- IFU AXI signals--------------------------
   // AXI Write Channels
   output logic                            ifu_axi_awvalid,
   input  logic                            ifu_axi_awready,
   output logic [`RV_IFU_BUS_TAG-1:0]      ifu_axi_awid,
   output logic [31:0]                     ifu_axi_awaddr,
   output logic [3:0]                      ifu_axi_awregion,
   output logic [7:0]                      ifu_axi_awlen,
   output logic [2:0]                      ifu_axi_awsize,
   output logic [1:0]                      ifu_axi_awburst,
   output logic                            ifu_axi_awlock,
   output logic [3:0]                      ifu_axi_awcache,
   output logic [2:0]                      ifu_axi_awprot,
   output logic [3:0]                      ifu_axi_awqos,

   output logic                            ifu_axi_wvalid,
   input  logic                            ifu_axi_wready,
   output logic [63:0]                     ifu_axi_wdata,
   output logic [7:0]                      ifu_axi_wstrb,
   output logic                            ifu_axi_wlast,

   input  logic                            ifu_axi_bvalid,
   output logic                            ifu_axi_bready,
   input  logic [1:0]                      ifu_axi_bresp,
   input  logic [`RV_IFU_BUS_TAG-1:0]      ifu_axi_bid,

   // AXI Read Channels
   output logic                            ifu_axi_arvalid,
   input  logic                            ifu_axi_arready,
   output logic [`RV_IFU_BUS_TAG-1:0]      ifu_axi_arid,
   output logic [31:0]                     ifu_axi_araddr,
   output logic [3:0]                      ifu_axi_arregion,
   output logic [7:0]                      ifu_axi_arlen,
   output logic [2:0]                      ifu_axi_arsize,
   output logic [1:0]                      ifu_axi_arburst,
   output logic                            ifu_axi_arlock,
   output logic [3:0]                      ifu_axi_arcache,
   output logic [2:0]                      ifu_axi_arprot,
   output logic [3:0]                      ifu_axi_arqos,

   input  logic                            ifu_axi_rvalid,
   output logic                            ifu_axi_rready,
   input  logic [`RV_IFU_BUS_TAG-1:0]      ifu_axi_rid,
   input  logic [63:0]                     ifu_axi_rdata,
   input  logic [1:0]                      ifu_axi_rresp,
   input  logic                            ifu_axi_rlast,

   //-------------------------- SB AXI signals--------------------------
   // AXI Write Channels
   output logic                            sb_axi_awvalid,
   input  logic                            sb_axi_awready,
   output logic [`RV_SB_BUS_TAG-1:0]       sb_axi_awid,
   output logic [31:0]                     sb_axi_awaddr,
   output logic [3:0]                      sb_axi_awregion,
   output logic [7:0]                      sb_axi_awlen,
   output logic [2:0]                      sb_axi_awsize,
   output logic [1:0]                      sb_axi_awburst,
   output logic                            sb_axi_awlock,
   output logic [3:0]                      sb_axi_awcache,
   output logic [2:0]                      sb_axi_awprot,
   output logic [3:0]                      sb_axi_awqos,

   output logic                            sb_axi_wvalid,
   input  logic                            sb_axi_wready,
   output logic [63:0]                     sb_axi_wdata,
   output logic [7:0]                      sb_axi_wstrb,
   output logic                            sb_axi_wlast,

   input  logic                            sb_axi_bvalid,
   output logic                            sb_axi_bready,
   input  logic [1:0]                      sb_axi_bresp,
   input  logic [`RV_SB_BUS_TAG-1:0]       sb_axi_bid,

   // AXI Read Channels
   output logic                            sb_axi_arvalid,
   input  logic                            sb_axi_arready,
   output logic [`RV_SB_BUS_TAG-1:0]       sb_axi_arid,
   output logic [31:0]                     sb_axi_araddr,
   output logic [3:0]                      sb_axi_arregion,
   output logic [7:0]                      sb_axi_arlen,
   output logic [2:0]                      sb_axi_arsize,
   output logic [1:0]                      sb_axi_arburst,
   output logic                            sb_axi_arlock,
   output logic [3:0]                      sb_axi_arcache,
   output logic [2:0]                      sb_axi_arprot,
   output logic [3:0]                      sb_axi_arqos,

   input  logic                            sb_axi_rvalid,
   output logic                            sb_axi_rready,
   input  logic [`RV_SB_BUS_TAG-1:0]       sb_axi_rid,
   input  logic [63:0]                     sb_axi_rdata,
   input  logic [1:0]                      sb_axi_rresp,
   input  logic                            sb_axi_rlast,

   //-------------------------- DMA AXI signals--------------------------
   // AXI Write Channels
   input  logic                         dma_axi_awvalid,
   output logic                         dma_axi_awready,
   input  logic [`RV_DMA_BUS_TAG-1:0]   dma_axi_awid,
   input  logic [31:0]                  dma_axi_awaddr,
   input  logic [2:0]                   dma_axi_awsize,
   input  logic [2:0]                   dma_axi_awprot,
   input  logic [7:0]                   dma_axi_awlen,
   input  logic [1:0]                   dma_axi_awburst,


   input  logic                         dma_axi_wvalid,
   output logic                         dma_axi_wready,
   input  logic [63:0]                  dma_axi_wdata,
   input  logic [7:0]                   dma_axi_wstrb,
   input  logic                         dma_axi_wlast,

   output logic                         dma_axi_bvalid,
   input  logic                         dma_axi_bready,
   output logic [1:0]                   dma_axi_bresp,
   output logic [`RV_DMA_BUS_TAG-1:0]   dma_axi_bid,

   // AXI Read Channels
   input  logic                         dma_axi_arvalid,
   output logic                         dma_axi_arready,
   input  logic [`RV_DMA_BUS_TAG-1:0]   dma_axi_arid,
   input  logic [31:0]                  dma_axi_araddr,
   input  logic [2:0]                   dma_axi_arsize,
   input  logic [2:0]                   dma_axi_arprot,
   input  logic [7:0]                   dma_axi_arlen,
   input  logic [1:0]                   dma_axi_arburst,

   output logic                         dma_axi_rvalid,
   input  logic                         dma_axi_rready,
   output logic [`RV_DMA_BUS_TAG-1:0]   dma_axi_rid,
   output logic [63:0]                  dma_axi_rdata,
   output logic [1:0]                   dma_axi_rresp,
   output logic                         dma_axi_rlast,

   // clk ratio signals
   input logic                       lsu_bus_clk_en, // Clock ratio b/w cpu core clk & AHB master interface
   input logic                       ifu_bus_clk_en, // Clock ratio b/w cpu core clk & AHB master interface
   input logic                       dbg_bus_clk_en, // Clock ratio b/w cpu core clk & AHB master interface
   input logic                       dma_bus_clk_en, // Clock ratio b/w cpu core clk & AHB slave interface


//   input logic                   ext_int,
   input logic                       timer_int,
   input logic [`RV_PIC_TOTAL_INT:1] extintsrc_req,

   output logic [1:0] dec_tlu_perfcnt0, // toggles when perf counter 0 has an event inc
   output logic [1:0] dec_tlu_perfcnt1,
   output logic [1:0] dec_tlu_perfcnt2,
   output logic [1:0] dec_tlu_perfcnt3,

   //Debug module
   input  logic                  dmi_reg_en,
   input  logic [6:0]            dmi_reg_addr,
   input  logic                  dmi_reg_wr_en,
   input  logic [31:0] 	         dmi_reg_wdata,
   output logic [31:0] 	         dmi_reg_rdata,
   input  logic                  dmi_hard_reset,

   // external MPC halt/run interface
   input logic mpc_debug_halt_req, // Async halt request
   input logic mpc_debug_run_req, // Async run request
   input logic mpc_reset_run_req, // Run/halt after reset
   output logic mpc_debug_halt_ack, // Halt ack
   output logic mpc_debug_run_ack, // Run ack
   output logic debug_brkpt_status, // debug breakpoint

   input logic                       i_cpu_halt_req, // Async halt req to CPU
   output logic                      o_cpu_halt_ack, // core response to halt
   output logic                      o_cpu_halt_status, // 1'b1 indicates core is halted
   output logic                      o_debug_mode_status, // Core to the PMU that core is in debug mode. When core is in debug mode, the PMU should refrain from sendng a halt or run request
   input logic                       i_cpu_run_req, // Async restart req to CPU
   output logic                      o_cpu_run_ack, // Core response to run req
   input logic                       scan_mode, // To enable scan mode
   input logic                       mbist_mode // to enable mbist
);

`include "global.h"

   // DCCM ports
   logic         dccm_wren;
   logic         dccm_rden;
   logic [DCCM_BITS-1:0]  dccm_wr_addr;
   logic [DCCM_BITS-1:0]  dccm_rd_addr_lo;
   logic [DCCM_BITS-1:0]  dccm_rd_addr_hi;
   logic [DCCM_FDATA_WIDTH-1:0]  dccm_wr_data;

   logic [DCCM_FDATA_WIDTH-1:0]  dccm_rd_data_lo;
   logic [DCCM_FDATA_WIDTH-1:0]  dccm_rd_data_hi;

   logic         lsu_freeze_dc3;

   // PIC ports

   // Icache & Itag ports
   logic [31:2]  ic_rw_addr;
   logic [3:0]   ic_wr_en  ;     // Which way to write
   logic         ic_rd_en ;


   logic [3:0]   ic_tag_valid;   // Valid from the I$ tag valid outside (in flops).

   logic [3:0]   ic_rd_hit;      // ic_rd_hit[3:0]
   logic         ic_tag_perr;    // Ic tag parity error

   logic [15:2]  ic_debug_addr;      // Read/Write addresss to the Icache.
   logic         ic_debug_rd_en;     // Icache debug rd
   logic         ic_debug_wr_en;     // Icache debug wr
   logic         ic_debug_tag_array; // Debug tag array
   logic [3:0]   ic_debug_way;       // Debug way. Rd or Wr.

`ifdef RV_ICACHE_ECC
   logic [24:0]  ictag_debug_rd_data;// Debug icache tag.
   logic [83:0]  ic_wr_data;         // ic_wr_data[135:0]
   logic [167:0] ic_rd_data;         // ic_rd_data[135:0]
   logic [41:0]  ic_debug_wr_data;   // Debug wr cache.
`else
   logic [20:0]  ictag_debug_rd_data;// Debug icache tag.
   logic [67:0]  ic_wr_data;         // ic_wr_data[135:0]
   logic [135:0] ic_rd_data;         // ic_rd_data[135:0]
   logic [33:0]  ic_debug_wr_data;   // Debug wr cache.
`endif

   logic [127:0] ic_premux_data;
   logic         ic_sel_premux_data;

`ifdef RV_ICCM_ENABLE
   // ICCM ports
   logic [`RV_ICCM_BITS-1:2]    iccm_rw_addr;
   logic           iccm_wren;
   logic           iccm_rden;
   logic [2:0]     iccm_wr_size;
   logic [77:0]    iccm_wr_data;
   logic [155:0]   iccm_rd_data;
`endif

   logic        core_rst_l;     // Core reset including rst_l and dbg_rst_l
   logic        jtag_tdoEn;

   logic        dccm_clk_override;
   logic        icm_clk_override;
   logic        dec_tlu_core_ecc_disable;

   // Instantiate the veer core
   veer veer (
          .*
          );

   // Instantiate the mem
   mem  mem (
        .rst_l(core_rst_l),
        .*
        );


endmodule

`default_nettype none
