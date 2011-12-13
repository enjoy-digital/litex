/*
 * Milkymist SoC
 * Copyright (C) 2007, 2008, 2009, 2010 Sebastien Bourdeauducq
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

module uart #(
	parameter csr_addr = 4'h0,
	parameter clk_freq = 100000000,
	parameter baud = 115200,
	parameter break_en_default = 1'b0
) (
	input sys_clk,
	input sys_rst,
	
	input [13:0] csr_a,
	input csr_we,
	input [31:0] csr_di,
	output reg [31:0] csr_do,

	output irq,

	input uart_rx,
	output uart_tx,

	output break
);

reg [15:0] divisor;
wire [7:0] rx_data;
wire [7:0] tx_data;
wire tx_wr;

wire uart_tx_transceiver;

uart_transceiver transceiver(
	.sys_clk(sys_clk),
	.sys_rst(sys_rst),

	.uart_rx(uart_rx),
	.uart_tx(uart_tx_transceiver),

	.divisor(divisor),

	.rx_data(rx_data),
	.rx_done(rx_done),

	.tx_data(tx_data),
	.tx_wr(tx_wr),
	.tx_done(tx_done),

	.break(break_transceiver)
);

assign uart_tx = thru_en ? uart_rx : uart_tx_transceiver;
assign break = break_en & break_transceiver;

/* CSR interface */
wire csr_selected = csr_a[13:10] == csr_addr;

assign irq = (tx_event & tx_irq_en) | (rx_event & rx_irq_en);

assign tx_data = csr_di[7:0];
assign tx_wr = csr_selected & csr_we & (csr_a[2:0] == 3'b000);

parameter default_divisor = clk_freq/baud/16;

reg thru_en;
reg break_en;
reg tx_irq_en;
reg rx_irq_en;
reg rx_event;
reg tx_event;
reg thre;

always @(posedge sys_clk) begin
	if(sys_rst) begin
		divisor <= default_divisor;
		csr_do <= 32'd0;
		thru_en <= 1'b0;
		break_en <= break_en_default;
		rx_irq_en <= 1'b0;
		tx_irq_en <= 1'b0;
		tx_event <= 1'b0;
		rx_event <= 1'b0;
		thre <= 1'b1;
	end else begin
		csr_do <= 32'd0;
		if(break)
			break_en <= 1'b0;
		if(tx_done) begin
			tx_event <= 1'b1;
			thre <= 1'b1;
		end
		if(tx_wr)
			thre <= 1'b0;
		if(rx_done) begin
			rx_event <= 1'b1;
		end
		if(csr_selected) begin
			case(csr_a[2:0])
				3'b000: csr_do <= rx_data;
				3'b001: csr_do <= divisor;
				3'b010: csr_do <= {tx_event, rx_event, thre};
				3'b011: csr_do <= {thru_en, tx_irq_en, rx_irq_en};
				3'b100: csr_do <= {break_en};
			endcase
			if(csr_we) begin
				case(csr_a[2:0])
					3'b000:; /* handled by transceiver */
					3'b001: divisor <= csr_di[15:0];
					3'b010: begin
						/* write one to clear */
						if(csr_di[1])
							rx_event <= 1'b0;
						if(csr_di[2])
							tx_event <= 1'b0;
					end
					3'b011: begin
						rx_irq_en <= csr_di[0];
						tx_irq_en <= csr_di[1];
						thru_en <= csr_di[2];
					end
					3'b100: break_en <= csr_di[0];
				endcase
			end
		end
	end
end

endmodule
