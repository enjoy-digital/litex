/**
 *
 * Name:
 *   bp_cce_mmio_cfg_loader.v
 *
 * Description:
 *
 */

module bp_cce_mmio_cfg_loader
  import bp_common_pkg::*;
  import bp_common_aviary_pkg::*;
  import bp_cce_pkg::*;
  import bp_cfg_link_pkg::*;
  import bp_be_pkg::*;
  import bp_be_dcache_pkg::*;
  import bp_me_pkg::*;
  #(parameter bp_cfg_e cfg_p = e_bp_inv_cfg
    `declare_bp_proc_params(cfg_p)
    `declare_bp_me_if_widths(paddr_width_p, cce_block_width_p, num_lce_p, lce_assoc_p)

    , parameter inst_width_p          = "inv"
    , parameter inst_ram_addr_width_p = "inv"
    , parameter inst_ram_els_p        = "inv"
    , parameter cce_ucode_filename_p  = "/tmp/cce_ucode.mem"
    , parameter skip_ram_init_p       = 0
    
    , localparam bp_pc_entry_point_gp=39'h00_5000_0000 //SC_add
    )
  (input                                             clk_i
   , input                                           reset_i

   // Config channel
   , output logic [cce_mem_msg_width_lp-1:0]         mem_cmd_o
   , output logic                                    mem_cmd_v_o
   , input                                           mem_cmd_yumi_i

   // We don't need a response from the cfg network
   , input [cce_mem_msg_width_lp-1:0]                mem_resp_i
   , input                                           mem_resp_v_i
   , output                                          mem_resp_ready_o
   );

  wire unused0 = &{mem_resp_i, mem_resp_v_i};
  assign mem_resp_ready_o = 1'b1;
   
 `declare_bp_me_if(paddr_width_p, cce_block_width_p, num_lce_p, lce_assoc_p);

  bp_cce_mem_msg_s mem_cmd_cast_o;

  assign mem_cmd_o = mem_cmd_cast_o;
  
  logic [`bp_cce_inst_width-1:0]    cce_inst_boot_rom [0:inst_ram_els_p-1];
  logic [inst_ram_addr_width_p-1:0] cce_inst_boot_rom_addr;
  logic [`bp_cce_inst_width-1:0]    cce_inst_boot_rom_data;
  
  initial $readmemb(cce_ucode_filename_p, cce_inst_boot_rom);

  assign cce_inst_boot_rom_data = cce_inst_boot_rom[cce_inst_boot_rom_addr];

  logic                        cfg_v_lo;
  logic [cfg_core_width_p-1:0] cfg_core_lo;
  logic [cfg_addr_width_p-1:0] cfg_addr_lo;
  logic [cfg_data_width_p-1:0] cfg_data_lo;

  (* mark_debug = "true" *) enum logic [3:0] {
    RESET
    ,BP_RESET_SET
    ,BP_FREEZE_SET
    ,BP_RESET_CLR
    ,SEND_RAM_LO
    ,SEND_RAM_HI
    ,SEND_CCE_NORMAL
    ,SEND_ICACHE_NORMAL
    ,SEND_DCACHE_NORMAL
    ,SEND_PC_LO
    ,SEND_PC_HI
    ,BP_FREEZE_CLR
    ,DONE
  } state_n, state_r;

  logic [cfg_addr_width_p-1:0] ucode_cnt_r;
  logic ucode_cnt_clr, ucode_cnt_inc;
  bsg_counter_clear_up
   #(.max_val_p(2**cfg_addr_width_p-1)
     ,.init_val_p(0)
     )
   ucode_counter
    (.clk_i(clk_i)
     ,.reset_i(reset_i)

     ,.clear_i(ucode_cnt_clr)
     ,.up_i(ucode_cnt_inc & mem_cmd_yumi_i)

     ,.count_o(ucode_cnt_r)
     );

  wire ucode_prog_done = (ucode_cnt_r == cfg_addr_width_p'(inst_ram_els_p-1));

  always_ff @(posedge clk_i) 
    begin
      if (reset_i)
        state_r <= RESET;
      else if (mem_cmd_yumi_i || (state_r == RESET))
        state_r <= state_n;
    end

  wire [7:0] unused;
  assign {unused, cce_inst_boot_rom_addr} = cfg_addr_lo >> 1'b1;

  always_comb
    begin
      mem_cmd_v_o = cfg_v_lo;

      // uncached store
      mem_cmd_cast_o.msg_type      = e_cce_mem_uc_wr;
      mem_cmd_cast_o.addr          = bp_cfg_base_addr_gp;
      mem_cmd_cast_o.payload       = '0;
      mem_cmd_cast_o.size          = e_mem_size_8;
      mem_cmd_cast_o.data          = cce_block_width_p'({cfg_core_lo, cfg_addr_lo, cfg_data_lo});
    end

  always_comb 
    begin
      ucode_cnt_clr = 1'b0;
      ucode_cnt_inc = 1'b0;

      cfg_v_lo = '0;
      cfg_core_lo = 8'hff;
      cfg_addr_lo = '0;
      cfg_data_lo = '0;

      case (state_r)
        RESET: begin
          state_n = skip_ram_init_p ? BP_FREEZE_CLR : BP_RESET_SET;

          ucode_cnt_clr = 1'b1;
        end
        BP_RESET_SET: begin
          state_n = BP_FREEZE_SET;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = bp_cfg_reg_reset_gp;
          cfg_data_lo = cfg_data_width_p'(1);
        end
        BP_FREEZE_SET: begin
          state_n = BP_RESET_CLR;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = bp_cfg_reg_freeze_gp;
          cfg_data_lo = cfg_data_width_p'(1);
        end
        BP_RESET_CLR: begin
          state_n = SEND_RAM_LO;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = bp_cfg_reg_reset_gp;
          cfg_data_lo = cfg_data_width_p'(0);
        end
        SEND_RAM_LO: begin
          state_n = SEND_RAM_HI;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_mem_base_cce_ucode_gp) + (ucode_cnt_r << 1);
          cfg_data_lo = cce_inst_boot_rom_data[0+:cfg_data_width_p];
          // TODO: This is nonsynth, won't work on FPGA
          cfg_data_lo = (|cfg_data_lo === 'X) ? '0 : cfg_data_lo;
        end
        SEND_RAM_HI: begin
          state_n = ucode_prog_done ? SEND_CCE_NORMAL : SEND_RAM_LO;

          ucode_cnt_inc = 1'b1;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_mem_base_cce_ucode_gp) + (ucode_cnt_r << 1) + 1'b1;
          cfg_data_lo = cfg_data_width_p'(cce_inst_boot_rom_data[inst_width_p-1:cfg_data_width_p]);
          // TODO: This is nonsynth, won't work on FPGA
          cfg_data_lo = (|cfg_data_lo === 'X) ? '0 : cfg_data_lo;
        end
        SEND_CCE_NORMAL: begin
          state_n = SEND_ICACHE_NORMAL;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = bp_cfg_reg_cce_mode_gp;
          cfg_data_lo = cfg_data_width_p'(e_cce_mode_normal);
        end
        SEND_ICACHE_NORMAL: begin
          state_n = SEND_DCACHE_NORMAL;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_reg_icache_mode_gp);
          cfg_data_lo = cfg_data_width_p'(e_dcache_lce_mode_normal); // TODO: tapeout hack, change to icache
        end
        SEND_DCACHE_NORMAL: begin
          state_n = SEND_PC_LO;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_reg_dcache_mode_gp);
          cfg_data_lo = cfg_data_width_p'(e_dcache_lce_mode_normal);
        end
        SEND_PC_LO: begin
          state_n = SEND_PC_HI;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_reg_start_pc_lo_gp);
          cfg_data_lo = bp_pc_entry_point_gp[0+:cfg_data_width_p];
        end
        SEND_PC_HI: begin
          state_n = BP_FREEZE_CLR;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_reg_start_pc_hi_gp);
          cfg_data_lo = cfg_data_width_p'(bp_pc_entry_point_gp[vaddr_width_p-1:cfg_data_width_p]);
        end
        BP_FREEZE_CLR: begin
          state_n = DONE;

          cfg_v_lo = 1'b1;
          cfg_addr_lo = cfg_addr_width_p'(bp_cfg_reg_freeze_gp);
          cfg_data_lo = cfg_data_width_p'(0);;
        end
        DONE: begin
          state_n = DONE;
        end
        default: begin
          state_n = RESET;
        end
      endcase
    end

endmodule
