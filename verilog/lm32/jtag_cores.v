/*
 * Milkymist SoC
 * Copyright (c) 2010 Michael Walle
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. The name of the author may not be used to endorse or promote products
 *    derived from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE AUTHOR ``AS IS'' AND ANY EXPRESS OR
 * IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
 * OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
 * IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
 * NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 * DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 * THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 * (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
 * THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 */

module jtag_cores (
    input [7:0] reg_d,
    input [2:0] reg_addr_d,
    output reg_update,
    output [7:0] reg_q,
    output [2:0] reg_addr_q,
    output jtck,
    output jrstn
);

wire tck;
wire tdi;
wire tdo;
wire shift;
wire update;
wire reset;

jtag_tap jtag_tap (
	.tck(tck),
	.tdi(tdi),
	.tdo(tdo),
	.shift(shift),
	.update(update),
	.reset(reset)
);

reg [10:0] jtag_shift;
reg [10:0] jtag_latched;

always @(posedge tck or posedge reset)
begin
	if(reset)
		jtag_shift <= 11'b0;
	else begin
		if(shift)
			jtag_shift <= {tdi, jtag_shift[10:1]};
		else
			jtag_shift <= {reg_d, reg_addr_d};
	end
end

assign tdo = jtag_shift[0];

always @(posedge reg_update or posedge reset)
begin
	if(reset)
		jtag_latched <= 11'b0;
	else
		jtag_latched <= jtag_shift;
end

assign reg_update = update;
assign reg_q = jtag_latched[10:3];
assign reg_addr_q = jtag_latched[2:0];
assign jtck = tck;
assign jrstn = ~reset;

endmodule
