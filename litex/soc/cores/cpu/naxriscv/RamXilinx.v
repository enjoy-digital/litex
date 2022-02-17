
module Ram_1w_1rs #(
        parameter integer wordCount = 0,
        parameter integer wordWidth = 0,
        parameter clockCrossing = 1'b0,
        parameter technology = "auto",
        parameter readUnderWrite = "dontCare",
        parameter integer wrAddressWidth = 0,
        parameter integer wrDataWidth = 0,
        parameter integer wrMaskWidth = 0,
        parameter wrMaskEnable = 1'b0,
        parameter integer rdAddressWidth = 0,
        parameter integer rdDataWidth  = 0
    )(
        input wr_clk,
        input wr_en,
        input [wrMaskWidth-1:0] wr_mask,
        input [wrAddressWidth-1:0] wr_addr,
        input [wrDataWidth-1:0] wr_data,
        input rd_clk,
        input rd_en,
        input [rdAddressWidth-1:0] rd_addr,
        output [rdDataWidth-1:0] rd_data
    );

    reg [wrDataWidth-1:0] ram_block [(2**wrAddressWidth)-1:0];
    integer i;
    localparam COL_WIDTH = wrDataWidth/wrMaskWidth;
    always @ (posedge wr_clk) begin
        if(wr_en) begin
            for(i=0;i<wrMaskWidth;i=i+1) begin
                if(wr_mask[i]) begin
                    ram_block[wr_addr][i*COL_WIDTH +: COL_WIDTH] <= wr_data[i*COL_WIDTH +:COL_WIDTH];
                end
            end
        end
    end

    reg [rdDataWidth-1:0] ram_rd_data;
    always @ (posedge rd_clk) begin
        if(rd_en) begin
            ram_rd_data <= ram_block[rd_addr];
        end
    end
    assign rd_data = ram_rd_data;
endmodule
