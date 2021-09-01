module DDR_INPUT(
 output reg o1,
 output reg o2,
 input i,
 input clk);

reg _o1, _o2;

always @ (posedge clk)
  begin
   o1 = _o1;
   o2 = _o2;
  end

always @ (posedge clk)
    begin
        _o1 = i;
    end

always @ (negedge clk)
    begin
        _o2 = i;
    end
endmodule
