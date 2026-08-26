`define addrW 32
/*

This file has to remain empty, this is used by Silice RISC-V integration

*/

// SL 2019, MIT license
module M_rv32i_cpu__mem_xregsA(
input      [5-1:0]                in_xregsA_addr0,
output reg signed [32-1:0]     out_xregsA_rdata0,
output reg signed [32-1:0]     out_xregsA_rdata1,
input      [1-1:0]             in_xregsA_wenable1,
input      [32-1:0]                 in_xregsA_wdata1,
input      [5-1:0]                in_xregsA_addr1,
input      clock0,
input      clock1
);
reg signed [32-1:0] buffer[32-1:0];
always @(posedge clock0) begin
  out_xregsA_rdata0 <= buffer[in_xregsA_addr0];
end
always @(posedge clock1) begin
  if (in_xregsA_wenable1) begin
    buffer[in_xregsA_addr1] <= in_xregsA_wdata1;
  end
end
initial begin
 buffer[0] = 0;
end

endmodule

// SL 2019, MIT license
module M_rv32i_cpu__mem_xregsB(
input      [5-1:0]                in_xregsB_addr0,
output reg signed [32-1:0]     out_xregsB_rdata0,
output reg signed [32-1:0]     out_xregsB_rdata1,
input      [1-1:0]             in_xregsB_wenable1,
input      [32-1:0]                 in_xregsB_wdata1,
input      [5-1:0]                in_xregsB_addr1,
input      clock0,
input      clock1
);
reg signed [32-1:0] buffer[32-1:0];
always @(posedge clock0) begin
  out_xregsB_rdata0 <= buffer[in_xregsB_addr0];
end
always @(posedge clock1) begin
  if (in_xregsB_wenable1) begin
    buffer[in_xregsB_addr1] <= in_xregsB_wdata1;
  end
end
initial begin
 buffer[0] = 0;
end

endmodule


module M_decode__dec (
in_instr,
in_pc,
in_regA,
in_regB,
out_write_rd,
out_jump,
out_branch,
out_load_store,
out_store,
out_loadStoreOp,
out_aluOp,
out_sub,
out_signedShift,
out_pcOrReg,
out_regOrImm,
out_csr,
out_rd_enable,
out_aluA,
out_aluB,
out_imm,
out_clock,
clock
);
input  [31:0] in_instr;
input  [31:0] in_pc;
input signed [31:0] in_regA;
input signed [31:0] in_regB;
output  [4:0] out_write_rd;
output  [0:0] out_jump;
output  [0:0] out_branch;
output  [0:0] out_load_store;
output  [0:0] out_store;
output  [2:0] out_loadStoreOp;
output  [2:0] out_aluOp;
output  [0:0] out_sub;
output  [0:0] out_signedShift;
output  [0:0] out_pcOrReg;
output  [0:0] out_regOrImm;
output  [2:0] out_csr;
output  [0:0] out_rd_enable;
output signed [31:0] out_aluA;
output signed [31:0] out_aluB;
output signed [31:0] out_imm;
output out_clock;
input clock;
assign out_clock = clock;
wire signed [31:0] _w_imm_u;
wire signed [31:0] _w_imm_j;
wire signed [31:0] _w_imm_i;
wire signed [31:0] _w_imm_b;
wire signed [31:0] _w_imm_s;
wire  [4:0] _w_opcode;
wire  [0:0] _w_AUIPC;
wire  [0:0] _w_LUI;
wire  [0:0] _w_JAL;
wire  [0:0] _w_JALR;
wire  [0:0] _w_Branch;
wire  [0:0] _w_Load;
wire  [0:0] _w_Store;
wire  [0:0] _w_IntImm;
wire  [0:0] _w_IntReg;
wire  [0:0] _w_CSR;
wire  [0:0] _w_no_rd;

reg  [4:0] _d_write_rd;
reg  [4:0] _q_write_rd;
reg  [0:0] _d_jump;
reg  [0:0] _q_jump;
reg  [0:0] _d_branch;
reg  [0:0] _q_branch;
reg  [0:0] _d_load_store;
reg  [0:0] _q_load_store;
reg  [0:0] _d_store;
reg  [0:0] _q_store;
reg  [2:0] _d_loadStoreOp;
reg  [2:0] _q_loadStoreOp;
reg  [2:0] _d_aluOp;
reg  [2:0] _q_aluOp;
reg  [0:0] _d_sub;
reg  [0:0] _q_sub;
reg  [0:0] _d_signedShift;
reg  [0:0] _q_signedShift;
reg  [0:0] _d_pcOrReg;
reg  [0:0] _q_pcOrReg;
reg  [0:0] _d_regOrImm;
reg  [0:0] _q_regOrImm;
reg  [2:0] _d_csr;
reg  [2:0] _q_csr;
reg  [0:0] _d_rd_enable;
reg  [0:0] _q_rd_enable;
reg signed [31:0] _d_aluA;
reg signed [31:0] _q_aluA;
reg signed [31:0] _d_aluB;
reg signed [31:0] _q_aluB;
reg signed [31:0] _d_imm;
reg signed [31:0] _q_imm;
assign out_write_rd = _q_write_rd;
assign out_jump = _q_jump;
assign out_branch = _q_branch;
assign out_load_store = _q_load_store;
assign out_store = _q_store;
assign out_loadStoreOp = _q_loadStoreOp;
assign out_aluOp = _q_aluOp;
assign out_sub = _q_sub;
assign out_signedShift = _q_signedShift;
assign out_pcOrReg = _q_pcOrReg;
assign out_regOrImm = _q_regOrImm;
assign out_csr = _q_csr;
assign out_rd_enable = _q_rd_enable;
assign out_aluA = _q_aluA;
assign out_aluB = _q_aluB;
assign out_imm = _q_imm;


assign _w_imm_u = {in_instr[12+:20],12'b0};
assign _w_imm_j = {{12{in_instr[31+:1]}},in_instr[12+:8],in_instr[20+:1],in_instr[21+:10],1'b0};
assign _w_imm_i = {{20{in_instr[31+:1]}},in_instr[20+:12]};
assign _w_imm_b = {{20{in_instr[31+:1]}},in_instr[7+:1],in_instr[25+:6],in_instr[8+:4],1'b0};
assign _w_imm_s = {{20{in_instr[31+:1]}},in_instr[25+:7],in_instr[7+:5]};
assign _w_opcode = in_instr[2+:5];
assign _w_AUIPC = _w_opcode==5'b00101;
assign _w_LUI = _w_opcode==5'b01101;
assign _w_JAL = _w_opcode==5'b11011;
assign _w_JALR = _w_opcode==5'b11001;
assign _w_Branch = _w_opcode==5'b11000;
assign _w_Load = _w_opcode==5'b00000;
assign _w_Store = _w_opcode==5'b01000;
assign _w_IntImm = _w_opcode==5'b00100;
assign _w_IntReg = _w_opcode==5'b01100;
assign _w_CSR = _w_opcode==5'b11100;
assign _w_no_rd = (_w_Branch|_w_Store);

`ifdef FORMAL
initial begin
assume(reset);
end
`endif
always @* begin
_d_write_rd = _q_write_rd;
_d_jump = _q_jump;
_d_branch = _q_branch;
_d_load_store = _q_load_store;
_d_store = _q_store;
_d_loadStoreOp = _q_loadStoreOp;
_d_aluOp = _q_aluOp;
_d_sub = _q_sub;
_d_signedShift = _q_signedShift;
_d_pcOrReg = _q_pcOrReg;
_d_regOrImm = _q_regOrImm;
_d_csr = _q_csr;
_d_rd_enable = _q_rd_enable;
_d_aluA = _q_aluA;
_d_aluB = _q_aluB;
_d_imm = _q_imm;
// _always_pre
_d_jump = (_w_JAL|_w_JALR);
_d_branch = (_w_Branch);
_d_store = (_w_Store);
_d_load_store = (_w_Load|_w_Store);
_d_regOrImm = (_w_IntReg);
_d_aluOp = (_w_IntImm|_w_IntReg) ? {in_instr[12+:3]}:3'b000;
_d_sub = (_w_IntReg&in_instr[30+:1]);
_d_signedShift = _w_IntImm&in_instr[30+:1];
_d_loadStoreOp = in_instr[12+:3];
_d_csr = {_w_CSR,in_instr[20+:2]};
_d_write_rd = in_instr[7+:5];
_d_rd_enable = (_d_write_rd!=0)&~_w_no_rd;
_d_pcOrReg = (_w_AUIPC|_w_JAL|_w_Branch);
_d_aluA = (_w_LUI) ? 0:in_regA;
_d_aluB = in_regB;
// __block_1
  case (_w_opcode)
  5'b00101: begin
// __block_3_case
// __block_4
_d_imm = _w_imm_u;
// __block_5
  end
  5'b01101: begin
// __block_6_case
// __block_7
_d_imm = _w_imm_u;
// __block_8
  end
  5'b11011: begin
// __block_9_case
// __block_10
_d_imm = _w_imm_j;
// __block_11
  end
  5'b11000: begin
// __block_12_case
// __block_13
_d_imm = _w_imm_b;
// __block_14
  end
  5'b11001: begin
// __block_15_case
// __block_16
_d_imm = _w_imm_i;
// __block_17
  end
  5'b00000: begin
// __block_18_case
// __block_19
_d_imm = _w_imm_i;
// __block_20
  end
  5'b00100: begin
// __block_21_case
// __block_22
_d_imm = _w_imm_i;
// __block_23
  end
  5'b01000: begin
// __block_24_case
// __block_25
_d_imm = _w_imm_s;
// __block_26
  end
  default: begin
// __block_27_case
// __block_28
_d_imm = {32{1'bx}};
// __block_29
  end
endcase
// __block_2
// __block_30
// _always_post
end

always @(posedge clock) begin
_q_write_rd <= _d_write_rd;
_q_jump <= _d_jump;
_q_branch <= _d_branch;
_q_load_store <= _d_load_store;
_q_store <= _d_store;
_q_loadStoreOp <= _d_loadStoreOp;
_q_aluOp <= _d_aluOp;
_q_sub <= _d_sub;
_q_signedShift <= _d_signedShift;
_q_pcOrReg <= _d_pcOrReg;
_q_regOrImm <= _d_regOrImm;
_q_csr <= _d_csr;
_q_rd_enable <= _d_rd_enable;
_q_aluA <= _d_aluA;
_q_aluB <= _d_aluB;
_q_imm <= _d_imm;
end

endmodule


module M_intops__alu (
in_pc,
in_xa,
in_xb,
in_imm,
in_aluOp,
in_sub,
in_pcOrReg,
in_regOrImm,
in_signedShift,
in_csr,
in_cycle,
in_instret,
in_user_data,
in_ra,
in_rb,
in_funct3,
in_branch,
in_jump,
out_r,
out_j,
out_w,
out_clock,
clock
);
input  [31:0] in_pc;
input signed [31:0] in_xa;
input signed [31:0] in_xb;
input signed [31:0] in_imm;
input  [2:0] in_aluOp;
input  [0:0] in_sub;
input  [0:0] in_pcOrReg;
input  [0:0] in_regOrImm;
input  [0:0] in_signedShift;
input  [2:0] in_csr;
input  [31:0] in_cycle;
input  [31:0] in_instret;
input  [31:0] in_user_data;
input signed [31:0] in_ra;
input signed [31:0] in_rb;
input  [2:0] in_funct3;
input  [0:0] in_branch;
input  [0:0] in_jump;
output signed [31:0] out_r;
output  [0:0] out_j;
output signed [31:0] out_w;
output out_clock;
input clock;
assign out_clock = clock;
wire signed [31:0] _w_a;
wire signed [31:0] _w_b;

reg signed [31:0] _d_r;
reg signed [31:0] _q_r;
reg  [0:0] _d_j;
reg  [0:0] _q_j;
reg signed [31:0] _d_w;
reg signed [31:0] _q_w;
assign out_r = _q_r;
assign out_j = _q_j;
assign out_w = _q_w;


assign _w_a = in_pcOrReg ? $signed({1'b0,in_pc[0+:32]}):in_xa;
assign _w_b = in_regOrImm ? (in_xb):in_imm;

`ifdef FORMAL
initial begin
assume(reset);
end
`endif
always @* begin
_d_r = _q_r;
_d_j = _q_j;
_d_w = _q_w;
// _always_pre
// __block_1
  case ({in_aluOp})
  3'b000: begin
// __block_3_case
// __block_4
_d_r = in_sub ? (_w_a-_w_b):(_w_a+_w_b);
// __block_5
  end
  3'b010: begin
// __block_6_case
// __block_7
if ($signed(in_xa)<$signed(_w_b)) begin
// __block_8
// __block_10
_d_r = 32'b1;
// __block_11
end else begin
// __block_9
// __block_12
_d_r = 32'b0;
// __block_13
end
// __block_14
// __block_15
  end
  3'b011: begin
// __block_16_case
// __block_17
if ($unsigned(in_xa)<$unsigned(_w_b)) begin
// __block_18
// __block_20
_d_r = 32'b1;
// __block_21
end else begin
// __block_19
// __block_22
_d_r = 32'b0;
// __block_23
end
// __block_24
// __block_25
  end
  3'b100: begin
// __block_26_case
// __block_27
_d_r = in_xa^_w_b;
// __block_28
  end
  3'b110: begin
// __block_29_case
// __block_30
_d_r = in_xa|_w_b;
// __block_31
  end
  3'b111: begin
// __block_32_case
// __block_33
_d_r = in_xa&_w_b;
// __block_34
  end
  3'b001: begin
// __block_35_case
// __block_36
_d_r = (in_xa<<<_w_b[0+:5]);
// __block_37
  end
  3'b101: begin
// __block_38_case
// __block_39
_d_r = in_signedShift ? (in_xa>>>_w_b[0+:5]):(in_xa>>_w_b[0+:5]);
// __block_40
  end
  default: begin
// __block_41_case
// __block_42
_d_r = {32{1'bx}};
// __block_43
  end
endcase
// __block_2
if (in_csr[2+:1]) begin
// __block_44
// __block_46
  case (in_csr[0+:2])
  2'b00: begin
// __block_48_case
// __block_49
_d_r = in_cycle;
// __block_50
  end
  2'b01: begin
// __block_51_case
// __block_52
_d_r = in_user_data;
// __block_53
  end
  2'b10: begin
// __block_54_case
// __block_55
_d_r = in_instret;
// __block_56
  end
  default: begin
// __block_57_case
// __block_58
_d_r = {32{1'bx}};
// __block_59
  end
endcase
// __block_47
// __block_60
end else begin
// __block_45
end
// __block_61
  case (in_funct3)
  3'b000: begin
// __block_63_case
// __block_64
_d_j = in_jump|(in_branch&(in_ra==in_rb));
// __block_65
  end
  3'b001: begin
// __block_66_case
// __block_67
_d_j = in_jump|(in_branch&(in_ra!=in_rb));
// __block_68
  end
  3'b100: begin
// __block_69_case
// __block_70
_d_j = in_jump|(in_branch&($signed(in_ra)<$signed(in_rb)));
// __block_71
  end
  3'b110: begin
// __block_72_case
// __block_73
_d_j = in_jump|(in_branch&($unsigned(in_ra)<$unsigned(in_rb)));
// __block_74
  end
  3'b101: begin
// __block_75_case
// __block_76
_d_j = in_jump|(in_branch&($signed(in_ra)>=$signed(in_rb)));
// __block_77
  end
  3'b111: begin
// __block_78_case
// __block_79
_d_j = in_jump|(in_branch&($unsigned(in_ra)>=$unsigned(in_rb)));
// __block_80
  end
  default: begin
// __block_81_case
// __block_82
_d_j = in_jump;
// __block_83
  end
endcase
// __block_62
// __block_84
// _always_post
end

always @(posedge clock) begin
_q_r <= _d_r;
_q_j <= _d_j;
_q_w <= _d_w;
end

endmodule

module M_rv32i_cpu (
in_boot_at,
in_user_data,
in_ram_data_out,
in_ram_done,
out_ram_addr,
out_ram_rw,
out_ram_wmask,
out_ram_data_in,
out_ram_in_valid,
out_predicted_addr,
out_predicted_correct,
in_run,
out_done,
reset,
out_clock,
clock
);
input  [31:0] in_boot_at;
input  [31:0] in_user_data;
input  [32-1:0] in_ram_data_out;
input  [1-1:0] in_ram_done;
output  [32-1:0] out_ram_addr;
output  [1-1:0] out_ram_rw;
output  [4-1:0] out_ram_wmask;
output  [32-1:0] out_ram_data_in;
output  [1-1:0] out_ram_in_valid;
output  [31:0] out_predicted_addr;
output  [0:0] out_predicted_correct;
input in_run;
output out_done;
input reset;
output out_clock;
input clock;
assign out_clock = clock;
wire  [4:0] _w_dec_write_rd;
wire  [0:0] _w_dec_jump;
wire  [0:0] _w_dec_branch;
wire  [0:0] _w_dec_load_store;
wire  [0:0] _w_dec_store;
wire  [2:0] _w_dec_loadStoreOp;
wire  [2:0] _w_dec_aluOp;
wire  [0:0] _w_dec_sub;
wire  [0:0] _w_dec_signedShift;
wire  [0:0] _w_dec_pcOrReg;
wire  [0:0] _w_dec_regOrImm;
wire  [2:0] _w_dec_csr;
wire  [0:0] _w_dec_rd_enable;
wire signed [31:0] _w_dec_aluA;
wire signed [31:0] _w_dec_aluB;
wire signed [31:0] _w_dec_imm;
wire signed [31:0] _w_alu_r;
wire  [0:0] _w_alu_j;
wire signed [31:0] _w_alu_w;
wire signed [31:0] _w_mem_xregsA_rdata0;
wire signed [31:0] _w_mem_xregsB_rdata0;
wire  [0:0] _c_dry_resume;
assign _c_dry_resume = 0;
reg  [3:0] _t_state;
wire  [31:0] _w_next_pc_p4;
wire  [31:0] _w_next_pc_p8;
wire  [2:0] _w_funct3;
wire  [0:0] _w___block_1_alu_wait;
wire  [4:0] _w___block_10_offset;
wire  [4:0] _w___block_10_signB;
wire  [4:0] _w___block_10_signH;

reg  [4:0] _d_xregsA_addr0 = 0;
reg  [4:0] _q_xregsA_addr0 = 0;
reg  [0:0] _d_xregsA_wenable1 = 0;
reg  [0:0] _q_xregsA_wenable1 = 0;
reg signed [31:0] _d_xregsA_wdata1 = 0;
reg signed [31:0] _q_xregsA_wdata1 = 0;
reg  [4:0] _d_xregsA_addr1 = 0;
reg  [4:0] _q_xregsA_addr1 = 0;
reg  [4:0] _d_xregsB_addr0 = 0;
reg  [4:0] _q_xregsB_addr0 = 0;
reg  [0:0] _d_xregsB_wenable1 = 0;
reg  [0:0] _q_xregsB_wenable1 = 0;
reg signed [31:0] _d_xregsB_wdata1 = 0;
reg signed [31:0] _q_xregsB_wdata1 = 0;
reg  [4:0] _d_xregsB_addr1 = 0;
reg  [4:0] _q_xregsB_addr1 = 0;
reg  [0:0] _d_instr_ready = 0;
reg  [0:0] _q_instr_ready = 0;
reg  [31:0] _d_instr = 0;
reg  [31:0] _q_instr = 0;
reg  [31:0] _d_pc = 0;
reg  [31:0] _q_pc = 0;
reg  [31:0] _d_next_instr = 0;
reg  [31:0] _q_next_instr = 0;
reg  [31:0] _d_next_pc = 0;
reg  [31:0] _q_next_pc = 0;
reg  [0:0] _d_saved_store;
reg  [0:0] _q_saved_store;
reg  [2:0] _d_saved_loadStoreOp;
reg  [2:0] _q_saved_loadStoreOp;
reg  [1:0] _d_saved_loadStoreAlign;
reg  [1:0] _q_saved_loadStoreAlign;
reg  [0:0] _d_saved_rd_enable;
reg  [0:0] _q_saved_rd_enable;
reg  [31:0] _d_refetch_addr;
reg  [31:0] _q_refetch_addr;
reg  [0:0] _d_refetch_rw = 0;
reg  [0:0] _q_refetch_rw = 0;
reg signed [31:0] _d_regA;
reg signed [31:0] _q_regA;
reg signed [31:0] _d_regB;
reg signed [31:0] _q_regB;
reg  [31:0] _d_cycle = 0;
reg  [31:0] _q_cycle = 0;
reg  [31:0] _d_instret = 0;
reg  [31:0] _q_instret = 0;
reg  [0:0] _d_refetch;
reg  [0:0] _q_refetch;
reg  [0:0] _d_wait_next_instr;
reg  [0:0] _q_wait_next_instr;
reg  [0:0] _d_commit_decode;
reg  [0:0] _q_commit_decode;
reg  [0:0] _d_do_load_store;
reg  [0:0] _q_do_load_store;
reg  [0:0] _d_start;
reg  [0:0] _q_start;
reg  [31:0] _d___block_10_tmp;
reg  [31:0] _q___block_10_tmp;
reg  [32-1:0] _d_ram_addr;
reg  [32-1:0] _q_ram_addr;
reg  [1-1:0] _d_ram_rw;
reg  [1-1:0] _q_ram_rw;
reg  [4-1:0] _d_ram_wmask;
reg  [4-1:0] _q_ram_wmask;
reg  [32-1:0] _d_ram_data_in;
reg  [32-1:0] _q_ram_data_in;
reg  [1-1:0] _d_ram_in_valid;
reg  [1-1:0] _q_ram_in_valid;
reg  [31:0] _d_predicted_addr;
reg  [31:0] _q_predicted_addr;
reg  [0:0] _d_predicted_correct;
reg  [0:0] _q_predicted_correct;
assign out_ram_addr = _q_ram_addr;
assign out_ram_rw = _q_ram_rw;
assign out_ram_wmask = _q_ram_wmask;
assign out_ram_data_in = _q_ram_data_in;
assign out_ram_in_valid = _q_ram_in_valid;
assign out_predicted_addr = _q_predicted_addr;
assign out_predicted_correct = _q_predicted_correct;
assign out_done = 0;
M_decode__dec dec (
.in_instr(_d_instr),
.in_pc(_d_pc),
.in_regA(_d_regA),
.in_regB(_d_regB),
.out_write_rd(_w_dec_write_rd),
.out_jump(_w_dec_jump),
.out_branch(_w_dec_branch),
.out_load_store(_w_dec_load_store),
.out_store(_w_dec_store),
.out_loadStoreOp(_w_dec_loadStoreOp),
.out_aluOp(_w_dec_aluOp),
.out_sub(_w_dec_sub),
.out_signedShift(_w_dec_signedShift),
.out_pcOrReg(_w_dec_pcOrReg),
.out_regOrImm(_w_dec_regOrImm),
.out_csr(_w_dec_csr),
.out_rd_enable(_w_dec_rd_enable),
.out_aluA(_w_dec_aluA),
.out_aluB(_w_dec_aluB),
.out_imm(_w_dec_imm),
.clock(clock));
M_intops__alu alu (
.in_pc(_q_pc),
.in_xa(_w_dec_aluA),
.in_xb(_w_dec_aluB),
.in_imm(_w_dec_imm),
.in_aluOp(_w_dec_aluOp),
.in_sub(_w_dec_sub),
.in_pcOrReg(_w_dec_pcOrReg),
.in_regOrImm(_w_dec_regOrImm),
.in_signedShift(_w_dec_signedShift),
.in_csr(_w_dec_csr),
.in_cycle(_q_cycle),
.in_instret(_q_instret),
.in_user_data(in_user_data),
.in_ra(_q_regA),
.in_rb(_q_regB),
.in_funct3(_w_funct3),
.in_branch(_w_dec_branch),
.in_jump(_w_dec_jump),
.out_r(_w_alu_r),
.out_j(_w_alu_j),
.out_w(_w_alu_w),
.clock(clock));

M_rv32i_cpu__mem_xregsA __mem__xregsA(
.clock0(clock),
.clock1(clock),
.in_xregsA_addr0(_d_xregsA_addr0),
.in_xregsA_wenable1(_d_xregsA_wenable1),
.in_xregsA_wdata1(_d_xregsA_wdata1),
.in_xregsA_addr1(_d_xregsA_addr1),
.out_xregsA_rdata0(_w_mem_xregsA_rdata0)
);
M_rv32i_cpu__mem_xregsB __mem__xregsB(
.clock0(clock),
.clock1(clock),
.in_xregsB_addr0(_d_xregsB_addr0),
.in_xregsB_wenable1(_d_xregsB_wenable1),
.in_xregsB_wdata1(_d_xregsB_wdata1),
.in_xregsB_addr1(_d_xregsB_addr1),
.out_xregsB_rdata0(_w_mem_xregsB_rdata0)
);

assign _w_next_pc_p4 = _q_next_pc+4;
assign _w_next_pc_p8 = _q_next_pc+8;
assign _w_funct3 = _q_instr[12+:3];
assign _w___block_1_alu_wait = 0;
assign _w___block_10_offset = {_q_saved_loadStoreAlign,3'b000};
assign _w___block_10_signB = _w___block_10_offset|5'b00111;
assign _w___block_10_signH = _w___block_10_offset|5'b01111;

`ifdef FORMAL
initial begin
assume(reset);
end
`endif
always @* begin
_d_xregsA_addr0 = _q_xregsA_addr0;
_d_xregsA_wenable1 = _q_xregsA_wenable1;
_d_xregsA_wdata1 = _q_xregsA_wdata1;
_d_xregsA_addr1 = _q_xregsA_addr1;
_d_xregsB_addr0 = _q_xregsB_addr0;
_d_xregsB_wenable1 = _q_xregsB_wenable1;
_d_xregsB_wdata1 = _q_xregsB_wdata1;
_d_xregsB_addr1 = _q_xregsB_addr1;
_d_instr_ready = _q_instr_ready;
_d_instr = _q_instr;
_d_pc = _q_pc;
_d_next_instr = _q_next_instr;
_d_next_pc = _q_next_pc;
_d_saved_store = _q_saved_store;
_d_saved_loadStoreOp = _q_saved_loadStoreOp;
_d_saved_loadStoreAlign = _q_saved_loadStoreAlign;
_d_saved_rd_enable = _q_saved_rd_enable;
_d_refetch_addr = _q_refetch_addr;
_d_refetch_rw = _q_refetch_rw;
_d_regA = _q_regA;
_d_regB = _q_regB;
_d_cycle = _q_cycle;
_d_instret = _q_instret;
_d_refetch = _q_refetch;
_d_wait_next_instr = _q_wait_next_instr;
_d_commit_decode = _q_commit_decode;
_d_do_load_store = _q_do_load_store;
_d_start = _q_start;
_d___block_10_tmp = _q___block_10_tmp;
_d_ram_addr = _q_ram_addr;
_d_ram_rw = _q_ram_rw;
_d_ram_wmask = _q_ram_wmask;
_d_ram_data_in = _q_ram_data_in;
_d_ram_in_valid = _q_ram_in_valid;
_d_predicted_addr = _q_predicted_addr;
_d_predicted_correct = _q_predicted_correct;
// _always_pre
_d_ram_in_valid = 0;
// __block_1
_t_state = {_q_refetch&(in_ram_done|_q_start),~_q_refetch&_q_do_load_store&in_ram_done,(_q_wait_next_instr)&(in_ram_done|_c_dry_resume),_q_commit_decode&~_w___block_1_alu_wait};
  case (_t_state)
  8: begin
// __block_3_case
// __block_4
_d_refetch = 0;
_d_next_instr = in_ram_data_out;
_d_xregsA_addr0 = _d_next_instr[15+:5];
_d_xregsB_addr0 = _d_next_instr[20+:5];
_d_predicted_correct = _q_instr_ready;
_d_predicted_addr = _w_next_pc_p4;
_d_ram_addr = _q_start ? in_boot_at:_q_refetch_addr;
_d_next_pc = _q_start ? in_boot_at:_q_next_pc;
_d_start = reset;
_d_ram_rw = _q_refetch_rw;
_d_ram_in_valid = ~reset;
_d_instr_ready = _q_do_load_store;
_d_wait_next_instr = ~_q_do_load_store;
// __block_5
  end
  4: begin
// __block_6_case
// __block_7
_d_do_load_store = 0;
if (~_q_saved_store) begin
// __block_8
// __block_10
  case (_q_saved_loadStoreOp[0+:2])
  2'b00: begin
// __block_12_case
// __block_13
_d___block_10_tmp = {{24{(~_q_saved_loadStoreOp[2+:1])&in_ram_data_out[_w___block_10_signB+:1]}},in_ram_data_out[_w___block_10_offset+:8]};
// __block_14
  end
  2'b01: begin
// __block_15_case
// __block_16
_d___block_10_tmp = {{16{(~_q_saved_loadStoreOp[2+:1])&in_ram_data_out[_w___block_10_signH+:1]}},in_ram_data_out[_w___block_10_offset+:16]};
// __block_17
  end
  2'b10: begin
// __block_18_case
// __block_19
_d___block_10_tmp = in_ram_data_out;
// __block_20
  end
  default: begin
// __block_21_case
// __block_22
_d___block_10_tmp = 0;
// __block_23
  end
endcase
// __block_11
_d_xregsA_wenable1 = _q_saved_rd_enable;
_d_xregsB_wenable1 = _q_saved_rd_enable;
_d_xregsA_wdata1 = _d___block_10_tmp;
_d_xregsB_wdata1 = _d___block_10_tmp;
// __block_24
end else begin
// __block_9
end
// __block_25
_d_ram_addr = _w_next_pc_p4;
if ((_q_next_instr[15+:5]==_q_xregsA_addr1||_q_next_instr[20+:5]==_q_xregsB_addr1||_q_instr[15+:5]==_q_xregsA_addr1||_q_instr[20+:5]==_q_xregsB_addr1)&_q_saved_rd_enable) begin
// __block_26
// __block_28
_d_refetch = 1;
_d_refetch_addr = _q_pc;
_d_next_pc = _q_pc;
_d_instr_ready = 0;
// __block_29
end else begin
// __block_27
// __block_30
_d_commit_decode = 1;
// __block_31
end
// __block_32
_d_ram_in_valid = 1;
_d_ram_rw = 0;
_d_predicted_addr = _w_next_pc_p8;
_d_predicted_correct = 1;
// __block_33
  end
  2: begin
// __block_34_case
// __block_35
_d_wait_next_instr = 0;
_d_next_instr = in_ram_data_out;
_d_xregsA_addr0 = _d_next_instr[15+:5];
_d_xregsB_addr0 = _d_next_instr[20+:5];
_d_commit_decode = 1;
_d_predicted_correct = 1;
_d_ram_addr = _w_next_pc_p4;
_d_ram_in_valid = 1;
_d_ram_rw = 0;
// __block_36
  end
  1: begin
// __block_37_case
// __block_38
_d_commit_decode = 0;
_d_do_load_store = _q_instr_ready&_w_dec_load_store;
_d_saved_store = _w_dec_store;
_d_saved_loadStoreOp = _w_dec_loadStoreOp;
_d_saved_loadStoreAlign = _w_alu_r[0+:2];
_d_saved_rd_enable = _w_dec_rd_enable;
_d_refetch = _q_instr_ready&(_w_alu_j|_w_dec_load_store);
_d_refetch_addr = _w_alu_r;
_d_refetch_rw = _w_dec_load_store&_w_dec_store;
_d_predicted_addr = _d_refetch ? _w_alu_r[0+:32]:_w_next_pc_p8;
_d_predicted_correct = 1;
_d_wait_next_instr = (~_d_refetch&~_d_do_load_store)|~_q_instr_ready;
  case (_w_dec_loadStoreOp)
  3'b000: begin
// __block_40_case
// __block_41
  case (_w_alu_r[0+:2])
  2'b00: begin
// __block_43_case
// __block_44
_d_ram_data_in[0+:8] = _q_regB[0+:8];
_d_ram_wmask = 4'b0001;
// __block_45
  end
  2'b01: begin
// __block_46_case
// __block_47
_d_ram_data_in[8+:8] = _q_regB[0+:8];
_d_ram_wmask = 4'b0010;
// __block_48
  end
  2'b10: begin
// __block_49_case
// __block_50
_d_ram_data_in[16+:8] = _q_regB[0+:8];
_d_ram_wmask = 4'b0100;
// __block_51
  end
  2'b11: begin
// __block_52_case
// __block_53
_d_ram_data_in[24+:8] = _q_regB[0+:8];
_d_ram_wmask = 4'b1000;
// __block_54
  end
endcase
// __block_42
// __block_55
  end
  3'b001: begin
// __block_56_case
// __block_57
  case (_w_alu_r[1+:1])
  1'b0: begin
// __block_59_case
// __block_60
_d_ram_data_in[0+:16] = _q_regB[0+:16];
_d_ram_wmask = 4'b0011;
// __block_61
  end
  1'b1: begin
// __block_62_case
// __block_63
_d_ram_data_in[16+:16] = _q_regB[0+:16];
_d_ram_wmask = 4'b1100;
// __block_64
  end
endcase
// __block_58
// __block_65
  end
  3'b010: begin
// __block_66_case
// __block_67
_d_ram_data_in = _q_regB;
_d_ram_wmask = 4'b1111;
// __block_68
  end
  default: begin
// __block_69_case
// __block_70
_d_ram_data_in = 0;
// __block_71
  end
endcase
// __block_39
_d_xregsA_wdata1 = _w_alu_j ? _q_next_pc:_w_alu_r;
_d_xregsB_wdata1 = _w_alu_j ? _q_next_pc:_w_alu_r;
_d_xregsA_addr1 = _w_dec_write_rd;
_d_xregsB_addr1 = _w_dec_write_rd;
_d_xregsA_wenable1 = _q_instr_ready&(~_d_refetch|_w_dec_jump)&_w_dec_rd_enable;
_d_xregsB_wenable1 = _q_instr_ready&(~_d_refetch|_w_dec_jump)&_w_dec_rd_enable;
_d_instr = _q_next_instr;
_d_pc = _q_next_pc;
_d_next_pc = (_w_alu_j&_q_instr_ready) ? _d_refetch_addr:_w_next_pc_p4;
_d_regA = ((_q_xregsA_addr0==_d_xregsA_addr1)&_d_xregsA_wenable1) ? _d_xregsA_wdata1:_w_mem_xregsA_rdata0;
_d_regB = ((_q_xregsB_addr0==_d_xregsB_addr1)&_d_xregsB_wenable1) ? _d_xregsB_wdata1:_w_mem_xregsB_rdata0;
if (_q_instr_ready) begin
// __block_72
// __block_74
_d_instret = _q_instret+1;
// __block_75
end else begin
// __block_73
end
// __block_76
_d_instr_ready = 1;
// __block_77
  end
endcase
// __block_2
_d_cycle = _q_cycle+1;
// __block_78
// _always_post
end

always @(posedge clock) begin
_q_xregsA_addr0 <= _d_xregsA_addr0;
_q_xregsA_wenable1 <= _d_xregsA_wenable1;
_q_xregsA_wdata1 <= _d_xregsA_wdata1;
_q_xregsA_addr1 <= _d_xregsA_addr1;
_q_xregsB_addr0 <= _d_xregsB_addr0;
_q_xregsB_wenable1 <= _d_xregsB_wenable1;
_q_xregsB_wdata1 <= _d_xregsB_wdata1;
_q_xregsB_addr1 <= _d_xregsB_addr1;
_q_instr_ready <= _d_instr_ready;
_q_instr <= _d_instr;
_q_pc <= _d_pc;
_q_next_instr <= _d_next_instr;
_q_next_pc <= _d_next_pc;
_q_saved_store <= _d_saved_store;
_q_saved_loadStoreOp <= _d_saved_loadStoreOp;
_q_saved_loadStoreAlign <= _d_saved_loadStoreAlign;
_q_saved_rd_enable <= _d_saved_rd_enable;
_q_refetch_addr <= _d_refetch_addr;
_q_refetch_rw <= _d_refetch_rw;
_q_regA <= _d_regA;
_q_regB <= _d_regB;
_q_cycle <= _d_cycle;
_q_instret <= _d_instret;
_q_refetch <= (reset) ? 1 : _d_refetch;
_q_wait_next_instr <= (reset) ? 0 : _d_wait_next_instr;
_q_commit_decode <= (reset) ? 0 : _d_commit_decode;
_q_do_load_store <= (reset) ? 0 : _d_do_load_store;
_q_start <= (reset) ? 1 : _d_start;
_q___block_10_tmp <= _d___block_10_tmp;
_q_ram_addr <= (reset) ? 0 : _d_ram_addr;
_q_ram_rw <= (reset) ? 0 : _d_ram_rw;
_q_ram_wmask <= (reset) ? 0 : _d_ram_wmask;
_q_ram_data_in <= (reset) ? 0 : _d_ram_data_in;
_q_ram_in_valid <= (reset) ? 0 : _d_ram_in_valid;
_q_predicted_addr <= _d_predicted_addr;
_q_predicted_correct <= _d_predicted_correct;
end

endmodule

