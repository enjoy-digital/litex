module minimac3(
	input sys_clk,
	input sys_rst,

	/* Control */
	input rx_ready_0,
	output rx_done_0,
	output [10:0] rx_count_0,
	input rx_ready_1,
	output rx_done_1,
	output [10:0] rx_count_1,
	
	input tx_start,
	output tx_done,
	input [10:0] tx_count,

	/* WISHBONE to access RAM */
	input [29:0] wb_adr_i,
	output [31:0] wb_dat_o,
	input [31:0] wb_dat_i,
	input [3:0] wb_sel_i,
	input wb_stb_i,
	input wb_cyc_i,
	output wb_ack_o,
	input wb_we_i,

	/* To PHY */
	input phy_tx_clk,
	output [3:0] phy_tx_data,
	output phy_tx_en,
	output phy_tx_er,
	input phy_rx_clk,
	input [3:0] phy_rx_data,
	input phy_dv,
	input phy_rx_er,
	input phy_col,
	input phy_crs
);

wire [1:0] phy_rx_ready;
wire [1:0] phy_rx_done;
wire [10:0] phy_rx_count_0;
wire [10:0] phy_rx_count_1;
wire phy_tx_start;
wire phy_tx_done;
wire [10:0] phy_tx_count;

minimac3_sync sync(
	.sys_clk(sys_clk),
	.phy_rx_clk(phy_rx_clk),
	.phy_tx_clk(phy_tx_clk),
	
	.sys_rx_ready({rx_ready_1, rx_ready_0}),
	.sys_rx_done({rx_done_1, rx_done_0}),
	.sys_rx_count_0(rx_count_0),
	.sys_rx_count_1(rx_count_1),
	.sys_tx_start(tx_start),
	.sys_tx_done(tx_done),
	.sys_tx_count(tx_count),
	
	.phy_rx_ready(phy_rx_ready),
	.phy_rx_done(phy_rx_done),
	.phy_rx_count_0(phy_rx_count_0),
	.phy_rx_count_1(phy_rx_count_1),
	.phy_tx_start(phy_tx_start),
	.phy_tx_done(phy_tx_done),
	.phy_tx_count(phy_tx_count)
);

wire [7:0] rxb0_dat;
wire [10:0] rxb0_adr;
wire rxb0_we;
wire [7:0] rxb1_dat;
wire [10:0] rxb1_adr;
wire rxb1_we;
wire [7:0] txb_dat;
wire [10:0] txb_adr;
minimac3_memory memory(
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),
	.phy_rx_clk(phy_rx_clk),
	.phy_tx_clk(phy_tx_clk),

	.wb_adr_i(wb_adr_i),
	.wb_dat_o(wb_dat_o),
	.wb_dat_i(wb_dat_i),
	.wb_sel_i(wb_sel_i),
	.wb_stb_i(wb_stb_i),
	.wb_cyc_i(wb_cyc_i),
	.wb_ack_o(wb_ack_o),
	.wb_we_i(wb_we_i),
	
	.rxb0_dat(rxb0_dat),
	.rxb0_adr(rxb0_adr),
	.rxb0_we(rxb0_we),
	.rxb1_dat(rxb1_dat),
	.rxb1_adr(rxb1_adr),
	.rxb1_we(rxb1_we),
	
	.txb_dat(txb_dat),
	.txb_adr(txb_adr)
);

minimac3_tx tx(
	.phy_tx_clk(phy_tx_clk),
	
	.tx_start(phy_tx_start),
	.tx_done(phy_tx_done),
	.tx_count(phy_tx_count),
	.txb_dat(txb_dat),
	.txb_adr(txb_adr),
	
	.phy_tx_en(phy_tx_en),
	.phy_tx_data(phy_tx_data)
);
assign phy_tx_er = 1'b0;

minimac3_rx rx(
	.phy_rx_clk(phy_rx_clk),
	
	.rx_ready(phy_rx_ready),
	.rx_done(phy_rx_done),
	.rx_count_0(phy_rx_count_0),
	.rx_count_1(phy_rx_count_1),
	
	.rxb0_dat(rxb0_dat),
	.rxb0_adr(rxb0_adr),
	.rxb0_we(rxb0_we),
	.rxb1_dat(rxb1_dat),
	.rxb1_adr(rxb1_adr),
	.rxb1_we(rxb1_we),
	
	.phy_dv(phy_dv),
	.phy_rx_data(phy_rx_data),
	.phy_rx_er(phy_rx_er)
);

endmodule
