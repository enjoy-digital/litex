/**
 * bp2wb_convertor.v
 * DESCRIPTION: THIS MODULE ADAPTS BP MEMORY BUS TO 64-BIT WISHBONE
 */

module bp2wb_convertor
  import bp_common_pkg::*;
  import bp_common_aviary_pkg::*;
  import bp_cce_pkg::*;
  import bp_me_pkg::*;
  #(parameter bp_params_e bp_params_p = e_bp_single_core_cfg
   `declare_bp_proc_params(bp_params_p)
   `declare_bp_me_if_widths(paddr_width_p, cce_block_width_p, lce_id_width_p, lce_assoc_p)

//   , parameter [paddr_width_p-1:0] dram_offset_p = '0
   , localparam num_block_words_lp   = cce_block_width_p / 64
   , localparam num_block_bytes_lp   = cce_block_width_p / 8
   , localparam num_word_bytes_lp    = dword_width_p / 8
   , localparam block_offset_bits_lp = `BSG_SAFE_CLOG2(num_block_bytes_lp)
   , localparam word_offset_bits_lp  = `BSG_SAFE_CLOG2(num_block_words_lp)
   , localparam byte_offset_bits_lp  = `BSG_SAFE_CLOG2(num_word_bytes_lp)
   , localparam wbone_data_width  = 64
   , localparam wbone_addr_ubound = paddr_width_p
   , localparam mem_granularity = 64 //TODO: adapt selection bit parametrized
   , localparam wbone_addr_lbound = 3 //`BSG_SAFE_CLOG2(wbone_data_width / mem_granularity) //dword granularity
   , localparam total_datafetch_cycle_lp   = cce_block_width_p / wbone_data_width
   , localparam total_datafetch_cycle_width = `BSG_SAFE_CLOG2(total_datafetch_cycle_lp)
   , localparam cached_addr_base =  32'h7000_0000//6000_0000 //32'h4000_4000//   
   )
  (                            input                                 clk_i
   ,(* mark_debug = "true" *)  input                               reset_i

   // BP side 
   ,(* mark_debug = "true" *)  input [cce_mem_msg_width_lp-1:0]    mem_cmd_i
   ,(* mark_debug = "true" *)  input                               mem_cmd_v_i
   ,(* mark_debug = "true" *)  output                              mem_cmd_ready_o

   ,                           output [cce_mem_msg_width_lp-1:0]   mem_resp_o
   , (* mark_debug = "true" *) output                              mem_resp_v_o
   , (* mark_debug = "true" *) input                               mem_resp_yumi_i

   // Wishbone side
   , (* mark_debug = "true" *) input [63:0]                        dat_i
   , (* mark_debug = "true" *) output logic [63:0]                 dat_o
   , (* mark_debug = "true" *) input                               ack_i
   , input                               err_i
//   , input                               rty_i
   , (* mark_debug = "true" *) output logic [wbone_addr_ubound-wbone_addr_lbound-1:0] adr_o//TODO: Double check!!!    
   , (* mark_debug = "true" *) output logic stb_o
   , output                              cyc_o
   , output [7:0]                        sel_o //TODO: double check!!!
   , (* mark_debug = "true" *) output                              we_o
   , output [2:0]                        cti_o //TODO: hardwire in Litex
   , output [1:0]                        bte_o //TODO: hardwire in Litex
 
   );

  `declare_bp_me_if(paddr_width_p, cce_block_width_p, lce_id_width_p, lce_assoc_p);
  
  //locals
 (* mark_debug = "true" *) logic  [total_datafetch_cycle_width:0] ack_ctr  = 0;
 (* mark_debug = "true" *) bp_cce_mem_msg_s  mem_cmd_cast_i, mem_resp_cast_o,  mem_cmd_debug, mem_cmd_debug2;
 (* mark_debug = "true" *) logic ready_li, v_li, stb_justgotack;
  (* mark_debug = "true" *) logic [cce_block_width_p-1:0] data_lo; 
  (* mark_debug = "true" *) logic  [cce_block_width_p-1:0] data_li;
  (* mark_debug = "true" *) wire [paddr_width_p-1:0]  mem_cmd_addr_l;
  (* mark_debug = "true" *) logic set_stb;


  //Handshaking between Wishbone and BlackParrot through convertor  
  //3.1.3:At every rising edge of [CLK_I] the terminating signal(ACK) is sampled.  If it
  //is asserted, then  [STB_O]  is  negated. 
  
  assign ready_li = ( ack_ctr == 0 ) & !set_stb & !mem_resp_v_o;
  assign mem_cmd_ready_o = ready_li;//!stb_o then ready to take!
 // assign v_li =  (ack_ctr == total_datafetch_cycle_lp-1);
  assign mem_resp_v_o =  v_li;
  assign stb_o = (set_stb) && !stb_justgotack; 
  assign cyc_o = stb_o; 
  assign sel_o = 8'b11111111; 
  assign cti_o = 0;
  assign bte_o = 0;

  initial begin
    ack_ctr = 0;
  end
  

//Flip stb after each ack--->RULE 3.20:
// Every time we get an ACK from WB, increment counter until the counter reaches to total_datafetch_cycle_lp
  always_ff @(posedge clk_i)
    begin
      
      if(reset_i)
      begin
        ack_ctr <= 0;
        set_stb <= 0;
        v_li <=0;
      end
//      else if (v_li)
//      begin
      else if (mem_resp_yumi_i)
        begin
          v_li <= 0;
          ack_ctr <= 0;
        end
//      end
      else if (mem_cmd_v_i)
      begin
        //data_li <= 0;
        set_stb <= 1;
        v_li <= 0;
        stb_justgotack <= 0;
      end
      
      else
      begin
        if (ack_i)//stb should be negated after ack
        begin
          stb_justgotack <= 1;
          data_li[(ack_ctr*wbone_data_width) +: wbone_data_width] <= dat_i;
          if ((ack_ctr == total_datafetch_cycle_lp-1) || (mem_cmd_addr_l < cached_addr_base && mem_cmd_r.header.msg_type == e_cce_mem_uc_wr )) //if uncached store, just one cycle is fine
          begin 
            v_li <=1;
            set_stb <= 0;
          end
          else 
            ack_ctr <= ack_ctr + 1; 
        end
        else
        begin
          stb_justgotack <= 0;
          v_li <=0;
        end
      end
    end

  //Packet Pass from BP to BP2WB
  assign mem_cmd_cast_i = mem_cmd_i;
   bp_cce_mem_msg_s mem_cmd_r;
   bsg_dff_reset_en
  #(.width_p(cce_mem_msg_width_lp))
    mshr_reg
     (.clk_i(clk_i)
      ,.reset_i(reset_i)
      ,.en_i(mem_cmd_v_i)//when
      ,.data_i(mem_cmd_i)
      ,.data_o(mem_cmd_r)
      );

 //Addr && Data && Command  Pass from BP2WB to WB 
  logic [wbone_addr_lbound-1:0] throw_away; 
  assign mem_cmd_addr_l =  mem_cmd_r.header.addr;
  assign data_lo = mem_cmd_r.data;
  logic [39:0] mem_cmd_addr_l_zero64;
  always_comb begin
    if( mem_cmd_addr_l < cached_addr_base )
    begin 
      adr_o = mem_cmd_addr_l[wbone_addr_ubound-1:wbone_addr_lbound];//no need to change address for uncached stores/loads
      dat_o = data_lo[(0*wbone_data_width) +: wbone_data_width];//unchached data is stored in LS 64bits
    end

    else
    begin
      mem_cmd_addr_l_zero64 = mem_cmd_addr_l >> 6 << 6;
      {adr_o,throw_away} =  mem_cmd_addr_l_zero64 + (ack_ctr*8);//TODO:careful
      dat_o = data_lo[(ack_ctr*wbone_data_width) +: wbone_data_width];
     end
  end

   assign we_o = (mem_cmd_r.header.msg_type inside {e_cce_mem_uc_wr, e_cce_mem_wr});

//Data Pass from BP2WB to BP

wire [cce_block_width_p-1:0]  rd_word_offset = mem_cmd_r.header.addr[3+:3];
//wire [cce_block_width_p-1:0]  rd_byte_offset = mem_cmd_r.addr[0+:3];
wire [cce_block_width_p-1:0]    rd_bit_shift = rd_word_offset*64; // We rely on receiver to adjust bits

(* mark_debug = "true" *) wire [cce_block_width_p-1:0] data_li_resp = (mem_cmd_r.header.msg_type == e_cce_mem_uc_rd)
                                            ? data_li >> rd_bit_shift
                                            : data_li;



assign mem_resp_cast_o = '{data     : data_li_resp
                                ,header :'{payload : mem_cmd_r.header.payload
                                ,size    : mem_cmd_r.header.size
                                ,addr    : mem_cmd_r.header.addr
                                ,msg_type: mem_cmd_r.header.msg_type
                                }
                                };
 
assign mem_resp_o = mem_resp_cast_o;

/*********************************************/
/*DEBUG SECTION*/
  


/*wire [3:0] fake_msg_type;
wire [10:0] fake_payload;
wire [2:0] fake_size;
wire [39:0] fake_addr;
assign fake_payload = mem_cmd_r.header.payload;
assign fake_size = mem_cmd_r.header.size;
assign fake_addr = mem_cmd_r.header.addr;
assign fake_msg_type = mem_cmd_r.header.msg_type;
*/
/*(* mark_debug = "true" *) logic debug_wire;
  initial begin
    debug_wire = 0;
  end

  assign mem_cmd_debug = mem_cmd_i;

always_ff @(posedge clk_i)
debug_wire <= (ack_i && mem_cmd_debug.header.addr >= 32'h80000000);

  always_ff @(posedge clk_i)
  begin
      if(mem_cmd_v_i && mem_cmd_debug.header.addr <= 32'h60000000)
      begin
        debug_wire <= 1;
//                $display("addr == %x", mem_cmd_debug.header.addr);
      end
/*      if (mem_resp_v_o && debug_ctr < 64 && mem_cmd_debug.header.addr >= 32'h80000000)
      begin
        debug_gotdata[((debug_ctr-1)*512) +: 512] <= data_li_resp;
        $display("data == %x", data_li_resp);
      end*/
//  end

wire [3:0] typean;
assign typean = mem_cmd_r.header.msg_type;

endmodule

