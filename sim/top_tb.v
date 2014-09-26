`timescale 1ns/1ps

module top_tb();

reg refclk_p;
wire refclk_n;
initial refclk_p = 1'b1;
always #3.33 refclk_p = ~refclk_p;
assign refclk_n = ~refclk_p;

reg clk200_p;
wire clk200_n;
initial clk200_p = 1'b1;
always #2.5 clk200_p = ~clk200_p;
assign clk200_n = ~clk200_p;

wire sata_txp;
wire sata_txn;
wire sata_rxp;
wire sata_rxn;

top dut(
	.serial_cts(1'b0),
	.serial_rts(1'b0),
	.serial_tx(),
	.serial_rx(1'b0),
	.clk200_p(clk200_p),
	.clk200_n(clk200_n),
	.sata_host_refclk_p(refclk_p),
	.sata_host_refclk_n(refclk_n),
	.sata_host_txp(sata_txp),
	.sata_host_txn(sata_txn),
	.sata_host_rxp(sata_rxp),
	.sata_host_rxn(sata_rxn),
	.sata_device_refclk_p(refclk_p),
	.sata_device_refclk_n(refclk_n),
	.sata_device_txp(sata_rxp),
	.sata_device_txn(sata_rxn),
	.sata_device_rxp(sata_txp),
	.sata_device_rxn(sata_txn)
);

endmodule
