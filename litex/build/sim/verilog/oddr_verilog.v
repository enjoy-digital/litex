module DDR_OUTPUT(
    input i1,
    input i2,
    output o,
    input clk);

wire _o;
reg _i1, _i2;

assign o = _o;
assign _o = (clk) ? _i1 : _i2;

always @ (posedge clk)
    begin
        _i1 = i1;
        _i2 = i2;
    end

endmodule
