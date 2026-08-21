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
// limitations under the License
`default_nettype none
module bscan_tap
  #(
    parameter AWIDTH = 7
    )
   (
    input wire 		     clk,
    input wire 		     rst,
    output wire [31:0] 	     dmi_reg_wdata,
    output wire [AWIDTH-1:0] dmi_reg_addr,
    output wire 	     dmi_reg_wr_en,
    output wire 	     dmi_reg_en,

    input wire [31:0] 	     dmi_reg_rdata,
    input wire [1:0] 	     rd_status,

    output reg 		     dmi_hard_reset,
    input wire [2:0] 	     idle,
    input wire [1:0] 	     dmi_stat,
    input wire [31:1] 	     jtag_id,
    input wire [3:0] 	     version);

   wire 		idcode_capture;
   wire 		idcode_tck;
   wire 		idcode_sel;
   wire 		idcode_shift;
   reg [31:0] 		idcode;

   BSCANE2
     #(.JTAG_CHAIN(2))
   tap_idcode
     (.CAPTURE (idcode_capture),
      .DRCK    (idcode_tck),
      .RESET   (),
      .RUNTEST (),
      .SEL     (idcode_sel),
      .SHIFT   (idcode_shift),
      .TCK     (),
      .TDI     (),
      .TMS     (),
      .TDO     (idcode[0]),
      .UPDATE  ());

   always @(posedge idcode_tck) begin
      if (idcode_sel)
	if (idcode_capture)
	  idcode <= {jtag_id, 1'b1};
	else
	  idcode <= {1'b0,idcode[31:1]};
   end
   
   wire dmi_capture;
   wire dmi_tck;
   reg [31:0] dmi;
   wire       dmi_sel;
   wire       dmi_shift;
   wire dmi_tdi;
   wire dmi_update;

   BSCANE2
     #(.JTAG_CHAIN(4))
   tap_dmi
     (.CAPTURE (dmi_capture),
      .DRCK    (),
      .RESET   (),
      .RUNTEST (),
      .SEL     (dmi_sel),
      .SHIFT   (dmi_shift),
      .TCK     (dmi_tck),
      .TDI     (dmi_tdi),
      .TMS     (),
      .TDO     (dmi[0]),
      .UPDATE  (dmi_update));

   always @(posedge dmi_tck) begin
      if (dmi_sel)
	if (dmi_capture)
	  dmi <= {17'd0, idle, dmi_stat, AWIDTH[5:0], version};
	else if (dmi_shift)
	  dmi <= {dmi_tdi,dmi[31:1]};
      dmi_hard_reset <= 1'b0;
      if (dmi_update & dmi_sel)
	dmi_hard_reset <= dmi[17];
   end      

   reg [40:0] dtmcs;
   reg [40:0] dtmcs_r;
   wire       dtmcs_capture;
   wire       dtmcs_tck;
   wire       dtmcs_sel;
   wire       dtmcs_shift;
   wire       dtmcs_tdi;
   wire       dtmcs_update;
   
   BSCANE2
     #(.JTAG_CHAIN(3))
   tap_dtmcs
     (.CAPTURE (dtmcs_capture),
      .DRCK    (),
      .RESET   (),
      .RUNTEST (),
      .SEL     (dtmcs_sel),
      .SHIFT   (dtmcs_shift),
      .TCK     (dtmcs_tck),
      .TDI     (dtmcs_tdi),
      .TMS     (),
      .TDO     (dtmcs[0]),
      .UPDATE  (dtmcs_update));

   always @(posedge dtmcs_tck) begin
      if (dtmcs_sel)
	if (dtmcs_capture)
	  dtmcs <= {7'd0, dmi_reg_rdata, rd_status};
	else if (dtmcs_shift)
	  dtmcs <= {dtmcs_tdi,dtmcs[40:1]};
      dtmcs_r[1:0] <= 2'b00;
      if (dtmcs_update & dtmcs_sel)
	dtmcs_r <= dtmcs;
   end      

   wire wr_en, rd_en;
   
assign {dmi_reg_addr, dmi_reg_wdata, wr_en, rd_en} = dtmcs_r;

   

  reg [2:0] rden, wren;

   wire     c_rd_en = rden[1] & ~rden[2];
   wire     c_wr_en = wren[1] & ~wren[2];

   always @ ( posedge clk or posedge rst) begin
      if(rst) begin
	 rden <= '0;
	 wren <= '0;
      end else begin
	 rden <= {rden[1:0], rd_en};
	 wren <= {wren[1:0], wr_en};
      end
   end

  assign dmi_reg_en    = c_wr_en | c_rd_en;
  assign dmi_reg_wr_en = c_wr_en;

endmodule
