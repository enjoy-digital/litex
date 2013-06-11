/*
 * 1:2 frequency-ratio DDR PHY for Spartan-6
 *
 * Assert dfi_wrdata_en and present the data 
 * on dfi_wrdata_mask/dfi_wrdata in the cycle
 * immediately following the write command.
 *
 * Assert dfi_rddata_en in the same cycle as the read
 * command. The data will come back on dfi_rddata
 * 5 cycles later, along with the assertion of
 * dfi_rddata_valid.
 *
 * This PHY only supports CAS Latency 3.
 * Read commands must be sent on phase 0.
 * Write commands must be sent on phase 1.
 */

module s6ddrphy #(
	parameter NUM_AD = 0,
	parameter NUM_BA = 0,
	parameter NUM_D = 0 /* < number of data lines per DFI phase */
) (
	/* Clocks */
	input sys_clk,
	input clk2x_270,
	input clk4x_wr,
	input clk4x_wr_strb,
	input clk4x_rd,
	input clk4x_rd_strb,
	
	/* DFI phase 0 */
	input [NUM_AD-1:0] dfi_address_p0,
	input [NUM_BA-1:0] dfi_bank_p0,
	input dfi_cs_n_p0,
	input dfi_cke_p0,
	input dfi_ras_n_p0,
	input dfi_cas_n_p0,
	input dfi_we_n_p0,
	input dfi_wrdata_en_p0,
	input [NUM_D/8-1:0] dfi_wrdata_mask_p0,
	input [NUM_D-1:0] dfi_wrdata_p0,
	input dfi_rddata_en_p0,
	output [NUM_D-1:0] dfi_rddata_w0,
	output dfi_rddata_valid_w0,
	
	/* DFI phase 1 */
	input [NUM_AD-1:0] dfi_address_p1,
	input [NUM_BA-1:0] dfi_bank_p1,
	input dfi_cs_n_p1,
	input dfi_cke_p1,
	input dfi_ras_n_p1,
	input dfi_cas_n_p1,
	input dfi_we_n_p1,
	input dfi_wrdata_en_p1,
	input [NUM_D/8-1:0] dfi_wrdata_mask_p1,
	input [NUM_D-1:0] dfi_wrdata_p1,
	input dfi_rddata_en_p1,
	output [NUM_D-1:0] dfi_rddata_w1,
	output dfi_rddata_valid_w1,
	
	/* DDR SDRAM pads */
	output reg [NUM_AD-1:0] sd_a,
	output reg [NUM_BA-1:0] sd_ba,
	output reg sd_cs_n,
	output reg sd_cke,
	output reg sd_ras_n,
	output reg sd_cas_n,
	output reg sd_we_n,
	inout [NUM_D/2-1:0] sd_dq,
	output [NUM_D/16-1:0] sd_dm,
	inout [NUM_D/16-1:0] sd_dqs
);

/* 
 * Command/address
 */

reg [NUM_AD-1:0] r0_dfi_address_p0;
reg [NUM_BA-1:0] r0_dfi_bank_p0;
reg r0_dfi_cs_n_p0;
reg r0_dfi_cke_p0;
reg r0_dfi_ras_n_p0;
reg r0_dfi_cas_n_p0;
reg r0_dfi_we_n_p0;
reg [NUM_AD-1:0] r0_dfi_address_p1;
reg [NUM_BA-1:0] r0_dfi_bank_p1;
reg r0_dfi_cs_n_p1;
reg r0_dfi_cke_p1;
reg r0_dfi_ras_n_p1;
reg r0_dfi_cas_n_p1;
reg r0_dfi_we_n_p1;
	
always @(posedge sys_clk) begin
	r0_dfi_address_p0 <= dfi_address_p0;
	r0_dfi_bank_p0 <= dfi_bank_p0;
	r0_dfi_cs_n_p0 <= dfi_cs_n_p0;
	r0_dfi_cke_p0 <= dfi_cke_p0;
	r0_dfi_ras_n_p0 <= dfi_ras_n_p0;
	r0_dfi_cas_n_p0 <= dfi_cas_n_p0;
	r0_dfi_we_n_p0 <= dfi_we_n_p0;
	
	r0_dfi_address_p1 <= dfi_address_p1;
	r0_dfi_bank_p1 <= dfi_bank_p1;
	r0_dfi_cs_n_p1 <= dfi_cs_n_p1;
	r0_dfi_cke_p1 <= dfi_cke_p1;
	r0_dfi_ras_n_p1 <= dfi_ras_n_p1;
	r0_dfi_cas_n_p1 <= dfi_cas_n_p1;
	r0_dfi_we_n_p1 <= dfi_we_n_p1;
end

reg phase_sel;
always @(posedge clk2x_270)
	phase_sel <= sys_clk;

reg [NUM_AD-1:0] r_dfi_address_p0;
reg [NUM_BA-1:0] r_dfi_bank_p0;
reg r_dfi_cs_n_p0;
reg r_dfi_cke_p0;
reg r_dfi_ras_n_p0;
reg r_dfi_cas_n_p0;
reg r_dfi_we_n_p0;
reg [NUM_AD-1:0] r_dfi_address_p1;
reg [NUM_BA-1:0] r_dfi_bank_p1;
reg r_dfi_cs_n_p1;
reg r_dfi_cke_p1;
reg r_dfi_ras_n_p1;
reg r_dfi_cas_n_p1;
reg r_dfi_we_n_p1;
	
always @(posedge clk2x_270) begin
	r_dfi_address_p0 <= r0_dfi_address_p0;
	r_dfi_bank_p0 <= r0_dfi_bank_p0;
	r_dfi_cs_n_p0 <= r0_dfi_cs_n_p0;
	r_dfi_cke_p0 <= r0_dfi_cke_p0;
	r_dfi_ras_n_p0 <= r0_dfi_ras_n_p0;
	r_dfi_cas_n_p0 <= r0_dfi_cas_n_p0;
	r_dfi_we_n_p0 <= r0_dfi_we_n_p0;
	
	r_dfi_address_p1 <= r0_dfi_address_p1;
	r_dfi_bank_p1 <= r0_dfi_bank_p1;
	r_dfi_cs_n_p1 <= r0_dfi_cs_n_p1;
	r_dfi_cke_p1 <= r0_dfi_cke_p1;
	r_dfi_ras_n_p1 <= r0_dfi_ras_n_p1;
	r_dfi_cas_n_p1 <= r0_dfi_cas_n_p1;
	r_dfi_we_n_p1 <= r0_dfi_we_n_p1;
end

always @(posedge clk2x_270) begin
	if(phase_sel) begin
		sd_a <= r_dfi_address_p0;
		sd_ba <= r_dfi_bank_p0;
		sd_cs_n <= r_dfi_cs_n_p0;
		sd_cke <= r_dfi_cke_p0;
		sd_ras_n <= r_dfi_ras_n_p0;
		sd_cas_n <= r_dfi_cas_n_p0;
		sd_we_n <= r_dfi_we_n_p0;
	end else begin
		sd_a <= r_dfi_address_p1;
		sd_ba <= r_dfi_bank_p1;
		sd_cs_n <= r_dfi_cs_n_p1;
		sd_cke <= r_dfi_cke_p1;
		sd_ras_n <= r_dfi_ras_n_p1;
		sd_cas_n <= r_dfi_cas_n_p1;
		sd_we_n <= r_dfi_we_n_p1;
	end
end

/* 
 * DQ/DQS/DM data
 */

genvar i;

wire drive_dqs;
wire [NUM_D/16-1:0] dqs_o;
wire [NUM_D/16-1:0] dqs_t;
reg postamble;
generate
	for(i=0;i<NUM_D/16;i=i+1)
	begin: gen_dqs
		ODDR2 #(
			.DDR_ALIGNMENT("C1"),
			.INIT(1'b0),
			.SRTYPE("ASYNC")
		) dqs_o_oddr (
			.Q(dqs_o[i]),
			.C0(clk2x_270),
			.C1(~clk2x_270),
			.CE(1'b1),
			.D0(1'b0),
			.D1(1'b1),
			.R(1'b0),
			.S(1'b0)
		);
		ODDR2 #(
			.DDR_ALIGNMENT("C1"),
			.INIT(1'b0),
			.SRTYPE("ASYNC")
		) dqs_t_oddr (
			.Q(dqs_t[i]),
			.C0(clk2x_270),
			.C1(~clk2x_270),
			.CE(1'b1),
			.D0(~(drive_dqs | postamble)),
			.D1(~drive_dqs),
			.R(1'b0),
			.S(1'b0)
		);
		OBUFT dqs_obuft(
			.I(dqs_o[i]),
			.T(dqs_t[i]),
			.O(sd_dqs[i])
		);
	end
endgenerate
always @(posedge clk2x_270)
	postamble <= drive_dqs;

reg [NUM_D-1:0] d_dfi_wrdata_p0;
reg [NUM_D-1:0] d_dfi_wrdata_p1;
reg [NUM_D/8-1:0] d_dfi_wrdata_mask_p0;
reg [NUM_D/8-1:0] d_dfi_wrdata_mask_p1;
always @(posedge sys_clk) begin
	d_dfi_wrdata_p0 <= dfi_wrdata_p0;
	d_dfi_wrdata_p1 <= dfi_wrdata_p1;
	d_dfi_wrdata_mask_p0 <= dfi_wrdata_mask_p0;
	d_dfi_wrdata_mask_p1 <= dfi_wrdata_mask_p1;
end

wire drive_dq;
wire d_drive_dq;
wire [NUM_D/2-1:0] dq_i;
wire [NUM_D/2-1:0] dq_o;
wire [NUM_D/2-1:0] dq_t;
generate
	for(i=0;i<NUM_D/2;i=i+1)
	begin: gen_dq
		OSERDES2 #(
			.DATA_WIDTH(4),
			.DATA_RATE_OQ("SDR"),
			.DATA_RATE_OT("SDR"),
			.SERDES_MODE("NONE"),
			.OUTPUT_MODE("SINGLE_ENDED")
		) dq_oserdes (
			.OQ(dq_o[i]),
			.OCE(1'b1),
			.CLK0(clk4x_wr),
			.CLK1(1'b0),
			.IOCE(clk4x_wr_strb),
			.RST(1'b0),
			.CLKDIV(sys_clk),
			.D1(d_dfi_wrdata_p0[i]),
			.D2(d_dfi_wrdata_p1[i+NUM_D/2]),
			.D3(d_dfi_wrdata_p1[i]),
			.D4(dfi_wrdata_p0[i+NUM_D/2]),
			.TQ(dq_t[i]),
			.T1(~d_drive_dq),
			.T2(~d_drive_dq),
			.T3(~d_drive_dq),
			.T4(~drive_dq),
			.TRAIN(1'b0),
			.TCE(1'b1),
			.SHIFTIN1(1'b0),
			.SHIFTIN2(1'b0),
			.SHIFTIN3(1'b0),
			.SHIFTIN4(1'b0),
			.SHIFTOUT1(),
			.SHIFTOUT2(),
			.SHIFTOUT3(),
			.SHIFTOUT4()
		);
		ISERDES2 #(
			.DATA_WIDTH(4),
			.DATA_RATE("SDR"),
			.BITSLIP_ENABLE("FALSE"),
			.SERDES_MODE("NONE"),
			.INTERFACE_TYPE("RETIMED")
		) dq_iserdes (
			.D(dq_i[i]),
			.CE0(1'b1),
			.CLK0(clk4x_rd),
			.CLK1(1'b0),
			.IOCE(clk4x_rd_strb),
			.RST(1'b0),
			.CLKDIV(sys_clk),
			.SHIFTIN(),
			.BITSLIP(1'b0),
			.FABRICOUT(),
			.Q1(dfi_rddata_w0[i+NUM_D/2]),
			.Q2(dfi_rddata_w0[i]),
			.Q3(dfi_rddata_w1[i+NUM_D/2]),
			.Q4(dfi_rddata_w1[i]),
			.DFB(),
			.CFB0(),
			.CFB1(),
			.VALID(),
			.INCDEC(),
			.SHIFTOUT()
		);
		IOBUF dq_iobuf(
			.I(dq_o[i]),
			.O(dq_i[i]),
			.T(dq_t[i]),
			.IO(sd_dq[i])
		);
	end
endgenerate

generate
	for(i=0;i<NUM_D/16;i=i+1)
	begin: gen_dm_oserdes
		OSERDES2 #(
			.DATA_WIDTH(4),
			.DATA_RATE_OQ("SDR"),
			.DATA_RATE_OT("SDR"),
			.SERDES_MODE("NONE"),
			.OUTPUT_MODE("SINGLE_ENDED")
		) dm_oserdes (
			.OQ(sd_dm[i]),
			.OCE(1'b1),
			.CLK0(clk4x_wr),
			.CLK1(1'b0),
			.IOCE(clk4x_wr_strb),
			.RST(1'b0),
			.CLKDIV(sys_clk),
			.D1(d_dfi_wrdata_mask_p0[i]),
			.D2(d_dfi_wrdata_mask_p1[i+NUM_D/16]),
			.D3(d_dfi_wrdata_mask_p1[i]),
			.D4(dfi_wrdata_mask_p0[i+NUM_D/16]),
			.TQ(),
			.T1(),
			.T2(),
			.T3(),
			.T4(),
			.TRAIN(1'b0),
			.TCE(1'b0),
			.SHIFTIN1(1'b0),
			.SHIFTIN2(1'b0),
			.SHIFTIN3(1'b0),
			.SHIFTIN4(1'b0),
			.SHIFTOUT1(),
			.SHIFTOUT2(),
			.SHIFTOUT3(),
			.SHIFTOUT4()
		);
	end
endgenerate
 
/* 
 * DQ/DQS/DM control
 */

reg d_dfi_wrdata_en_p1;
always @(posedge sys_clk)
	d_dfi_wrdata_en_p1 <= dfi_wrdata_en_p1;
 
assign drive_dq = dfi_wrdata_en_p1;
assign d_drive_dq = d_dfi_wrdata_en_p1;
 
reg r_dfi_wrdata_en;
reg r2_dfi_wrdata_en;
always @(posedge clk2x_270) begin
	r_dfi_wrdata_en <= d_dfi_wrdata_en_p1;
	r2_dfi_wrdata_en <= r_dfi_wrdata_en;
end

assign drive_dqs = r2_dfi_wrdata_en;

wire rddata_valid;
reg [5:0] rddata_sr;
assign dfi_rddata_valid_w0 = rddata_sr[0];
assign dfi_rddata_valid_w1 = rddata_sr[0];
always @(posedge sys_clk)
	rddata_sr <= {dfi_rddata_en_p0, rddata_sr[5:1]};

endmodule
