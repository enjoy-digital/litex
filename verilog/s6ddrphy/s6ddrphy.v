module s6ddrphy #(
	parameter NUM_AD = 0,
	parameter NUM_BA = 0,
	parameter NUM_D = 0 /* < number of data lines per DFI phase */
) (
	/* Clocks */
	input sys_clk,
	input clk2x_90,
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
	output sd_clk_out_p,
	output sd_clk_out_n,
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
 * SDRAM clock
 */
ODDR2 #(
	.DDR_ALIGNMENT("NONE"),
	.INIT(1'b0),
	.SRTYPE("SYNC")
) sd_clk_forward_p (
	.Q(sd_clk_out_p),
	.C0(clk2x_90),
	.C1(~clk2x_90),
	.CE(1'b1),
	.D0(1'b1),
	.D1(1'b0),
	.R(1'b0),
	.S(1'b0)
);
ODDR2 #(
	.DDR_ALIGNMENT("NONE"),
	.INIT(1'b0),
	.SRTYPE("SYNC")
) sd_clk_forward_n (
	.Q(sd_clk_out_n),
	.C0(clk2x_90),
	.C1(~clk2x_90),
	.CE(1'b1),
	.D0(1'b0),
	.D1(1'b1),
	.R(1'b0),
	.S(1'b0)
);

/* 
 * Command/address
 */

reg phase_sel;
always @(negedge clk2x_90)
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
	
always @(posedge sys_clk) begin
	r_dfi_address_p0 <= dfi_address_p0;
	r_dfi_bank_p0 <= dfi_bank_p0;
	r_dfi_cs_n_p0 <= dfi_cs_n_p0;
	r_dfi_cke_p0 <= dfi_cke_p0;
	r_dfi_ras_n_p0 <= dfi_ras_n_p0;
	r_dfi_cas_n_p0 <= dfi_cas_n_p0;
	r_dfi_we_n_p0 <= dfi_we_n_p0;
	
	r_dfi_address_p1 <= dfi_address_p1;
	r_dfi_bank_p1 <= dfi_bank_p1;
	r_dfi_cs_n_p1 <= dfi_cs_n_p1;
	r_dfi_cke_p1 <= dfi_cke_p1;
	r_dfi_ras_n_p1 <= dfi_ras_n_p1;
	r_dfi_cas_n_p1 <= dfi_cas_n_p1;
	r_dfi_we_n_p1 <= dfi_we_n_p1;
end

reg [NUM_AD-1:0] r2_dfi_address_p0;
reg [NUM_BA-1:0] r2_dfi_bank_p0;
reg r2_dfi_cs_n_p0;
reg r2_dfi_cke_p0;
reg r2_dfi_ras_n_p0;
reg r2_dfi_cas_n_p0;
reg r2_dfi_we_n_p0;
reg [NUM_AD-1:0] r2_dfi_address_p1;
reg [NUM_BA-1:0] r2_dfi_bank_p1;
reg r2_dfi_cs_n_p1;
reg r2_dfi_cke_p1;
reg r2_dfi_ras_n_p1;
reg r2_dfi_cas_n_p1;
reg r2_dfi_we_n_p1;
	
always @(negedge clk2x_90) begin
	r2_dfi_address_p0 <= r_dfi_address_p0;
	r2_dfi_bank_p0 <= r_dfi_bank_p0;
	r2_dfi_cs_n_p0 <= r_dfi_cs_n_p0;
	r2_dfi_cke_p0 <= r_dfi_cke_p0;
	r2_dfi_ras_n_p0 <= r_dfi_ras_n_p0;
	r2_dfi_cas_n_p0 <= r_dfi_cas_n_p0;
	r2_dfi_we_n_p0 <= r_dfi_we_n_p0;
	
	r2_dfi_address_p1 <= r_dfi_address_p1;
	r2_dfi_bank_p1 <= r_dfi_bank_p1;
	r2_dfi_cs_n_p1 <= r_dfi_cs_n_p1;
	r2_dfi_cke_p1 <= r_dfi_cke_p1;
	r2_dfi_ras_n_p1 <= r_dfi_ras_n_p1;
	r2_dfi_cas_n_p1 <= r_dfi_cas_n_p1;
	r2_dfi_we_n_p1 <= r_dfi_we_n_p1;
end

always @(posedge clk2x_90) begin
	if(phase_sel) begin
		sd_a <= r2_dfi_address_p1;
		sd_ba <= r2_dfi_bank_p1;
		sd_cs_n <= r2_dfi_cs_n_p1;
		sd_cke <= r2_dfi_cke_p1;
		sd_ras_n <= r2_dfi_ras_n_p1;
		sd_cas_n <= r2_dfi_cas_n_p1;
		sd_we_n <= r2_dfi_we_n_p1;
	end else begin
		sd_a <= r2_dfi_address_p0;
		sd_ba <= r2_dfi_bank_p0;
		sd_cs_n <= r2_dfi_cs_n_p0;
		sd_cke <= r2_dfi_cke_p0;
		sd_ras_n <= r2_dfi_ras_n_p0;
		sd_cas_n <= r2_dfi_cas_n_p0;
		sd_we_n <= r2_dfi_we_n_p0;
	end
end

// TODO
assign sd_dq = 32'hzzzzzzzz;
assign sd_dm = 0;
assign sd_dqs = 4'hz;
 
endmodule
