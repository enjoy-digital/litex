/*
* bsg_mem_1rw_sync_mask_write_bit.v
*
* distributed synchronous 1-port ram for xilinx ultrascale or ultrascale plus FPGA
* Write mode: No-change | Read mode: No-change
* Note:
* There are 2 basic BRAM library primitives, RAMB18E2 and RAMB36E2 in Vivado.
* But none of them support bit-wise mask. They have Byte-wide write enable ports though.
* So we use the RAM_STYLE attribute to instruct the tool to infer distributed LUT RAM instead.
*
* To save resources, the code is written to be inferred as Signle-port distributed ram RAM64X1S.
* https://www.xilinx.com/support/documentation/user_guides/ug574-ultrascale-clb.pdf
*
*/


module bsg_mem_1rw_sync_mask_write_bit #(
  parameter width_p = "inv"
  , parameter els_p = "inv"
  , parameter latch_last_read_p=0
  , parameter enable_clock_gating_p=0
  , localparam addr_width_lp = `BSG_SAFE_CLOG2(els_p)
) (
  input                      clk_i
  , input                      reset_i
  , input  [      width_p-1:0] data_i
  , input  [addr_width_lp-1:0] addr_i
  , input                      v_i
  , input  [      width_p-1:0] w_mask_i
  , input                      w_i
  , output [      width_p-1:0] data_o
);

  wire unused = reset_i;

  (* ram_style = "distributed" *) logic [width_p-1:0] mem [els_p-1:0];

  logic [width_p-1:0] data_r;
  always_ff @(posedge clk_i) begin
    if (v_i & ~w_i)
      data_r <= mem[addr_i];
  end

  assign data_o = data_r;

  for (genvar i=0; i<width_p; i=i+1) begin
    always_ff @(posedge clk_i) begin
      if (v_i)
        if (w_i & w_mask_i[i])
          mem[addr_i][i] <= data_i[i];
    end
  end

endmodule

