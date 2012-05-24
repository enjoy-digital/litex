/* TODO: use behavioral BRAM models (Xst can extract byte WE) */

module minimac3_memory(
	input sys_clk,
	input sys_rst,
	input phy_rx_clk,
	input phy_tx_clk,
	
	input [29:0] wb_adr_i,
	output [31:0] wb_dat_o,
	input [31:0] wb_dat_i,
	input [3:0] wb_sel_i,
	input wb_stb_i,
	input wb_cyc_i,
	output reg wb_ack_o,
	input wb_we_i,
	
	input [7:0] rxb0_dat,
	input [10:0] rxb0_adr,
	input rxb0_we,
	input [7:0] rxb1_dat,
	input [10:0] rxb1_adr,
	input rxb1_we,
	
	output [7:0] txb_dat,
	input [10:0] txb_adr

);

wire wb_en = wb_cyc_i & wb_stb_i;
wire [1:0] wb_buf = wb_adr_i[10:9];
wire [31:0] wb_dat_i_le = {wb_dat_i[7:0], wb_dat_i[15:8], wb_dat_i[23:16], wb_dat_i[31:24]};
wire [3:0] wb_sel_i_le = {wb_sel_i[0], wb_sel_i[1], wb_sel_i[2], wb_sel_i[3]};

wire [31:0] rxb0_wbdat;
RAMB16BWER #(
	.DATA_WIDTH_A(36),
	.DATA_WIDTH_B(9),
	.DOA_REG(0),
	.DOB_REG(0),
	.EN_RSTRAM_A("FALSE"),
	.EN_RSTRAM_B("FALSE"),
	.SIM_DEVICE("SPARTAN6"),
	.WRITE_MODE_A("WRITE_FIRST"),
	.WRITE_MODE_B("WRITE_FIRST")
) rxb0 (
	.DIA(wb_dat_i_le),
	.DIPA(4'd0),
	.DOA(rxb0_wbdat),
	.ADDRA({wb_adr_i[8:0], 5'd0}),
	.WEA({4{wb_en & wb_we_i & (wb_buf == 2'b00)}} & wb_sel_i_le),
	.ENA(1'b1),
	.RSTA(1'b0),
	.CLKA(sys_clk),

	.DIB(rxb0_dat),
	.DIPB(1'd0),
	.DOB(),
	.ADDRB({rxb0_adr, 3'd0}),
	.WEB({4{rxb0_we}}),
	.ENB(1'b1),
	.RSTB(1'b0),
	.CLKB(phy_rx_clk)
);

wire [31:0] rxb1_wbdat;
RAMB16BWER #(
	.DATA_WIDTH_A(36),
	.DATA_WIDTH_B(9),
	.DOA_REG(0),
	.DOB_REG(0),
	.EN_RSTRAM_A("FALSE"),
	.EN_RSTRAM_B("FALSE"),
	.SIM_DEVICE("SPARTAN6"),
	.WRITE_MODE_A("WRITE_FIRST"),
	.WRITE_MODE_B("WRITE_FIRST")
) rxb1 (
	.DIA(wb_dat_i_le),
	.DIPA(4'd0),
	.DOA(rxb1_wbdat),
	.ADDRA({wb_adr_i[8:0], 5'd0}),
	.WEA({4{wb_en & wb_we_i & (wb_buf == 2'b01)}} & wb_sel_i_le),
	.ENA(1'b1),
	.RSTA(1'b0),
	.CLKA(sys_clk),

	.DIB(rxb1_dat),
	.DIPB(1'd0),
	.DOB(),
	.ADDRB({rxb1_adr, 3'd0}),
	.WEB({4{rxb1_we}}),
	.ENB(1'b1),
	.RSTB(1'b0),
	.CLKB(phy_rx_clk)
);

wire [31:0] txb_wbdat;
RAMB16BWER #(
	.DATA_WIDTH_A(36),
	.DATA_WIDTH_B(9),
	.DOA_REG(0),
	.DOB_REG(0),
	.EN_RSTRAM_A("FALSE"),
	.EN_RSTRAM_B("FALSE"),
	.SIM_DEVICE("SPARTAN6"),
	.WRITE_MODE_A("WRITE_FIRST"),
	.WRITE_MODE_B("WRITE_FIRST")
) txb (
	.DIA(wb_dat_i_le),
	.DIPA(4'd0),
	.DOA(txb_wbdat),
	.ADDRA({wb_adr_i[8:0], 5'd0}),
	.WEA({4{wb_en & wb_we_i & (wb_buf == 2'b10)}} & wb_sel_i_le),
	.ENA(1'b1),
	.RSTA(1'b0),
	.CLKA(sys_clk),

	.DIB(8'd0),
	.DIPB(1'd0),
	.DOB(txb_dat),
	.ADDRB({txb_adr, 3'd0}),
	.WEB(4'd0),
	.ENB(1'b1),
	.RSTB(1'b0),
	.CLKB(phy_tx_clk)
);

always @(posedge sys_clk) begin
	if(sys_rst)
		wb_ack_o <= 1'b0;
	else begin
		wb_ack_o <= 1'b0;
		if(wb_en & ~wb_ack_o)
			wb_ack_o <= 1'b1;
	end
end

reg [1:0] wb_buf_r;
always @(posedge sys_clk)
	wb_buf_r <= wb_buf;

reg [31:0] wb_dat_o_le;
always @(*) begin
	case(wb_buf_r)
		2'b00: wb_dat_o_le = rxb0_wbdat;
		2'b01: wb_dat_o_le = rxb1_wbdat;
		default: wb_dat_o_le = txb_wbdat;
	endcase
end
assign wb_dat_o = {wb_dat_o_le[7:0], wb_dat_o_le[15:8], wb_dat_o_le[23:16], wb_dat_o_le[31:24]};

endmodule
