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
	output [NUM_AD-1:0] sd_a,
	output [NUM_BA-1:0] sd_ba,
	output sd_cs_n,
	output sd_cke,
	output sd_ras_n,
	output sd_cas_n,
	output sd_we_n,
	inout [NUM_D/2-1:0] sd_dq,
	output [NUM_D/16-1:0] sd_dm,
	inout [NUM_D/16-1:0] sd_dqs
);

endmodule
