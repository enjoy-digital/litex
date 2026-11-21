// ----------------------------------------------------------------------------
// Copyright (c) 2020-2024 RISC-V Steel contributors
//
// This work is licensed under the MIT License, see LICENSE file for details.
// SPDX-License-Identifier: MIT
// ----------------------------------------------------------------------------

module rvsteel_core #(

  parameter     [31:0]  BOOT_ADDRESS = 32'h00000000

  ) (

  // Global signals

  input  wire           clock,
  input  wire           reset,
  input  wire           halt,

  // IO interface

  output wire   [31:0]  rw_address,
  input  wire   [31:0]  read_data,
  output wire           read_request,
  input  wire           read_response,
  output wire   [31:0]  write_data,
  output wire   [3:0 ]  write_strobe,
  output wire           write_request,
  input  wire           write_response,

  // Interrupt signals (hardwire inputs to zero if unused)

  input  wire           irq_external,
  output wire           irq_external_response,
  input  wire           irq_timer,
  output wire           irq_timer_response,
  input  wire           irq_software,
  output wire           irq_software_response,
  input  wire   [15:0]  irq_fast,
  output wire   [15:0]  irq_fast_response,

  // Real Time Clock (hardwire to zero if unused)

  input  wire   [63:0]  real_time_clock

  );

  //-----------------------------------------------------------------------------------------------//
  // Constants                                                                                     //
  //-----------------------------------------------------------------------------------------------//

  // Address of Machine Information CSRs

  localparam MARCHID              = 12'hF12;
  localparam MIMPID               = 12'hF13;

  // Address of Performance Counters CSRs

  localparam CYCLE                = 12'hC00;
  localparam TIME                 = 12'hC01;
  localparam INSTRET              = 12'hC02;
  localparam CYCLEH               = 12'hC80;
  localparam TIMEH                = 12'hC81;
  localparam INSTRETH             = 12'hC82;

  // Address of Machine Trap Setup CSRs

  localparam MSTATUS              = 12'h300;
  localparam MSTATUSH             = 12'h310;
  localparam MISA                 = 12'h301;
  localparam MIE                  = 12'h304;
  localparam MTVEC                = 12'h305;

  // Address of Machine Trap Handling CSRs

  localparam MSCRATCH             = 12'h340;
  localparam MEPC                 = 12'h341;
  localparam MCAUSE               = 12'h342;
  localparam MTVAL                = 12'h343;
  localparam MIP                  = 12'h344;

  // Address of Machine Performance Counters CSRs

  localparam MCYCLE               = 12'hB00;
  localparam MINSTRET             = 12'hB02;
  localparam MCYCLEH              = 12'hB80;
  localparam MINSTRETH            = 12'hB82;

  // Writeback Mux selection

  localparam WB_ALU               = 3'b000;
  localparam WB_LOAD_UNIT         = 3'b001;
  localparam WB_UPPER_IMM         = 3'b010;
  localparam WB_TARGET_ADDER      = 3'b011;
  localparam WB_CSR               = 3'b100;
  localparam WB_PC_PLUS_4         = 3'b101;

  // Immediate format selection

  localparam I_TYPE_IMMEDIATE     = 3'b001;
  localparam S_TYPE_IMMEDIATE     = 3'b010;
  localparam B_TYPE_IMMEDIATE     = 3'b011;
  localparam U_TYPE_IMMEDIATE     = 3'b100;
  localparam J_TYPE_IMMEDIATE     = 3'b101;
  localparam CSR_TYPE_IMMEDIATE   = 3'b110;

  // Program Counter source selection

  localparam PC_BOOT              = 2'b00;
  localparam PC_EPC               = 2'b01;
  localparam PC_TRAP              = 2'b10;
  localparam PC_NEXT              = 2'b11;

  // Load size encoding

  localparam LOAD_SIZE_BYTE       = 2'b00;
  localparam LOAD_SIZE_HALF       = 2'b01;
  localparam LOAD_SIZE_WORD       = 2'b10;

  // CSR File operation encoding

  localparam CSR_RWX              = 2'b01;
  localparam CSR_RSX              = 2'b10;
  localparam CSR_RCX              = 2'b11;

  // States in M-mode

  localparam STATE_RESET          = 4'b0001;
  localparam STATE_OPERATING      = 4'b0010;
  localparam STATE_TRAP_TAKEN     = 4'b0100;
  localparam STATE_TRAP_RETURN    = 4'b1000;

  // No operation

  localparam NOP_INSTRUCTION      = 32'h00000013;

  // Opcodes

  localparam OPCODE_OP            = 7'b0110011;
  localparam OPCODE_OP_IMM        = 7'b0010011;
  localparam OPCODE_LOAD          = 7'b0000011;
  localparam OPCODE_STORE         = 7'b0100011;
  localparam OPCODE_BRANCH        = 7'b1100011;
  localparam OPCODE_JAL           = 7'b1101111;
  localparam OPCODE_JALR          = 7'b1100111;
  localparam OPCODE_LUI           = 7'b0110111;
  localparam OPCODE_AUIPC         = 7'b0010111;
  localparam OPCODE_MISC_MEM      = 7'b0001111;
  localparam OPCODE_SYSTEM        = 7'b1110011;

  // Funct3

  localparam FUNCT3_ADD           = 3'b000;
  localparam FUNCT3_SUB           = 3'b000;
  localparam FUNCT3_SLT           = 3'b010;
  localparam FUNCT3_SLTU          = 3'b011;
  localparam FUNCT3_AND           = 3'b111;
  localparam FUNCT3_OR            = 3'b110;
  localparam FUNCT3_XOR           = 3'b100;
  localparam FUNCT3_SLL           = 3'b001;
  localparam FUNCT3_SRL           = 3'b101;
  localparam FUNCT3_SRA           = 3'b101;
  localparam FUNCT3_ADDI          = 3'b000;
  localparam FUNCT3_SLTI          = 3'b010;
  localparam FUNCT3_SLTIU         = 3'b011;
  localparam FUNCT3_ANDI          = 3'b111;
  localparam FUNCT3_ORI           = 3'b110;
  localparam FUNCT3_XORI          = 3'b100;
  localparam FUNCT3_SLLI          = 3'b001;
  localparam FUNCT3_SRLI          = 3'b101;
  localparam FUNCT3_SRAI          = 3'b101;
  localparam FUNCT3_BEQ           = 3'b000;
  localparam FUNCT3_BNE           = 3'b001;
  localparam FUNCT3_BLT           = 3'b100;
  localparam FUNCT3_BGE           = 3'b101;
  localparam FUNCT3_BLTU          = 3'b110;
  localparam FUNCT3_BGEU          = 3'b111;
  localparam FUNCT3_SB            = 3'b000;
  localparam FUNCT3_SH            = 3'b001;
  localparam FUNCT3_SW            = 3'b010;
  localparam FUNCT3_ECALL         = 3'b000;
  localparam FUNCT3_EBREAK        = 3'b000;
  localparam FUNCT3_MRET          = 3'b000;

  // Funct7

  localparam FUNCT7_SUB           = 7'b0100000;
  localparam FUNCT7_SRA           = 7'b0100000;
  localparam FUNCT7_ADD           = 7'b0000000;
  localparam FUNCT7_SLT           = 7'b0000000;
  localparam FUNCT7_SLTU          = 7'b0000000;
  localparam FUNCT7_AND           = 7'b0000000;
  localparam FUNCT7_OR            = 7'b0000000;
  localparam FUNCT7_XOR           = 7'b0000000;
  localparam FUNCT7_SLL           = 7'b0000000;
  localparam FUNCT7_SRL           = 7'b0000000;
  localparam FUNCT7_SRAI          = 7'b0100000;
  localparam FUNCT7_SLLI          = 7'b0000000;
  localparam FUNCT7_SRLI          = 7'b0000000;
  localparam FUNCT7_ECALL         = 7'b0000000;
  localparam FUNCT7_EBREAK        = 7'b0000000;
  localparam FUNCT7_MRET          = 7'b0011000;

  // RS1, RS2 and RD encodings for SYSTEM instructions

  localparam RS1_ECALL            = 5'b00000;
  localparam RS1_EBREAK           = 5'b00000;
  localparam RS1_MRET             = 5'b00000;
  localparam RS2_ECALL            = 5'b00000;
  localparam RS2_EBREAK           = 5'b00001;
  localparam RS2_MRET             = 5'b00010;
  localparam RD_ECALL             = 5'b00000;
  localparam RD_EBREAK            = 5'b00000;
  localparam RD_MRET              = 5'b00000;

  //-----------------------------------------------------------------------------------------------//
  // Wires and regs                                                                                //
  //-----------------------------------------------------------------------------------------------//

  wire  [31:0]  alu_2nd_operand;
  wire          alu_2nd_operand_source;
  wire  [31:0]  alu_adder_2nd_operand_mux;
  wire  [31:0]  alu_minus_2nd_operand;
  wire  [3:0 ]  alu_operation_code;
  reg   [31:0]  alu_output;
  wire  [31:0]  alu_shift_right_mux;
  wire          alu_slt_result;
  wire          alu_sltu_result;
  wire  [31:0]  alu_sra_result;
  wire  [31:0]  alu_srl_result;
  reg           branch_condition_satisfied;
  wire  [31:0]  branch_target_address;
  wire          clock_enable;
  wire  [31:0]  csr_data_mask;
  reg   [31:0]  csr_data_out;
  wire          csr_file_write_enable;
  wire          csr_file_write_request;
  reg   [31:0]  csr_mcause;
  reg   [4:0 ]  csr_mcause_code;
  reg           csr_mcause_interrupt_flag;
  reg   [63:0]  csr_mcycle;
  reg   [31:0]  csr_mepc;
  wire  [31:0]  csr_mie;
  reg   [15:0]  csr_mie_mfie;
  reg           csr_mie_meie;
  reg           csr_mie_msie;
  reg           csr_mie_mtie;
  wire  [31:0]  csr_mip;
  reg   [15:0]  csr_mip_mfip;
  reg           csr_mip_meip;
  reg           csr_mip_mtip;
  reg           csr_mip_msip;
  reg   [63:0]  csr_minstret;
  reg   [31:0]  csr_mscratch;
  wire  [31:0]  csr_mstatus;
  reg           csr_mstatus_mie;
  reg           csr_mstatus_mpie;
  reg   [31:0]  csr_mtvec;
  reg   [31:0]  csr_mtval;
  wire  [2:0 ]  csr_operation;
  reg   [63:0]  csr_utime;
  reg   [31:0]  csr_write_data;
  reg   [3:0 ]  current_state;
  wire          ebreak;
  wire          ecall;
  wire          flush;
  wire          illegal_instruction;
  reg   [31:0]  immediate;
  wire  [31:0]  immediate_b_type;
  wire  [31:0]  immediate_csr_type;
  wire  [31:0]  immediate_i_type;
  wire  [31:0]  immediate_j_type;
  wire  [31:0]  immediate_s_type;
  wire  [19:0]  immediate_sign_extension;
  reg   [2:0 ]  immediate_type;
  wire  [31:0]  immediate_u_type;
  reg   [31:0]  integer_file [31:1];
  wire          integer_file_write_enable;
  wire          integer_file_write_request;
  wire  [31:0]  instruction;
  wire  [31:0]  instruction_address;
  wire  [2:0 ]  instruction_funct3;
  wire  [6:0 ]  instruction_funct7;
  wire  [6:0 ]  instruction_opcode;
  wire  [11:0]  instruction_csr_address;
  wire  [4:0 ]  instruction_rd_address;
  wire  [4:0 ]  instruction_rs1_address;
  wire  [4:0 ]  instruction_rs2_address;
  wire  [31:0]  interrupt_address_offset;
  wire          load;
  reg   [7:0 ]  load_byte_data;
  wire  [23:0]  load_byte_upper_bits;
  wire          load_commit_cycle;
  reg   [31:0]  load_data;
  reg   [15:0]  load_half_data;
  wire  [15:0]  load_half_upper_bits;
  wire          load_pending;
  wire          load_request;
  wire  [1:0 ]  load_size;
  wire          load_unsigned;
  wire          misaligned_address_exception;
  wire          misaligned_instruction_address;
  wire          misaligned_load;
  wire          misaligned_store;
  wire          mret;
  wire  [31:0]  next_address;
  reg   [31:0]  next_program_counter;
  reg   [3:0 ]  next_state;
  reg   [31:0]  prev_instruction;
  reg   [31:0]  prev_instruction_address;
  reg           prev_load_request;
  reg           prev_read_request;
  reg   [31:0]  prev_rw_address;
  reg   [31:0]  prev_write_data;
  reg           prev_write_request;
  reg   [3:0 ]  prev_write_strobe;
  reg   [31:0]  program_counter;
  wire  [31:0]  program_counter_plus_4;
  reg   [1:0 ]  program_counter_source;
  wire          reset_internal;
  reg           reset_reg;
  wire  [31:0]  rs1_data;
  wire  [31:0]  rs2_data;
  wire  [31:0]  rw_address_internal;
  wire          store;
  reg   [31:0]  store_byte_data;
  wire          store_commit_cycle;
  reg   [31:0]  store_half_data;
  wire          store_pending;
  wire          store_request;
  wire          take_branch;
  wire          take_trap;
  wire  [31:0]  target_address_adder;
  wire          target_address_source;
  wire  [31:0]  trap_address;
  reg   [31:0]  write_data_internal;
  reg   [3:0 ]  write_strobe_for_byte;
  reg   [3:0 ]  write_strobe_for_half;
  reg   [3:0 ]  write_strobe_internal;
  reg   [2:0 ]  writeback_mux_selector;
  reg   [31:0]  writeback_multiplexer_output;
  wire          branch_type;
  wire          jal_type;
  wire          jalr_type;
  wire          auipc_type;
  wire          lui_type;
  wire          load_type;
  wire          store_type;
  wire          system_type;
  wire          op_type;
  wire          op_imm_type;
  wire          misc_mem_type;
  wire          addi;
  wire          slti;
  wire          sltiu;
  wire          andi;
  wire          ori;
  wire          xori;
  wire          slli;
  wire          srli;
  wire          srai;
  wire          add;
  wire          sub;
  wire          slt;
  wire          sltu;
  wire          is_and;
  wire          is_or;
  wire          is_xor;
  wire          sll;
  wire          srl;
  wire          sra;
  wire          csrxxx;
  wire          illegal_store;
  wire          illegal_load;
  wire          illegal_jalr;
  wire          illegal_branch;
  wire          illegal_op;
  wire          illegal_op_imm;
  wire          illegal_system;
  wire          unknown_type;
  wire          misaligned_word;
  wire          misaligned_half;
  wire          misaligned;
  wire          is_branch;
  wire          is_jump;
  wire          is_equal;
  wire          is_not_equal;
  wire          is_less_than_unsigned;
  wire          is_less_than;
  wire          is_greater_or_equal_than;
  wire          is_greater_or_equal_than_unsigned;
  wire          interrupt_pending;
  wire          exception_pending;

  //-----------------------------------------------------------------------------------------------//
  // Global signals                                                                                //
  //-----------------------------------------------------------------------------------------------//

  always @(posedge clock)
    reset_reg <= reset;

  assign reset_internal = reset | reset_reg;

  assign clock_enable = !( halt                |
    (prev_read_request   & !read_response    ) |
    (prev_write_request  & !write_response   ) );

  always @(posedge clock) begin
    if (reset_internal) begin
      prev_instruction_address  <= BOOT_ADDRESS;
      prev_load_request         <= 1'b0;
      prev_rw_address           <= 32'h00000000;
      prev_read_request         <= 1'b0;
      prev_write_data           <= 32'h00000000;
      prev_write_request        <= 1'b0;
      prev_write_strobe         <= 4'b0000;
    end
    else if(clock_enable) begin
      prev_instruction_address  <= instruction_address;
      prev_load_request         <= load_request;
      prev_rw_address           <= rw_address;
      prev_read_request         <= read_request;
      prev_write_data           <= write_data;
      prev_write_request        <= write_request;
      prev_write_strobe         <= write_strobe;
    end
  end

  //-----------------------------------------------------------------------------------------------//
  // Instruction fetch and instruction address logic                                               //
  //-----------------------------------------------------------------------------------------------//

  assign instruction_address =
    reset ?
    BOOT_ADDRESS :
    (clock_enable ?
      next_program_counter :
      prev_instruction_address);

    always @(posedge clock)
    if (reset_internal)
      prev_instruction <= NOP_INSTRUCTION;
    else
      prev_instruction <= instruction;

  always @* begin : next_program_counter_mux
    case (program_counter_source)
      PC_BOOT: next_program_counter = BOOT_ADDRESS;
      PC_EPC:  next_program_counter = csr_mepc;
      PC_TRAP: next_program_counter = trap_address;
      PC_NEXT: next_program_counter = next_address;
    endcase
  end

  assign program_counter_plus_4 =
    program_counter + 32'h00000004;

  assign target_address_adder =
    target_address_source == 1'b1 ?
    rs1_data + immediate :
    program_counter + immediate;

  assign branch_target_address =
    {target_address_adder[31:1], 1'b0};

  assign next_address =
   take_branch ?
   branch_target_address :
   program_counter_plus_4;

  always @(posedge clock) begin : program_counter_reg_implementation
    if (reset_internal)
      program_counter <= BOOT_ADDRESS;
    else if (clock_enable & !load_pending & !store_pending)
      program_counter <= next_program_counter;
  end

  assign instruction =
    flush ?
    NOP_INSTRUCTION :
    (!clock_enable | load_commit_cycle | store_commit_cycle) ?
      prev_instruction :
      read_data;

  assign instruction_opcode =
    instruction[6:0];

  assign instruction_funct3 =
    instruction[14:12];

  assign instruction_funct7 =
    instruction[31:25];

  assign instruction_rs1_address =
    instruction[19:15];

  assign instruction_rs2_address =
    instruction[24:20];

  assign instruction_rd_address =
    instruction[11:7];

  assign instruction_csr_address =
    instruction[31:20];

  //-----------------------------------------------------------------------------------------------//
  // IO read / write                                                                               //
  //-----------------------------------------------------------------------------------------------//

  assign read_request =
    reset_internal ?
    1'b0 :
    (clock_enable ?
      ~store_request :
      prev_read_request);

  assign rw_address =
    reset_internal ?
    32'h00000000 :
    (clock_enable ?
      rw_address_internal :
      prev_rw_address);

  assign write_request =
    reset_internal ?
    1'b0 :
    (clock_enable ?
      store_request :
      prev_write_request);

  assign write_data =
    reset_internal ?
    32'h00000000 :
    (clock_enable ?
      write_data_internal :
      prev_write_data);

  assign write_strobe =
    reset_internal ?
    4'b0 :
    (clock_enable ?
      write_strobe_internal :
      prev_write_strobe);

  assign load_commit_cycle =
    prev_load_request & read_response;

  assign store_commit_cycle =
    prev_write_request & write_response;

  assign load_pending =
    load  & !load_commit_cycle;

  assign store_pending =
    store & !store_commit_cycle;

  assign load_request =
    load  & ~misaligned_load  & ~take_trap & ~load_commit_cycle;

  assign store_request =
    store & ~misaligned_store & ~take_trap & ~store_commit_cycle;

  assign rw_address_internal =
    load_request | store_request ?
    {target_address_adder[31:2], 2'b00} :
    instruction_address;

  always @* begin
    case(instruction_funct3)
      FUNCT3_SB: begin
        write_strobe_internal = write_strobe_for_byte;
        write_data_internal   = store_byte_data;
      end
      FUNCT3_SH: begin
        write_strobe_internal = write_strobe_for_half;
        write_data_internal   = store_half_data;
      end
      FUNCT3_SW: begin
        write_strobe_internal = {4{write_request}};
        write_data_internal   = rs2_data;
      end
      default: begin
        write_strobe_internal = {4{write_request}};
        write_data_internal   = rs2_data;
      end
    endcase
  end

  always @* begin
    case(target_address_adder[1:0])
      2'b00: begin
        store_byte_data       = {24'b0, rs2_data[7:0]};
        write_strobe_for_byte = {3'b0, write_request};
      end
      2'b01: begin
        store_byte_data       = {16'b0, rs2_data[7:0], 8'b0};
        write_strobe_for_byte = {2'b0, write_request, 1'b0};
      end
      2'b10: begin
        store_byte_data       = {8'b0, rs2_data[7:0], 16'b0};
        write_strobe_for_byte = {1'b0, write_request, 2'b0};
      end
      2'b11: begin
        store_byte_data       = {rs2_data[7:0], 24'b0};
        write_strobe_for_byte = {write_request, 3'b0};
      end
    endcase
  end

  always @* begin
    case(target_address_adder[1])
      1'b0: begin
        store_half_data       = {16'b0, rs2_data[15:0]};
        write_strobe_for_half = {2'b0, {2{write_request}}};
      end
      1'b1: begin
        store_half_data       = {rs2_data[15:0], 16'b0};
        write_strobe_for_half = {{2{write_request}}, 2'b0};
      end
    endcase
  end

  //-----------------------------------------------------------------------------------------------//
  // Instruction decoding                                                                          //
  //-----------------------------------------------------------------------------------------------//

  // Instruction type detection

  assign branch_type =
    instruction_opcode == OPCODE_BRANCH;

  assign jal_type =
    instruction_opcode == OPCODE_JAL;

  assign jalr_type =
    instruction_opcode == OPCODE_JALR;

  assign auipc_type =
    instruction_opcode == OPCODE_AUIPC;

  assign lui_type =
    instruction_opcode == OPCODE_LUI;

  assign load_type =
    instruction_opcode == OPCODE_LOAD;

  assign store_type =
    instruction_opcode == OPCODE_STORE;

  assign system_type =
    instruction_opcode == OPCODE_SYSTEM;

  assign op_type =
    instruction_opcode == OPCODE_OP;

  assign op_imm_type =
    instruction_opcode == OPCODE_OP_IMM;

  assign misc_mem_type =
    instruction_opcode == OPCODE_MISC_MEM;

  // Instruction detection

  assign addi =
    op_imm_type &
    instruction_funct3 == FUNCT3_ADDI;

  assign slti =
    op_imm_type &
    instruction_funct3 == FUNCT3_SLTI;

  assign sltiu =
    op_imm_type &
    instruction_funct3 == FUNCT3_SLTIU;

  assign andi =
    op_imm_type &
    instruction_funct3 == FUNCT3_ANDI;

  assign ori =
    op_imm_type &
    instruction_funct3 == FUNCT3_ORI;

  assign xori =
    op_imm_type &
    instruction_funct3 == FUNCT3_XORI;

  assign slli =
    op_imm_type &
    instruction_funct3 == FUNCT3_SLLI &
    instruction_funct7 == FUNCT7_SLLI;

  assign srli =
    op_imm_type &
    instruction_funct3 == FUNCT3_SRLI &
    instruction_funct7 == FUNCT7_SRLI;

  assign srai =
    op_imm_type &
    instruction_funct3 == FUNCT3_SRAI &
    instruction_funct7 == FUNCT7_SRAI;

  assign add =
    op_type &
    instruction_funct3 == FUNCT3_ADD &
    instruction_funct7 == FUNCT7_ADD;

  assign sub =
    op_type &
    instruction_funct3 == FUNCT3_SUB &
    instruction_funct7 == FUNCT7_SUB;

  assign slt =
    op_type &
    instruction_funct3 == FUNCT3_SLT &
    instruction_funct7 == FUNCT7_SLT;

  assign sltu =
    op_type &
    instruction_funct3 == FUNCT3_SLTU &
    instruction_funct7 == FUNCT7_SLTU;

  assign is_and =
    op_type &
    instruction_funct3 == FUNCT3_AND &
    instruction_funct7 == FUNCT7_AND;

  assign is_or =
    op_type &
    instruction_funct3 == FUNCT3_OR &
    instruction_funct7 == FUNCT7_OR;

  assign is_xor =
    op_type &
    instruction_funct3 == FUNCT3_XOR &
    instruction_funct7 == FUNCT7_XOR;

  assign sll =
    op_type &
    instruction_funct3 == FUNCT3_SLL &
    instruction_funct7 == FUNCT7_SLL;

  assign srl =
    op_type &
    instruction_funct3 == FUNCT3_SRL &
    instruction_funct7 == FUNCT7_SRL;

  assign sra =
    op_type &
    instruction_funct3 == FUNCT3_SRA &
    instruction_funct7 == FUNCT7_SRA;

  assign csrxxx =
    system_type &
    instruction_funct3 != 3'b000 &
    instruction_funct3 != 3'b100;

  assign ecall =
    system_type &
    instruction_funct3 == FUNCT3_ECALL &
    instruction_funct7 == FUNCT7_ECALL &
    instruction_rs1_address == RS1_ECALL &
    instruction_rs2_address == RS2_ECALL &
    instruction_rd_address  == RD_ECALL;

  assign ebreak =
    system_type &
    instruction_funct3 == FUNCT3_EBREAK &
    instruction_funct7 == FUNCT7_EBREAK &
    instruction_rs1_address == RS1_EBREAK &
    instruction_rs2_address == RS2_EBREAK &
    instruction_rd_address  == RD_EBREAK;

  assign mret =
    system_type &
    instruction_funct3 == FUNCT3_MRET &
    instruction_funct7 == FUNCT7_MRET &
    instruction_rs1_address == RS1_MRET &
    instruction_rs2_address == RS2_MRET &
    instruction_rd_address  == RD_MRET;

  // Illegal instruction detection

  assign illegal_store =
    store_type &
    (instruction_funct3[2] == 1'b1 ||
    instruction_funct3[1:0] == 2'b11);

  assign illegal_load =
    load_type &
    (instruction_funct3 == 3'b011 ||
     instruction_funct3 == 3'b110 ||
     instruction_funct3 == 3'b111);

  assign illegal_jalr =
    jalr_type &
    instruction_funct3 != 3'b000;

  assign illegal_branch =
    branch_type &
    (instruction_funct3 == 3'b010 ||
    instruction_funct3 == 3'b011);

  assign illegal_op =
    op_type &
    ~(add | sub | slt | sltu | is_and | is_or | is_xor | sll | srl | sra);

  assign illegal_op_imm =
    op_imm_type &
    ~(addi | slti | sltiu | andi | ori | xori | slli | srli | srai);

  assign illegal_system =
    system_type &
    ~(csrxxx | ecall | ebreak | mret);

  assign unknown_type =
    ~(branch_type | jal_type | jalr_type | auipc_type | lui_type | load_type | store_type
    | system_type | op_type | op_imm_type | misc_mem_type);

  assign illegal_instruction =
    unknown_type | illegal_store | illegal_load | illegal_jalr | illegal_branch | illegal_op
    | illegal_op_imm | illegal_system;

  // Misaligned address detection

  assign misaligned_word =
    instruction_funct3[1:0] == 2'b10 &
    (target_address_adder[1] | target_address_adder[0]);

  assign misaligned_half =
    instruction_funct3[1:0] == 2'b01 &
    target_address_adder[0];

  assign misaligned =
    misaligned_word | misaligned_half;

  assign misaligned_store =
    store & misaligned;

  assign misaligned_load =
    load & misaligned;

  // Control signals generation

  assign alu_operation_code[2:0] =
    instruction_funct3;

  assign alu_operation_code[3] =
    instruction_funct7[5] &
    ~(addi | slti | sltiu | andi | ori | xori);

  assign load =
    load_type &
    ~illegal_load;

  assign store =
    store_type &
    ~illegal_store;

  assign load_size =
    instruction_funct3[1:0];

  assign load_unsigned =
    instruction_funct3[2];

  assign alu_2nd_operand_source =
    instruction_opcode[5];

  assign target_address_source =
    load_type | store_type | jalr_type;

  assign integer_file_write_request =
    lui_type | auipc_type | jalr_type | jal_type | op_type | op_imm_type | load_type | csrxxx;

  assign csr_file_write_request =
    csrxxx;

  assign csr_operation = instruction_funct3;

  always @* begin : writeback_selector_decoding
    if (op_type == 1'b1 || op_imm_type == 1'b1)
      writeback_mux_selector = WB_ALU;
    else if (load_type == 1'b1)
      writeback_mux_selector = WB_LOAD_UNIT;
    else if (jal_type == 1'b1 || jalr_type == 1'b1)
      writeback_mux_selector = WB_PC_PLUS_4;
    else if (lui_type == 1'b1)
      writeback_mux_selector = WB_UPPER_IMM;
    else if (auipc_type == 1'b1)
      writeback_mux_selector = WB_TARGET_ADDER;
    else if (csrxxx == 1'b1)
      writeback_mux_selector = WB_CSR;
    else
      writeback_mux_selector = WB_ALU;
  end

  always @* begin : immediate_type_decoding
    if (op_imm_type == 1'b1 || load_type == 1'b1 || jalr_type == 1'b1)
      immediate_type = I_TYPE_IMMEDIATE;
    else if (store_type == 1'b1)
      immediate_type = S_TYPE_IMMEDIATE;
    else if (branch_type == 1'b1)
      immediate_type = B_TYPE_IMMEDIATE;
    else if (jal_type == 1'b1)
      immediate_type = J_TYPE_IMMEDIATE;
    else if (lui_type == 1'b1 || auipc_type == 1'b1)
      immediate_type = U_TYPE_IMMEDIATE;
    else if (csrxxx == 1'b1)
      immediate_type = CSR_TYPE_IMMEDIATE;
    else
      immediate_type = I_TYPE_IMMEDIATE;
  end

  //-----------------------------------------------------------------------------------------------//
  // Immediate generation                                                                          //
  //-----------------------------------------------------------------------------------------------//

  assign immediate_sign_extension = {
    20 {instruction[31]}
  };

  assign immediate_i_type = {
    immediate_sign_extension,
    instruction[31:20]
  };

  assign immediate_s_type = {
    immediate_sign_extension,
    instruction[31:25],
    instruction[11:7 ]
  };

  assign immediate_b_type = {
    immediate_sign_extension,
    instruction[7],
    instruction[30:25],
    instruction[11:8],
    1'b0
  };

  assign immediate_u_type = {
    instruction[31:12],
    12'h000
  };

  assign immediate_j_type = {
    immediate_sign_extension[11:0],
    instruction[19:12],
    instruction[20],
    instruction[30:21],
    1'b0
  };

  assign immediate_csr_type = {
    27'b0,
    instruction[19:15]
  };

  always @(*) begin : immediate_mux
    case (immediate_type)
      I_TYPE_IMMEDIATE:
        immediate = immediate_i_type;
      S_TYPE_IMMEDIATE:
        immediate = immediate_s_type;
      B_TYPE_IMMEDIATE:
        immediate = immediate_b_type;
      U_TYPE_IMMEDIATE:
        immediate = immediate_u_type;
      J_TYPE_IMMEDIATE:
        immediate = immediate_j_type;
      CSR_TYPE_IMMEDIATE:
        immediate = immediate_csr_type;
      default:
        immediate = immediate_i_type;
    endcase
  end

  //-----------------------------------------------------------------------------------------------//
  // Take branch decision                                                                          //
  //-----------------------------------------------------------------------------------------------//

  assign is_branch =
    branch_type & !illegal_branch;

  assign is_jump =
    jal_type | (jalr_type & !illegal_jalr);

  assign is_equal =
    rs1_data == rs2_data;

  assign is_not_equal =
    !is_equal;

  assign is_less_than_unsigned =
    rs1_data < rs2_data;

  assign is_less_than =
    rs1_data[31] ^ rs2_data[31] ?
    rs1_data[31] :
    is_less_than_unsigned;

  assign is_greater_or_equal_than =
    !is_less_than;

  assign is_greater_or_equal_than_unsigned =
    !is_less_than_unsigned;

  always @* begin : branch_condition_satisfied_mux
    case (instruction_funct3)
      FUNCT3_BEQ:
        branch_condition_satisfied =
          is_equal;
      FUNCT3_BNE:
        branch_condition_satisfied =
          is_not_equal;
      FUNCT3_BLT:
        branch_condition_satisfied =
          is_less_than;
      FUNCT3_BGE:
        branch_condition_satisfied =
          is_greater_or_equal_than;
      FUNCT3_BLTU:
        branch_condition_satisfied =
          is_less_than_unsigned;
      FUNCT3_BGEU:
        branch_condition_satisfied =
          is_greater_or_equal_than_unsigned;
      default:
        branch_condition_satisfied =
          1'b0;
      endcase
  end

  assign take_branch =
    (is_jump == 1'b1) ?
    1'b1 :
      (is_branch == 1'b1) ?
      branch_condition_satisfied :
      1'b0;

  //-----------------------------------------------------------------------------------------------//
  // Integer File implementation                                                                   //
  //-----------------------------------------------------------------------------------------------//

  assign integer_file_write_enable =
    integer_file_write_request & !flush & !load_pending;

  integer i;
  always @(posedge clock) begin
    if (reset_internal)
      for (i = 1; i < 32; i = i + 1) integer_file[i] <= 32'h00000000;
    else if (clock_enable & integer_file_write_enable)
      integer_file[instruction_rd_address] <= writeback_multiplexer_output;
  end

  assign rs1_data =
    instruction_rs1_address == 5'b00000 ?
    32'h00000000 :
    integer_file[instruction_rs1_address];

  assign rs2_data =
    instruction_rs2_address == 5'b00000 ?
    32'h00000000 :
    integer_file[instruction_rs2_address];

  //---------------------------------------------------------------------------------------------//
  // M-mode logic and hart control                                                               //
  //---------------------------------------------------------------------------------------------//

  assign flush =
    current_state != STATE_OPERATING;

  assign interrupt_pending =
    (csr_mie_meie & csr_mip_meip) |
    (csr_mie_mtie & csr_mip_mtip) |
    (csr_mie_msie & csr_mip_msip) |
    (|(csr_mie_mfie & csr_mip_mfip));

  assign exception_pending =
    illegal_instruction |
    misaligned_load |
    misaligned_store |
    misaligned_instruction_address;

  assign take_trap =
    (csr_mstatus_mie & interrupt_pending) |
    exception_pending |
    ecall |
    ebreak;

  always @* begin : m_mode_fsm_next_state_logic
    case (current_state)
      STATE_RESET:
        next_state = STATE_OPERATING;
      STATE_OPERATING:
        if(take_trap)
          next_state = STATE_TRAP_TAKEN;
        else if(mret)
          next_state = STATE_TRAP_RETURN;
        else
          next_state = STATE_OPERATING;
      STATE_TRAP_TAKEN:
        next_state = STATE_OPERATING;
      STATE_TRAP_RETURN:
        next_state = STATE_OPERATING;
      default:
        next_state = STATE_OPERATING;
    endcase
  end

  always @(posedge clock) begin : m_mode_fsm_current_state_register
    if(reset_internal)
      current_state <= STATE_RESET;
    else if (clock_enable | interrupt_pending)
      current_state <= next_state;
  end

  always @* begin : program_counter_source_mux
    case (current_state)
      STATE_RESET:
        program_counter_source = PC_BOOT;
      STATE_OPERATING:
        program_counter_source = PC_NEXT;
      STATE_TRAP_TAKEN:
        program_counter_source = PC_TRAP;
      STATE_TRAP_RETURN:
        program_counter_source = PC_EPC;
      default:
        program_counter_source = PC_NEXT;
    endcase
  end

  assign irq_external_response =
    (current_state    == STATE_TRAP_TAKEN) &&
    (csr_mcause_code  == 5'b1011);

  assign irq_timer_response =
    (current_state    == STATE_TRAP_TAKEN) &&
    (csr_mcause_code  == 5'b0111);

  assign irq_software_response =
    (current_state    == STATE_TRAP_TAKEN) &&
    (csr_mcause_code  == 5'b0011);

  generate
    genvar ifast;
    for (ifast = 0; ifast < 16; ifast = ifast + 1) begin
        assign irq_fast_response[ifast] =
        (current_state    == STATE_TRAP_TAKEN) &&
        (csr_mcause_code  == ifast+16);
    end
  endgenerate

  //---------------------------------------------------------------------------------------------//
  // Control and Status Registers implementation                                                 //
  //---------------------------------------------------------------------------------------------//

  assign csr_data_mask =
    csr_operation[2] == 1'b1 ?
    {27'b0, immediate[4:0]} :
    rs1_data;

  always @* begin : csr_write_data_mux
    case (csr_operation[1:0])
      CSR_RWX:
        csr_write_data = csr_data_mask;
      CSR_RSX:
        csr_write_data = csr_data_out |  csr_data_mask;
      CSR_RCX:
        csr_write_data = csr_data_out & ~csr_data_mask;
      default:
        csr_write_data = csr_data_out;
    endcase
  end

  always @* begin : csr_data_out_mux
    case (instruction_csr_address)
      MARCHID:       csr_data_out = 32'h00000018; // RISC-V Steel microarchitecture ID
      MIMPID:        csr_data_out = 32'h00000006; // Version 6
      CYCLE:         csr_data_out = csr_mcycle    [31:0 ];
      CYCLEH:        csr_data_out = csr_mcycle    [63:32];
      TIME:          csr_data_out = csr_utime     [31:0 ];
      TIMEH:         csr_data_out = csr_utime     [63:32];
      INSTRET:       csr_data_out = csr_minstret  [31:0 ];
      INSTRETH:      csr_data_out = csr_minstret  [63:32];
      MSTATUS:       csr_data_out = csr_mstatus;
      MSTATUSH:      csr_data_out = 32'h00000000;
      MISA:          csr_data_out = 32'h40000100; // RV32I base ISA only
      MIE:           csr_data_out = csr_mie;
      MTVEC:         csr_data_out = csr_mtvec;
      MSCRATCH:      csr_data_out = csr_mscratch;
      MEPC:          csr_data_out = csr_mepc;
      MCAUSE:        csr_data_out = csr_mcause;
      MTVAL:         csr_data_out = csr_mtval;
      MIP:           csr_data_out = csr_mip;
      MCYCLE:        csr_data_out = csr_mcycle    [31:0 ];
      MCYCLEH:       csr_data_out = csr_mcycle    [63:32];
      MINSTRET:      csr_data_out = csr_minstret  [31:0 ];
      MINSTRETH:     csr_data_out = csr_minstret  [63:32];
      default:       csr_data_out = 32'h00000000;
    endcase
  end

  assign csr_file_write_enable =
    csr_file_write_request & !flush;

  assign misaligned_instruction_address =
    take_branch & next_address[1];

  //---------------------------------------------------------------------------------------------//
  // mstatus : M-mode Status register                                                            //
  //---------------------------------------------------------------------------------------------//

  assign csr_mstatus = {
    19'b0000000000000000000,
    2'b11,              // M-mode Prior Privilege (always M-mode)
    3'b000,
    csr_mstatus_mpie,   // M-mode Prior Global Interrupt Enable
    3'b000,
    csr_mstatus_mie,    // M-mode Global Interrupt Enable
    3'b000
  };

  always @(posedge clock) begin : mstatus_csr_fields_update
    if(reset_internal) begin
      csr_mstatus_mie   <= 1'b0;
      csr_mstatus_mpie  <= 1'b1;
    end
    else if (clock_enable) begin
      if(current_state == STATE_TRAP_RETURN) begin
        csr_mstatus_mie   <= csr_mstatus_mpie;
        csr_mstatus_mpie  <= 1'b1;
      end
      else if(current_state == STATE_TRAP_TAKEN) begin
        csr_mstatus_mpie  <= csr_mstatus_mie;
        csr_mstatus_mie   <= 1'b0;
      end
      else if(current_state == STATE_OPERATING && instruction_csr_address == MSTATUS && csr_file_write_enable) begin
        csr_mstatus_mie   <= csr_write_data[3];
        csr_mstatus_mpie  <= csr_write_data[7];
      end
    end
  end

  //---------------------------------------------------------------------------------------------//
  // mie : M-mode Interrupt Enable register                                                      //
  //---------------------------------------------------------------------------------------------//

  assign csr_mie = {
    csr_mie_mfie,   // M-mode Designated for platform use (irq fast)
    4'b0,
    csr_mie_meie,   // M-mode External Interrupt Enable
    3'b0,
    csr_mie_mtie,   // M-mode Timer Interrupt Enable
    3'b0,
    csr_mie_msie,   // M-mode Software Interrupt Enable
    3'b0
  };

  always @(posedge clock) begin : mie_csr_fields_implementation
    if(reset_internal) begin
      csr_mie_mfie <= 16'b0;
      csr_mie_meie <= 1'b0;
      csr_mie_mtie <= 1'b0;
      csr_mie_msie <= 1'b0;
    end
    else if(clock_enable & instruction_csr_address == MIE && csr_file_write_enable) begin
      csr_mie_mfie <= csr_write_data[31:16];
      csr_mie_meie <= csr_write_data[11];
      csr_mie_mtie <= csr_write_data[7];
      csr_mie_msie <= csr_write_data[3];
    end
  end

  //---------------------------------------------------------------------------------------------//
  // mip : M-mode Interrupt Pending                                                              //
  //---------------------------------------------------------------------------------------------//

  assign csr_mip = {
    csr_mip_mfip,
    4'b0,
    csr_mip_meip,
    3'b0,
    csr_mip_mtip,
    3'b0,
    csr_mip_msip,
    3'b0
  };

  always @(posedge clock) begin : mip_csr_fields_implementation
    if(reset_internal) begin
      csr_mip_mfip <= 16'b0;
      csr_mip_meip <= 1'b0;
      csr_mip_mtip <= 1'b0;
      csr_mip_msip <= 1'b0;
    end
    else begin
      csr_mip_mfip <= irq_fast;
      csr_mip_meip <= irq_external;
      csr_mip_mtip <= irq_timer;
      csr_mip_msip <= irq_software;
    end
  end

  //---------------------------------------------------------------------------------------------//
  // mepc : M-mode Exception Program Counter register                                            //
  //---------------------------------------------------------------------------------------------//

  always @(posedge clock) begin : mepc_implementation
    if(reset_internal)
      csr_mepc <= 32'h00000000;
    else if (clock_enable) begin
      if(take_trap)
        csr_mepc <= program_counter;
      else if(current_state == STATE_OPERATING && instruction_csr_address == MEPC && csr_file_write_enable)
        csr_mepc <= {csr_write_data[31:2], 2'b00};
    end
  end

  //---------------------------------------------------------------------------------------------//
  // mscratch : M-mode Scratch register                                                          //
  //---------------------------------------------------------------------------------------------//

  always @(posedge clock) begin
    if(reset_internal)
      csr_mscratch <= 32'h00000000;
    else if(clock_enable & instruction_csr_address == MSCRATCH && csr_file_write_enable)
      csr_mscratch <= csr_write_data;
  end

  //---------------------------------------------------------------------------------------------//
  // mcycle : M-mode Cycle Counter register                                                      //
  //---------------------------------------------------------------------------------------------//

  always @(posedge clock) begin : mcycle_implementation
    if (reset_internal)
      csr_mcycle <= 64'b0;
    else begin
      if (clock_enable & instruction_csr_address == MCYCLE && csr_file_write_enable)
        csr_mcycle <= {csr_mcycle[63:32], csr_write_data} + 1;
      else if (clock_enable & instruction_csr_address == MCYCLEH && csr_file_write_enable)
        csr_mcycle <= {csr_write_data, csr_mcycle[31:0]} + 1;
      else
        csr_mcycle <= csr_mcycle + 1;
    end
  end

  //---------------------------------------------------------------------------------------------//
  // minstret : M-mode Instruction Retired Counter register                                      //
  //---------------------------------------------------------------------------------------------//

  always @(posedge clock) begin : minstret_implementation
    if (reset_internal)
      csr_minstret  <= 64'b0;
    else if (clock_enable) begin
      if (instruction_csr_address == MINSTRET && csr_file_write_enable) begin
        if (current_state == STATE_OPERATING)
          csr_minstret <= {csr_minstret[63:32], csr_write_data} + 1;
        else
          csr_minstret <= {csr_minstret[63:32], csr_write_data};
      end
      else if (instruction_csr_address == MINSTRETH && csr_file_write_enable) begin
        if (current_state == STATE_OPERATING)
          csr_minstret <= {csr_write_data, csr_minstret[31:0]} + 1;
        else
          csr_minstret <= {csr_write_data, csr_minstret[31:0]};
      end
      else begin
        if (current_state == STATE_OPERATING)
          csr_minstret <= csr_minstret + 1;
        else
          csr_minstret <= csr_minstret;
      end
    end
  end

  //---------------------------------------------------------------------------------------------//
  // utime : Time register (Read-only shadow of mtime)                                           //
  //---------------------------------------------------------------------------------------------//

  always @(posedge clock) begin : utime_csr_implementation
    csr_utime <= real_time_clock;
  end

  //---------------------------------------------------------------------------------------------//
  // mcause : M-mode Trap Cause register                                                         //
  //---------------------------------------------------------------------------------------------//

  always @(posedge clock) begin : mcause_implementation
    if(reset_internal)
      csr_mcause <= 32'h00000000;
    else if (clock_enable) begin
      if(current_state == STATE_TRAP_TAKEN)
        csr_mcause <= {csr_mcause_interrupt_flag, 26'b0, csr_mcause_code};
      else if(current_state == STATE_OPERATING && instruction_csr_address == MCAUSE && csr_file_write_enable)
        csr_mcause <= csr_write_data;
    end
  end

  always @(posedge clock) begin : trap_cause_implementation
    if(reset_internal) begin
      csr_mcause_code           <= 5'b0;
      csr_mcause_interrupt_flag <= 1'b0;
    end
    if(clock_enable & current_state == STATE_OPERATING) begin
      if(illegal_instruction) begin
        csr_mcause_code           <= 5'b0010;
        csr_mcause_interrupt_flag <= 1'b0;
      end
      else if(misaligned_instruction_address) begin
        csr_mcause_code           <= 5'b0000;
        csr_mcause_interrupt_flag <= 1'b0;
      end
      else if(ecall) begin
        csr_mcause_code           <= 5'b1011;
        csr_mcause_interrupt_flag <= 1'b0;
      end
      else if(ebreak) begin
        csr_mcause_code           <= 5'b0011;
        csr_mcause_interrupt_flag <= 1'b0;
      end
      else if(misaligned_store) begin
        csr_mcause_code           <= 5'b0110;
        csr_mcause_interrupt_flag <= 1'b0;
      end
      else if(misaligned_load) begin
        csr_mcause_code           <= 5'b0100;
        csr_mcause_interrupt_flag <= 1'b0;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[0] & csr_mip_mfip[0]) begin
        csr_mcause_code           <= 5'd16;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[1] & csr_mip_mfip[1]) begin
        csr_mcause_code           <= 5'd17;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[2] & csr_mip_mfip[2]) begin
        csr_mcause_code           <= 5'd18;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[3] & csr_mip_mfip[3]) begin
        csr_mcause_code           <= 5'd19;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[4] & csr_mip_mfip[4]) begin
        csr_mcause_code           <= 5'd20;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[5] & csr_mip_mfip[5]) begin
        csr_mcause_code           <= 5'd21;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[6] & csr_mip_mfip[6]) begin
        csr_mcause_code           <= 5'd22;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[7] & csr_mip_mfip[7]) begin
        csr_mcause_code           <= 5'd23;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[8] & csr_mip_mfip[8]) begin
        csr_mcause_code           <= 5'd24;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[9] & csr_mip_mfip[9]) begin
        csr_mcause_code           <= 5'd25;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[10] & csr_mip_mfip[10]) begin
        csr_mcause_code           <= 5'd26;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[11] & csr_mip_mfip[11]) begin
        csr_mcause_code           <= 5'd27;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[12] & csr_mip_mfip[12]) begin
        csr_mcause_code           <= 5'd28;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[13] & csr_mip_mfip[13]) begin
        csr_mcause_code           <= 5'd29;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[14] & csr_mip_mfip[14]) begin
        csr_mcause_code           <= 5'd30;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mfie[15] & csr_mip_mfip[15]) begin
        csr_mcause_code           <= 5'd31;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_meie & csr_mip_meip) begin
        csr_mcause_code           <= 5'b1011;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_msie & csr_mip_msip) begin
        csr_mcause_code           <= 5'b0011;
        csr_mcause_interrupt_flag <= 1'b1;
      end
      else if(csr_mstatus_mie & csr_mie_mtie & csr_mip_mtip) begin
        csr_mcause_code           <= 5'b0111;
        csr_mcause_interrupt_flag <= 1'b1;
      end
    end
  end

  //---------------------------------------------------------------------------------------------//
  // mtval : M-mode Trap Value                                                                   //
  //---------------------------------------------------------------------------------------------//

  assign misaligned_address_exception =
    misaligned_load | misaligned_store | misaligned_instruction_address;

  always @(posedge clock) begin : mtval_implementation
    if(reset_internal)
      csr_mtval <= 32'h00000000;
    else if (clock_enable) begin
      if(take_trap) begin
        if(misaligned_address_exception)
          csr_mtval <= target_address_adder;
        else if (ebreak)
          csr_mtval <= program_counter;
        else
          csr_mtval <= 32'h00000000;
      end
      else if(current_state == STATE_OPERATING && instruction_csr_address == MTVAL && csr_file_write_enable)
        csr_mtval <= csr_write_data;
    end
  end

  //---------------------------------------------------------------------------------------------//
  // mtvec : M-mode Trap Vector Address register                                                 //
  //---------------------------------------------------------------------------------------------//

  assign interrupt_address_offset =
    {{25{1'b0}}, csr_mcause_code, 2'b00};

  assign trap_address =
    csr_mtvec[1:0] == 2'b01 && csr_mcause_interrupt_flag ?
    {csr_mtvec[31:2], 2'b00} + interrupt_address_offset :
    {csr_mtvec[31:2], 2'b00};

  always @(posedge clock) begin : mtvec_implementation
    if(reset_internal)
      csr_mtvec <= 32'h00000000;
    else if(clock_enable & instruction_csr_address == MTVEC && csr_file_write_enable)
      csr_mtvec <= {csr_write_data[31:2], 1'b0, csr_write_data[0]};
  end

  //---------------------------------------------------------------------------------------------//
  // Integer register file writeback selection                                                   //
  //---------------------------------------------------------------------------------------------//

  always @* begin
    case (writeback_mux_selector)
      WB_ALU:          writeback_multiplexer_output = alu_output;
      WB_LOAD_UNIT:    writeback_multiplexer_output = load_data;
      WB_UPPER_IMM:    writeback_multiplexer_output = immediate;
      WB_TARGET_ADDER: writeback_multiplexer_output = target_address_adder;
      WB_CSR:          writeback_multiplexer_output = csr_data_out;
      WB_PC_PLUS_4:    writeback_multiplexer_output = program_counter_plus_4;
      default:         writeback_multiplexer_output = alu_output;
    endcase
  end

  //-----------------------------------------------------------------------------------------------//
  // Load data logic                                                                               //
  //-----------------------------------------------------------------------------------------------//

  always @* begin : load_size_mux
    case (load_size)
      LOAD_SIZE_BYTE:
        load_data = {load_byte_upper_bits, load_byte_data};
      LOAD_SIZE_HALF:
        load_data = {load_half_upper_bits, load_half_data};
      LOAD_SIZE_WORD:
        load_data = read_data;
      default:
        load_data = read_data;
    endcase
  end

  always @* begin : load_byte_data_mux
    case (target_address_adder[1:0])
      2'b00:
        load_byte_data = read_data[7:0];
      2'b01:
        load_byte_data = read_data[15:8];
      2'b10:
        load_byte_data = read_data[23:16];
      2'b11:
        load_byte_data = read_data[31:24];
    endcase
  end

  always @* begin : load_half_data_mux
    case (target_address_adder[1])
      1'b0:
        load_half_data = read_data[15:0];
      1'b1:
        load_half_data = read_data[31:16];
    endcase
  end

  assign load_byte_upper_bits =
    load_unsigned == 1'b1 ?
    24'b0 :
    {24{load_byte_data[7]}};

  assign load_half_upper_bits =
    load_unsigned == 1'b1 ?
    16'b0 :
    {16{load_half_data[15]}};

  //-----------------------------------------------------------------------------------------------//
  // Arithmetic and Logic Unit                                                                     //
  //-----------------------------------------------------------------------------------------------//

  assign alu_2nd_operand =
    alu_2nd_operand_source ?
    rs2_data :
    immediate;

  assign alu_minus_2nd_operand =
    - alu_2nd_operand;

  assign alu_adder_2nd_operand_mux =
    alu_operation_code[3] == 1'b1 ?
    alu_minus_2nd_operand :
    alu_2nd_operand;

  assign alu_sra_result =
    $signed(rs1_data) >>> alu_2nd_operand[4:0];

  assign alu_srl_result =
    rs1_data >> alu_2nd_operand[4:0];

  assign alu_shift_right_mux =
    alu_operation_code[3] == 1'b1 ?
    alu_sra_result :
    alu_srl_result;

  assign alu_sltu_result =
    rs1_data < alu_2nd_operand;

  assign alu_slt_result =
    rs1_data[31] ^ alu_2nd_operand[31] ?
    rs1_data[31] :
    alu_sltu_result;

  always @* begin : operation_result_mux
    case (alu_operation_code[2:0])
      FUNCT3_ADD:
        alu_output =
          rs1_data + alu_adder_2nd_operand_mux;
      FUNCT3_SRL:
        alu_output =
          alu_shift_right_mux;
      FUNCT3_OR:
        alu_output =
          rs1_data | alu_2nd_operand;
      FUNCT3_AND:
        alu_output =
          rs1_data & alu_2nd_operand;
      FUNCT3_XOR:
        alu_output =
          rs1_data ^ alu_2nd_operand;
      FUNCT3_SLT:
        alu_output =
          {31'b0, alu_slt_result};
      FUNCT3_SLTU:
        alu_output =
          {31'b0, alu_sltu_result};
      FUNCT3_SLL:
        alu_output =
          rs1_data << alu_2nd_operand[4:0];
    endcase
  end

endmodule
