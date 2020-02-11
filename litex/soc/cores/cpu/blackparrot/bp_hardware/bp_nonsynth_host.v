
module bp_nonsynth_host
 import bp_common_pkg::*;
 import bp_common_aviary_pkg::*;
 import bp_be_pkg::*;
 import bp_common_rv64_pkg::*;
 import bp_cce_pkg::*;
 import bsg_noc_pkg::*;
 import bp_cfg_link_pkg::*;
 #(parameter bp_cfg_e cfg_p = e_bp_inv_cfg
   `declare_bp_proc_params(cfg_p)
   `declare_bp_me_if_widths(paddr_width_p, cce_block_width_p, num_lce_p, lce_assoc_p)
   )
  (input clk_i
   , input reset_i

   , input [cce_mem_msg_width_lp-1:0]              mem_cmd_i
   , input                                         mem_cmd_v_i
   , output logic                                  mem_cmd_yumi_o

   , output logic [cce_mem_msg_width_lp-1:0]       mem_resp_o
   , output logic                                  mem_resp_v_o
   , input                                         mem_resp_ready_i

   , output [num_core_p-1:0]                       program_finish_o
   ,(* mark_debug = "true" *) output logic                                  all_finished_debug_o //SC_add
   , (* mark_debug = "true" *) output logic                                 core_passed_debug
   , (* mark_debug = "true" *) output logic                                 core_failed_debug
   );

`declare_bp_me_if(paddr_width_p, cce_block_width_p, num_lce_p, lce_assoc_p);

// HOST I/O mappings
//localparam host_dev_base_addr_gp     = 32'h03??_????;

// Host I/O mappings (arbitrarily decided for now)
//   Overall host controls 32'h0300_0000-32'h03FF_FFFF

localparam hprint_base_addr_gp = paddr_width_p'(32'h0300_0???);
localparam cprint_base_addr_gp = paddr_width_p'(64'h0300_1???);
localparam finish_base_addr_gp = paddr_width_p'(64'h0300_2???);

bp_cce_mem_msg_s  mem_cmd_cast_i;

assign mem_cmd_cast_i = mem_cmd_i;

localparam lg_num_core_lp = `BSG_SAFE_CLOG2(num_core_p);

logic hprint_data_cmd_v;
logic cprint_data_cmd_v;
logic finish_data_cmd_v;

always_comb
  begin
    hprint_data_cmd_v = 1'b0;
    cprint_data_cmd_v = 1'b0;
    finish_data_cmd_v = 1'b0;

    unique
    casez (mem_cmd_cast_i.addr)
      hprint_base_addr_gp: hprint_data_cmd_v = mem_cmd_v_i; 
      cprint_base_addr_gp: cprint_data_cmd_v = mem_cmd_v_i;
      finish_base_addr_gp: finish_data_cmd_v = mem_cmd_v_i;
      default: begin end
    endcase
  end

logic [num_core_p-1:0] hprint_w_v_li;
logic [num_core_p-1:0] cprint_w_v_li;
logic [num_core_p-1:0] finish_w_v_li;

// Memory-mapped I/O is 64 bit aligned
localparam byte_offset_width_lp = 3;
wire [lg_num_core_lp-1:0] mem_cmd_core_enc =
  mem_cmd_cast_i.addr[byte_offset_width_lp+:lg_num_core_lp];

bsg_decode_with_v
 #(.num_out_p(num_core_p))
 hprint_data_cmd_decoder
  (.v_i(hprint_data_cmd_v)
   ,.i(mem_cmd_core_enc)
   
   ,.o(hprint_w_v_li)
   );

bsg_decode_with_v
 #(.num_out_p(num_core_p))
 cprint_data_cmd_decoder
  (.v_i(cprint_data_cmd_v)
   ,.i(mem_cmd_core_enc)

   ,.o(cprint_w_v_li)
   );

bsg_decode_with_v
 #(.num_out_p(num_core_p))
 finish_data_cmd_decoder
  (.v_i(finish_data_cmd_v)
   ,.i(mem_cmd_core_enc)

   ,.o(finish_w_v_li)
   );

logic [num_core_p-1:0] finish_r;
bsg_dff_reset
 #(.width_p(num_core_p))
 finish_accumulator
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.data_i(finish_r | finish_w_v_li)
   ,.data_o(finish_r)
   );

logic all_finished_r;
bsg_dff_reset
 #(.width_p(1))
 all_finished_reg
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.data_i(&finish_r)
   ,.data_o(all_finished_r)
   );

assign program_finish_o = finish_r;

always_ff @(negedge clk_i)
  begin
    for (integer i = 0; i < num_core_p; i++)
      begin
        if (hprint_w_v_li[i] & mem_cmd_yumi_o)
          $display("[CORE%0x PRT] %x", i, mem_cmd_cast_i.data[0+:8]);
        if (cprint_w_v_li[i] & mem_cmd_yumi_o)
          $display("[CORE%0x PRT] %c", i, mem_cmd_cast_i.data[0+:8]);
        if (finish_w_v_li[i] & mem_cmd_yumi_o & ~mem_cmd_cast_i.data[0])
        begin
          $display("[CORE%0x FSH] PASS", i);
          core_passed_debug <= 1;
        end  
        if (finish_w_v_li[i] & mem_cmd_yumi_o &  mem_cmd_cast_i.data[0])
        begin
          $display("[CORE%0x FSH] FAIL", i);
          core_failed_debug <=1;
        end
      end

    if (all_finished_r)
      begin
        $display("All cores finished! Terminating...");
        $finish();
        all_finished_debug_o <= 1;
      end
    if (reset_i)
    begin
      all_finished_debug_o <= 0;
      core_passed_debug <= 0;
      core_failed_debug <= 0;
    end
  end
bp_cce_mem_msg_s mem_resp_lo;
logic mem_resp_v_lo, mem_resp_ready_lo;
assign mem_cmd_yumi_o = mem_cmd_v_i & mem_resp_ready_lo;
bsg_one_fifo
 #(.width_p(cce_mem_msg_width_lp))
 mem_resp_buffer
  (.clk_i(clk_i)
   ,.reset_i(reset_i)

   ,.data_i(mem_resp_lo)
   ,.v_i(mem_cmd_yumi_o)
   ,.ready_o(mem_resp_ready_lo)

   ,.data_o(mem_resp_o)
   ,.v_o(mem_resp_v_lo)
   ,.yumi_i(mem_resp_ready_i & mem_resp_v_lo)
   );
assign mem_resp_v_o = mem_resp_v_lo & mem_resp_ready_i;

assign mem_resp_lo =
  '{msg_type       : mem_cmd_cast_i.msg_type
    ,addr          : mem_cmd_cast_i.addr
    ,payload       : mem_cmd_cast_i.payload
    ,size          : mem_cmd_cast_i.size
    ,data          : '0
    };


endmodule : bp_nonsynth_host

