-- ================================================================================ --
-- NEORV32 CPU - Central Control Unit                                               --
-- -------------------------------------------------------------------------------- --
-- The NEORV32 RISC-V Processor - https://github.com/stnolting/neorv32              --
-- Copyright (c) NEORV32 contributors.                                              --
-- Copyright (c) 2020 - 2025 Stephan Nolting. All rights reserved.                  --
-- Licensed under the BSD-3-Clause license, see LICENSE for details.                --
-- SPDX-License-Identifier: BSD-3-Clause                                            --
-- ================================================================================ --

library ieee;
use ieee.std_logic_1164.all;
use ieee.numeric_std.all;

library neorv32;
use neorv32.neorv32_package.all;

entity neorv32_cpu_control is
  generic (
    -- General --
    HART_ID          : natural range 0 to 1023;        -- hardware thread ID
    VENDOR_ID        : std_ulogic_vector(31 downto 0); -- vendor ID
    BOOT_ADDR        : std_ulogic_vector(31 downto 0); -- boot address
    DEBUG_PARK_ADDR  : std_ulogic_vector(31 downto 0); -- debug-mode parking loop entry address, 4-byte aligned
    DEBUG_EXC_ADDR   : std_ulogic_vector(31 downto 0); -- debug-mode exception entry address, 4-byte aligned
    -- RISC-V ISA Extensions --
    RISCV_ISA_A      : boolean; -- atomic memory operations extension
    RISCV_ISA_B      : boolean; -- bit-manipulation extension
    RISCV_ISA_C      : boolean; -- compressed extension
    RISCV_ISA_E      : boolean; -- embedded-class register file extension
    RISCV_ISA_M      : boolean; -- mul/div extension
    RISCV_ISA_U      : boolean; -- user mode extension
    RISCV_ISA_Zaamo  : boolean; -- atomic read-modify-write extension
    RISCV_ISA_Zalrsc : boolean; -- atomic reservation-set operations extension
    RISCV_ISA_Zcb    : boolean; -- additional code size reduction instructions
    RISCV_ISA_Zba    : boolean; -- shifted-add bit-manipulation extension
    RISCV_ISA_Zbb    : boolean; -- basic bit-manipulation extension
    RISCV_ISA_Zbkb   : boolean; -- bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc   : boolean; -- carry-less multiplication instructions
    RISCV_ISA_Zbkx   : boolean; -- cryptography crossbar permutation extension
    RISCV_ISA_Zbs    : boolean; -- single-bit bit-manipulation extension
    RISCV_ISA_Zfinx  : boolean; -- 32-bit floating-point extension
    RISCV_ISA_Zibi   : boolean; -- branch with immediate
    RISCV_ISA_Zicntr : boolean; -- base counters
    RISCV_ISA_Zicond : boolean; -- integer conditional operations
    RISCV_ISA_Zihpm  : boolean; -- hardware performance monitors
    RISCV_ISA_Zimop  : boolean; -- may-be-operations
    RISCV_ISA_Zkn    : boolean; -- NIST algorithm suite
    RISCV_ISA_Zknd   : boolean; -- cryptography NIST AES decryption extension
    RISCV_ISA_Zkne   : boolean; -- cryptography NIST AES encryption extension
    RISCV_ISA_Zknh   : boolean; -- cryptography NIST hash extension
    RISCV_ISA_Zks    : boolean; -- ShangMi algorithm suite
    RISCV_ISA_Zksed  : boolean; -- ShangMi block cipher extension
    RISCV_ISA_Zksh   : boolean; -- ShangMi hash extension
    RISCV_ISA_Zkt    : boolean; -- data-independent execution time (for cryptography operations)
    RISCV_ISA_Zmmul  : boolean; -- multiply-only M sub-extension
    RISCV_ISA_Zxcfu  : boolean; -- custom (instr.) functions unit
    RISCV_ISA_Sdext  : boolean; -- external debug mode extension
    RISCV_ISA_Sdtrig : boolean; -- trigger module extension
    RISCV_ISA_Smpmp  : boolean; -- physical memory protection
    -- Tuning Options --
    CPU_CONSTT_BR_EN : boolean  -- constant-time branches
  );
  port (
    -- global control --
    clk_i         : in  std_ulogic;                     -- global clock, rising edge
    rstn_i        : in  std_ulogic;                     -- global reset, low-active, async
    ctrl_o        : out ctrl_bus_t;                     -- main control bus
    -- misc --
    frontend_i    : in  if_bus_t;                       -- front-end status and data
    hwtrig_i      : in  std_ulogic;                     -- hardware trigger
    -- data path interface --
    alu_cp_done_i : in  std_ulogic;                     -- ALU iterative operation done
    alu_cmp_i     : in  std_ulogic_vector(1 downto 0);  -- comparator status
    alu_add_i     : in  std_ulogic_vector(31 downto 0); -- ALU address result
    rf_rs1_i      : in  std_ulogic_vector(31 downto 0); -- register file source 1
    csr_rdata_o   : out std_ulogic_vector(31 downto 0); -- CSR read data
    xcsr_rdata_i  : in  std_ulogic_vector(31 downto 0); -- external CSR read data
    -- interrupts --
    irq_dbg_i     : in  std_ulogic;                     -- debug mode (halt) request
    irq_machine_i : in  std_ulogic_vector(2 downto 0);  -- RISC-V interrupt
    irq_fast_i    : in  std_ulogic_vector(15 downto 0); -- fast interrupts
    -- load/store unit interface --
    lsu_wait_i    : in  std_ulogic;                     -- wait for data bus
    lsu_mar_i     : in  std_ulogic_vector(31 downto 0); -- memory address register
    lsu_err_i     : in  std_ulogic_vector(3 downto 0)   -- alignment/access errors
  );
end neorv32_cpu_control;

architecture neorv32_cpu_control_rtl of neorv32_cpu_control is

  -- execution micro sequencer --
  type exec_state_t is (S_RESTART, S_DISPATCH, S_TRAP_ENTER, S_TRAP_EXIT, S_EXECUTE,
                        S_ALU_WAIT, S_BRANCH, S_MEM_REQ, S_MEM_RSP, S_SYSTEM, S_SLEEP);
  type exec_t is record
    state : exec_state_t;
    ir    : std_ulogic_vector(31 downto 0); -- instruction word being executed right now
    ci    : std_ulogic;                     -- current instruction is decompressed instruction
    pc    : std_ulogic_vector(31 downto 0); -- current PC (current instruction)
    pc2   : std_ulogic_vector(31 downto 0); -- next PC (next linear instruction)
  end record;
  signal exec, exec_nxt : exec_t;
  signal ctrl, ctrl_nxt : ctrl_bus_t; -- CPU control bus

  -- trap controller --
  type trap_t is record
    exc_buf   : std_ulogic_vector(exc_width_c-1 downto 0); -- synchronous exception buffer (one bit per exception)
    exc_fire  : std_ulogic;                                -- set if there is a valid source in the exception buffer
    irq_pnd   : std_ulogic_vector(irq_width_c-1 downto 0); -- pending interrupt
    irq_buf   : std_ulogic_vector(irq_width_c-1 downto 0); -- asynchronous exception/interrupt buffer (one bit per interrupt)
    irq_fire  : std_ulogic_vector(1 downto 0);             -- set if an interrupt is actually kicking in
    cause     : std_ulogic_vector(6 downto 0);             -- trap ID for cause CSRs
    pc        : std_ulogic_vector(31 downto 0);            -- trap program counter
    env_pend  : std_ulogic; -- pending start of trap environment
    env_enter : std_ulogic; -- enter trap environment
    env_exit  : std_ulogic; -- leave trap environment
    instr_be  : std_ulogic; -- instruction fetch bus error
    instr_ma  : std_ulogic; -- instruction fetch misaligned address
    instr_il  : std_ulogic; -- illegal instruction
    ecall     : std_ulogic; -- ecall instruction
    ebreak    : std_ulogic; -- ebreak instruction
  end record;
  signal trap : trap_t;

  -- control and status registers (CSR) --
  type csr_t is record
    prv_level    : std_ulogic; -- current privilege level
    mstatus_mie  : std_ulogic; -- machine-mode IRQ enable
    mstatus_mpie : std_ulogic; -- previous machine-mode IRQ enable
    mstatus_mpp  : std_ulogic; -- machine previous privilege mode
    mstatus_mprv : std_ulogic; -- effective privilege level for load/stores
    mstatus_tw   : std_ulogic; -- do not allow user mode to execute WFI instruction when set
    mie_msi      : std_ulogic; -- machine software interrupt enable
    mie_mei      : std_ulogic; -- machine external interrupt enable
    mie_mti      : std_ulogic; -- machine timer interrupt enable
    mie_firq     : std_ulogic_vector(15 downto 0); -- fast interrupt enable
    mepc         : std_ulogic_vector(31 downto 0); -- machine exception PC
    mcause       : std_ulogic_vector(5 downto 0);  -- machine trap cause
    mtvec        : std_ulogic_vector(31 downto 0); -- machine trap-handler base address
    mtval        : std_ulogic_vector(31 downto 0); -- machine bad address or instruction
    mtinst       : std_ulogic_vector(31 downto 0); -- machine trap instruction
    mscratch     : std_ulogic_vector(31 downto 0); -- machine scratch register
    mcounteren   : std_ulogic_vector(2 downto 0);  -- machine counter access enable: instruction, time, cycle
    dcsr_ebreakm : std_ulogic; -- behavior of ebreak instruction in m-mode
    dcsr_ebreaku : std_ulogic; -- behavior of ebreak instruction in u-mode
    dcsr_step    : std_ulogic; -- single-step mode
    dcsr_prv     : std_ulogic; -- current privilege level when entering debug mode
    dcsr_cause   : std_ulogic_vector(2 downto 0);  -- why was debug mode entered
    dpc          : std_ulogic_vector(31 downto 0); -- mode program counter
    dscratch0    : std_ulogic_vector(31 downto 0); -- debug mode scratch register 0
  end record;
  signal csr : csr_t;
  signal csr_wdata, csr_rdata, dcsr_rdata : std_ulogic_vector(31 downto 0); -- read/write data

  -- debug-mode controller --
  type debug_ctrl_t is record
    run, trig_halt, trig_hw, trig_break, trig_step : std_ulogic;
  end record;
  signal debug_ctrl : debug_ctrl_t;

  -- misc/helpers --
  signal branch_taken : std_ulogic; -- branch condition true or unconditional jump
  signal monitor_cnt  : std_ulogic_vector(alu_cp_tmo_c downto 0); -- execution monitor cycle counter
  signal csr_valid    : std_ulogic_vector(2 downto 0); -- CSR access: [2] implemented, [1] r/w access, [0] privilege
  signal illegal_cmd  : std_ulogic; -- illegal instruction check
  signal cnt_event    : std_ulogic_vector(10 downto 0); -- counter events
  signal ebreak_trig  : std_ulogic; -- environment break exception trigger
  signal trap_env     : std_ulogic_vector(6 downto 0); -- environment call cause-value helper

begin

  -- ****************************************************************************************************************************
  -- Instruction Execution
  -- ****************************************************************************************************************************

  -- Branch Condition Check -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  branch_check: process(exec, alu_cmp_i)
  begin
    if (exec.ir(instr_opcode_lsb_c+2) = '0') then -- conditional branch
      if (exec.ir(instr_funct3_msb_c) = '0') then -- bge / bne
        branch_taken <= alu_cmp_i(cmp_equal_c) xor exec.ir(instr_funct3_lsb_c);
      else -- blt(u) / bge(u)
        branch_taken <= alu_cmp_i(cmp_less_c) xor exec.ir(instr_funct3_lsb_c);
      end if;
    else -- unconditional branch are always taken
      branch_taken <= '1';
    end if;
  end process branch_check;


  -- Execution Micro Sequencer Sync ---------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  exec_sync: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl       <= ctrl_bus_zero_c;
      exec.state <= S_RESTART;
      exec.ir    <= (others => '0');
      exec.ci    <= '0';
      exec.pc    <= BOOT_ADDR(31 downto 2) & "00"; -- 32-bit-aligned boot address
      exec.pc2   <= BOOT_ADDR(31 downto 2) & "00"; -- 32-bit-aligned boot address
    elsif rising_edge(clk_i) then
      ctrl <= ctrl_nxt;
      exec <= exec_nxt;
    end if;
  end process exec_sync;


  -- Execution Micro Sequencer Comb ---------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  exec_comb: process(exec, debug_ctrl, trap, hwtrig_i, frontend_i, csr, ctrl, alu_cp_done_i, lsu_wait_i, alu_add_i, branch_taken)
    variable opcode_v : std_ulogic_vector(6 downto 0);
    variable funct7_v : std_ulogic_vector(6 downto 0);
    variable funct3_v : std_ulogic_vector(2 downto 0);
  begin
    -- shortcuts --
    opcode_v := exec.ir(instr_opcode_msb_c downto instr_opcode_lsb_c+2) & "11"; -- simplified rv32 opcode
    funct7_v := exec.ir(instr_funct7_msb_c downto instr_funct7_lsb_c);
    funct3_v := exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c);

    -- defaults --
    exec_nxt          <= exec;
    trap.env_enter    <= '0';
    trap.env_exit     <= '0';
    trap.instr_be     <= '0';
    trap.instr_ma     <= '0';
    trap.ecall        <= '0';
    trap.ebreak       <= '0';
    ctrl_nxt          <= ctrl_bus_zero_c; -- all zero/off by default (ALU operation = ZERO, ALU.adder_out = ADD)
    ctrl_nxt.csr_addr <= ctrl.csr_addr;   -- keep previous CSR address
    ctrl_nxt.lsu_rmw  <= ctrl.lsu_rmw;    -- keep memory access type
    ctrl_nxt.lsu_rsv  <= ctrl.lsu_rsv;
    ctrl_nxt.lsu_rw   <= ctrl.lsu_rw;

    -- immediate --
    case opcode_v is
      when opcode_store_c  => ctrl_nxt.alu_imm <= replicate_f(exec.ir(31), 21) & exec.ir(30 downto 25) & exec.ir(11 downto 7); -- S-type
      when opcode_branch_c => ctrl_nxt.alu_imm <= replicate_f(exec.ir(31), 20) & exec.ir(7) & exec.ir(30 downto 25) & exec.ir(11 downto 8) & '0'; -- B-type
      when opcode_lui_c |
           opcode_auipc_c  => ctrl_nxt.alu_imm <= exec.ir(31 downto 12) & x"000"; -- U-type
      when opcode_jal_c    => ctrl_nxt.alu_imm <= replicate_f(exec.ir(31), 12) & exec.ir(19 downto 12) & exec.ir(20) & exec.ir(30 downto 21) & '0'; -- J-type
      when opcode_amo_c    => ctrl_nxt.alu_imm <= (others => '0'); -- atomic memory access
      when others          => ctrl_nxt.alu_imm <= replicate_f(exec.ir(31), 21) & exec.ir(30 downto 21) & exec.ir(20); -- I-type
    end case;

    -- ALU sign control --
    if (opcode_v(4) = '1') then -- ALU ops
      ctrl_nxt.alu_unsigned <= funct3_v(0); -- unsigned ALU operation? (SLTIU, SLTU)
    else -- branches
      ctrl_nxt.alu_unsigned <= funct3_v(1); -- unsigned branch? (BLTU, BGEU)
    end if;

    -- ALU operands --
    if (opcode_v = opcode_auipc_c) or (opcode_v = opcode_jal_c) or (opcode_v = opcode_branch_c) then -- operand A = PC?
      ctrl_nxt.alu_opa_mux <= '1';
    end if;
    if (opcode_v /= opcode_alu_c) then -- operand B = immediate?
      ctrl_nxt.alu_opb_mux <= '1';
    end if;

    -- state machine --
    case exec.state is

      when S_RESTART => -- reset and restart instruction fetch at next-PC
      -- ------------------------------------------------------------
        ctrl_nxt.rf_zero  <= '1'; -- [house keeping] force writing zero to x0 in case it is an array register
        ctrl_nxt.if_reset <= '1';
        exec_nxt.state    <= S_DISPATCH;

      when S_DISPATCH => -- wait for ISSUE ENGINE to emit a valid instruction word
      -- ------------------------------------------------------------
        -- prepare update of next-PC (pc2) in S_EXECUTE state --
        ctrl_nxt.alu_opa_mux <= '1'; -- opa = current PC
        ctrl_nxt.alu_opb_mux <= '1'; -- opb = immediate = +2/4
        if RISCV_ISA_C and (frontend_i.compr = '1') then
          ctrl_nxt.alu_imm <= x"00000002";
        else
          ctrl_nxt.alu_imm <= x"00000004";
        end if;
        -- dispatch instruction --
        if (trap.env_pend = '1') or (trap.exc_fire = '1') then -- pending trap or pending exception (fast)
          exec_nxt.state <= S_TRAP_ENTER;
        elsif (frontend_i.valid = '1') and (hwtrig_i = '0') then -- new instruction word available and no pending HW trigger
          trap.instr_be  <= frontend_i.fault; -- access fault during instruction fetch
          exec_nxt.ci    <= frontend_i.compr; -- this is a decompressed instruction
          exec_nxt.ir    <= frontend_i.instr; -- actual instruction word
          exec_nxt.pc    <= exec.pc2(31 downto 1) & '0';
          exec_nxt.state <= S_EXECUTE; -- start executing new instruction
          if (frontend_i.instr(instr_opcode_msb_c downto instr_opcode_lsb_c+2) = opcode_system_c(6 downto 2)) then
            ctrl_nxt.csr_addr <= frontend_i.instr(instr_imm12_msb_c downto instr_imm12_lsb_c); -- reduce switching activity on csr_addr net
          end if;
        end if;

      when S_TRAP_ENTER => -- enter trap environment and jump to trap vector
      -- ------------------------------------------------------------
        if (trap.cause(5) = '1') and RISCV_ISA_Sdext then -- debug mode entry
          exec_nxt.pc2 <= DEBUG_PARK_ADDR(31 downto 2) & "00"; -- start at "parking loop" <normal_entry>
        elsif (debug_ctrl.run = '1') and RISCV_ISA_Sdext then -- any other trap INSIDE debug mode
          exec_nxt.pc2 <= DEBUG_EXC_ADDR(31 downto 2) & "00"; -- start at "parking loop" <exception_entry>
        elsif (csr.mtvec(0) = '1') and (trap.cause(6) = '1') then -- M-mode trap: vectored mode and interrupt
          exec_nxt.pc2 <= csr.mtvec(31 downto 7) & trap.cause(4 downto 0) & "00"; -- PC = mtvec + 4 * mcause
        else -- M-mode trap: direct mode
          exec_nxt.pc2 <= csr.mtvec(31 downto 2) & "00"; -- PC = mtvec
        end if;
        trap.env_enter <= '1';
        exec_nxt.state <= S_RESTART; -- restart instruction fetch

      when S_TRAP_EXIT => -- return from trap environment and jump to trap PC
      -- ------------------------------------------------------------
        if (debug_ctrl.run = '1') and RISCV_ISA_Sdext then -- debug mode exit
          exec_nxt.pc2 <= csr.dpc(31 downto 1) & '0';
        else -- normal end of trap
          exec_nxt.pc2 <= csr.mepc(31 downto 1) & '0';
        end if;
        trap.env_exit  <= '1';
        exec_nxt.state <= S_RESTART; -- restart instruction fetch

      when S_EXECUTE => -- decode and prepare execution (FSM will be here for exactly 1 cycle in any case)
      -- ------------------------------------------------------------
        exec_nxt.pc2 <= alu_add_i(31 downto 1) & '0'; -- next PC = PC + immediate
        case opcode_v is

          -- register/immediate ALU operation --
          when opcode_alu_c | opcode_alui_c =>

            -- ALU core operation --
            case funct3_v is
              when funct3_sadd_c => ctrl_nxt.alu_op <= alu_op_add_c; -- ADD(I), SUB
              when funct3_slt_c  => ctrl_nxt.alu_op <= alu_op_slt_c; -- SLT(I)
              when funct3_sltu_c => ctrl_nxt.alu_op <= alu_op_slt_c; -- SLTU(I)
              when funct3_xor_c  => ctrl_nxt.alu_op <= alu_op_xor_c; -- XOR(I)
              when funct3_or_c   => ctrl_nxt.alu_op <= alu_op_or_c;  -- OR(I)
              when funct3_and_c  => ctrl_nxt.alu_op <= alu_op_and_c; -- AND(I)
              when others        => ctrl_nxt.alu_op <= alu_op_zero_c;
            end case;

            -- addition/subtraction control --
            if (funct3_v(2 downto 1) = funct3_slt_c(2 downto 1)) or -- SLT(I), SLTU(I)
               ((funct3_v = funct3_sadd_c) and (opcode_v(5) = '1') and (exec.ir(instr_funct7_msb_c-1) = '1')) then -- SUB
              ctrl_nxt.alu_sub <= '1';
            end if;

            -- is base rv32i/e ALU[I] instruction (excluding shifts)? --
            if ((opcode_v(5) = '0') and (funct3_v /= funct3_sll_c) and (funct3_v /= funct3_sr_c)) or -- base ALUI instruction (excluding SLLI, SRLI, SRAI)
               ((opcode_v(5) = '1') and (((funct3_v = funct3_sadd_c) and (funct7_v = "0000000")) or ((funct3_v = funct3_sadd_c) and (funct7_v = "0100000")) or
                                         ((funct3_v = funct3_slt_c)  and (funct7_v = "0000000")) or ((funct3_v = funct3_sltu_c) and (funct7_v = "0000000")) or
                                         ((funct3_v = funct3_xor_c)  and (funct7_v = "0000000")) or ((funct3_v = funct3_or_c)   and (funct7_v = "0000000")) or
                                         ((funct3_v = funct3_and_c)  and (funct7_v = "0000000")))) then -- base ALU instruction (excluding SLL, SRL, SRA)
              ctrl_nxt.rf_wb_en <= '1'; -- valid RF write-back (won't happen if exception)
              exec_nxt.state    <= S_DISPATCH;
            else -- [NOTE] illegal ALU[I] instructions are handled as multi-cycle operations that will time-out if no ALU co-processor responds
              ctrl_nxt.alu_cp_alu <= '1'; -- trigger ALU[I] opcode co-processor
              exec_nxt.state      <= S_ALU_WAIT;
            end if;

          -- load upper immediate --
          when opcode_lui_c =>
            ctrl_nxt.alu_op   <= alu_op_movb_c; -- pass immediate
            ctrl_nxt.rf_wb_en <= '1'; -- valid RF write-back (won't happen if exception)
            exec_nxt.state    <= S_DISPATCH;

          -- add upper immediate to PC --
          when opcode_auipc_c =>
            ctrl_nxt.alu_op   <= alu_op_add_c; -- add PC and immediate
            ctrl_nxt.rf_wb_en <= '1'; -- valid RF write-back (won't happen if exception)
            exec_nxt.state    <= S_DISPATCH;

          -- memory access --
          when opcode_load_c | opcode_store_c | opcode_amo_c =>
            if RISCV_ISA_Zaamo and (opcode_v(2) = opcode_amo_c(2)) and (exec.ir(instr_funct5_lsb_c+1) = '0') then -- atomic read-modify-write operation
              ctrl_nxt.lsu_rmw <= '1'; -- read-modify-write
              ctrl_nxt.lsu_rsv <= '0';
              ctrl_nxt.lsu_rw  <= '0'; -- executed as single load for the CPU control logic
            elsif RISCV_ISA_Zalrsc and (opcode_v(2) = opcode_amo_c(2)) and (exec.ir(instr_funct5_lsb_c+1) = '1') then -- atomic reservation-set operation
              ctrl_nxt.lsu_rmw <= '0';
              ctrl_nxt.lsu_rsv <= '1'; -- reservation-operation
              ctrl_nxt.lsu_rw  <= exec.ir(instr_funct5_lsb_c);
            else -- normal load/store
              ctrl_nxt.lsu_rmw <= '0';
              ctrl_nxt.lsu_rsv <= '0';
              ctrl_nxt.lsu_rw  <= exec.ir(instr_opcode_lsb_c+5);
            end if;
            exec_nxt.state <= S_MEM_REQ;

          -- branch / jump-and-link (with register) --
          when opcode_branch_c | opcode_jal_c | opcode_jalr_c =>
            exec_nxt.state <= S_BRANCH;

          -- memory fence operations --
          when opcode_fence_c =>
            ctrl_nxt.lsu_fence <= not exec.ir(instr_funct3_lsb_c); -- data fence
            ctrl_nxt.if_fence  <= exec.ir(instr_funct3_lsb_c); -- instruction fence
            exec_nxt.state     <= S_RESTART; -- reset instruction fetch & IPB via branch to next-PC (actually only required for fence.i)

          -- FPU: floating-point operations --
          when opcode_fpu_c =>
            ctrl_nxt.alu_cp_fpu <= '1';
            exec_nxt.state      <= S_ALU_WAIT; -- will be aborted by monitor timeout if FPU is not implemented

          -- CFU: custom RISC-V instructions --
          when opcode_cust0_c | opcode_cust1_c =>
            ctrl_nxt.alu_cp_cfu <= '1';
            exec_nxt.state      <= S_ALU_WAIT; -- will be aborted by monitor timeout if CFU is not implemented

          -- environment/CSR operation or ILLEGAL opcode --
          when others =>
            if (funct3_v /= funct3_env_c) and (funct3_v /= funct3_zimop_c) then -- no CSR read if environment or may-be operation
              ctrl_nxt.csr_re <= '1';
            end if;
            exec_nxt.state <= S_SYSTEM;

        end case;

      when S_ALU_WAIT => -- wait for multi-cycle ALU co-processor operation to finish or trap
      -- ------------------------------------------------------------
        ctrl_nxt.alu_op   <= alu_op_cp_c;
        ctrl_nxt.rf_wb_en <= alu_cp_done_i; -- valid RF write-back (won't happen if exception)
        if (alu_cp_done_i = '1') or (or_reduce_f(trap.exc_buf(exc_ialign_c downto exc_iaccess_c)) = '1') then
          exec_nxt.state <= S_DISPATCH;
        end if;

      when S_BRANCH => -- update next-PC on taken branches and jumps
      -- ------------------------------------------------------------
        if CPU_CONSTT_BR_EN or (branch_taken = '1') then
          ctrl_nxt.if_reset <= '1'; -- reset instruction fetch to restart at next-PC (pc2)
        end if;
        if (branch_taken = '1') then -- taken/unconditional branch
          trap.instr_ma <= alu_add_i(1) and bool_to_ulogic_f(not RISCV_ISA_C); -- branch destination misaligned?
          exec_nxt.pc2  <= alu_add_i(31 downto 1) & '0';
        end if;
        ctrl_nxt.pc_ret   <= exec.pc2(31 downto 1) & '0'; -- output return address
        ctrl_nxt.rf_wb_en <= exec.ir(instr_opcode_lsb_c+2); -- save return address if link operation (won't happen if exception)
        exec_nxt.state    <= S_DISPATCH;

      when S_MEM_REQ => -- trigger memory request
      -- ------------------------------------------------------------
        if (or_reduce_f(trap.exc_buf(exc_ialign_c downto exc_iaccess_c)) = '0') then -- memory request if no instruction exception
          ctrl_nxt.lsu_req <= '1';
          exec_nxt.state   <= S_MEM_RSP;
        else
          exec_nxt.state <= S_DISPATCH;
        end if;

      when S_MEM_RSP => -- wait for memory response
      -- ------------------------------------------------------------
        if (lsu_wait_i = '0') or (or_reduce_f(trap.exc_buf(exc_laccess_c downto exc_salign_c)) = '1') then -- bus response or load/store exception
          ctrl_nxt.rf_wb_en <= (not ctrl.lsu_rw) or ctrl.lsu_rsv or ctrl.lsu_rmw; -- write to RF if read operation (won't happen in case of exception)
          exec_nxt.state    <= S_DISPATCH;
        end if;

      when S_SYSTEM => -- CSR/ENVIRONMENT operation; no effect if illegal instruction
      -- ------------------------------------------------------------
        exec_nxt.state <= S_DISPATCH; -- default
        if (or_reduce_f(trap.exc_buf(exc_ialign_c downto exc_iaccess_c)) = '0') then -- non-illegal instruction
          if (funct3_v = funct3_env_c) then -- environment instruction
            case exec.ir(instr_imm12_lsb_c+2 downto instr_imm12_lsb_c) is -- three LSBs are sufficient here
              when "000"  => trap.ecall     <= '1'; -- ecall
              when "001"  => trap.ebreak    <= '1'; -- ebreak
              when "010"  => exec_nxt.state <= S_TRAP_EXIT; -- xret
              when "101"  => exec_nxt.state <= S_SLEEP; -- wfi
              when others => exec_nxt.state <= S_DISPATCH; -- illegal or CSR operation
            end case;
          elsif (funct3_v /= funct3_zimop_c) and -- write to CSR if not may-be-operation
                (((funct3_v = funct3_csrrw_c) or (funct3_v = funct3_csrrwi_c)) or (exec.ir(instr_rd_msb_c downto instr_rd_lsb_c) = "00000")) then
            ctrl_nxt.csr_we <= '1'; -- CSRRW[I]: always write CSR; CSRR[S/C][I]: write CSR if rs1/imm5 is NOT zero
          end if;
        end if;
        -- always write to register file; environment operations have rd = zero so this does not hurt --
        ctrl_nxt.rf_wb_en <= '1'; -- won't happen if exception

      when others => -- S_SLEEP / undefined state: halt CPU
      -- ------------------------------------------------------------
        if (or_reduce_f(trap.irq_buf) = '1') or (trap.exc_fire = '1') then -- wake up on enabled pending IRQ or if pending exception
          exec_nxt.state <= S_DISPATCH;
        end if;

    end case;
  end process exec_comb;


  -- CPU Control Bus Output -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  -- instruction fetch --
  ctrl_o.if_fence     <= ctrl.if_fence;
  ctrl_o.if_reset     <= ctrl_nxt.if_reset; -- this is an ASYNC control signal!
  ctrl_o.if_ready     <= '1' when (exec.state = S_DISPATCH) else '0';
  -- program counter --
  ctrl_o.pc_cur       <= exec.pc(31 downto 1) & '0';
  ctrl_o.pc_nxt       <= exec.pc2(31 downto 1) & '0';
  ctrl_o.pc_ret       <= ctrl.pc_ret(31 downto 1) & '0';
  -- register file --
  ctrl_o.rf_wb_en     <= ctrl.rf_wb_en and (not or_reduce_f(trap.exc_buf(exc_laccess_c downto exc_iaccess_c))); -- no sync. exception
  ctrl_o.rf_rs1       <= exec.ir(instr_rs1_msb_c downto instr_rs1_lsb_c);
  ctrl_o.rf_rs2       <= exec.ir(instr_rs2_msb_c downto instr_rs2_lsb_c);
  ctrl_o.rf_rd        <= exec.ir(instr_rd_msb_c downto instr_rd_lsb_c);
  ctrl_o.rf_zero      <= ctrl.rf_zero;
  -- alu --
  ctrl_o.alu_op       <= ctrl.alu_op;
  ctrl_o.alu_sub      <= ctrl.alu_sub;
  ctrl_o.alu_opa_mux  <= ctrl.alu_opa_mux;
  ctrl_o.alu_opb_mux  <= ctrl.alu_opb_mux;
  ctrl_o.alu_unsigned <= ctrl.alu_unsigned;
  ctrl_o.alu_imm      <= ctrl.alu_imm;
  ctrl_o.alu_cp_alu   <= ctrl.alu_cp_alu and (not or_reduce_f(trap.exc_buf(exc_ialign_c downto exc_iaccess_c))); -- trigger if no instruction exception
  ctrl_o.alu_cp_cfu   <= ctrl.alu_cp_cfu and (not or_reduce_f(trap.exc_buf(exc_ialign_c downto exc_iaccess_c))); -- trigger if no instruction exception
  ctrl_o.alu_cp_fpu   <= ctrl.alu_cp_fpu and (not or_reduce_f(trap.exc_buf(exc_ialign_c downto exc_iaccess_c))); -- trigger if no instruction exception
  -- load/store unit --
  ctrl_o.lsu_req      <= ctrl.lsu_req;
  ctrl_o.lsu_rw       <= ctrl.lsu_rw;
  ctrl_o.lsu_rmw      <= ctrl.lsu_rmw;
  ctrl_o.lsu_rsv      <= ctrl.lsu_rsv;
  ctrl_o.lsu_mo_we    <= '1' when (exec.state = S_MEM_REQ) else '0'; -- write memory output registers (data & address)
  ctrl_o.lsu_fence    <= ctrl.lsu_fence;
  ctrl_o.lsu_priv     <= csr.mstatus_mpp when (csr.mstatus_mprv = '1') else csr.prv_level; -- effective privilege level for loads/stores in M-mode
  -- control and status registers --
  ctrl_o.csr_we       <= ctrl.csr_we;
  ctrl_o.csr_re       <= ctrl.csr_re;
  ctrl_o.csr_addr     <= ctrl.csr_addr;
  ctrl_o.csr_wdata    <= csr_wdata;
  -- counter events --
  ctrl_o.cnt_event    <= cnt_event;
  -- instruction word bit fields --
  ctrl_o.ir_funct3    <= exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c);
  ctrl_o.ir_funct12   <= exec.ir(instr_imm12_msb_c downto instr_imm12_lsb_c);
  ctrl_o.ir_opcode    <= exec.ir(instr_opcode_msb_c downto instr_opcode_lsb_c);
  -- status --
  ctrl_o.cpu_priv     <= csr.prv_level;
  ctrl_o.cpu_trap     <= trap.env_enter;
  ctrl_o.cpu_sync_exc <= trap.exc_fire;
  ctrl_o.cpu_debug    <= debug_ctrl.run;


  -- Counter Events -------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  cnt_event(cnt_event_cy_c)       <= '0' when (exec.state = S_SLEEP)                                                 else '1'; -- active cycle
  cnt_event(cnt_event_tm_c)       <= '0';
  cnt_event(cnt_event_ir_c)       <= '1' when (exec.state = S_EXECUTE)                                               else '0'; -- retired (=executed) instr.
  cnt_event(cnt_event_compr_c)    <= '1' when (exec.state = S_EXECUTE)  and (exec.ci = '1')                          else '0'; -- executed compressed instr.
  cnt_event(cnt_event_wait_dis_c) <= '1' when (exec.state = S_DISPATCH) and (frontend_i.valid = '0')                 else '0'; -- instruction dispatch wait
  cnt_event(cnt_event_wait_alu_c) <= '1' when (exec.state = S_ALU_WAIT)                                              else '0'; -- multi-cycle ALU wait
  cnt_event(cnt_event_branch_c)   <= '1' when (exec.state = S_BRANCH)                                                else '0'; -- executed branch instruction
  cnt_event(cnt_event_ctrlflow_c) <= '1' when (ctrl.if_reset = '1') and (exec.ir(6 downto 0) /= opcode_fence_c)      else '0'; -- control flow transfer
  cnt_event(cnt_event_load_c)     <= '1' when (ctrl.lsu_req = '1') and ((ctrl.lsu_rw = '0') or (ctrl.lsu_rmw = '1')) else '0'; -- executed load operation
  cnt_event(cnt_event_store_c)    <= '1' when (ctrl.lsu_req = '1') and ((ctrl.lsu_rw = '1') or (ctrl.lsu_rmw = '1')) else '0'; -- executed store operation
  cnt_event(cnt_event_wait_lsu_c) <= '1' when (ctrl.lsu_req = '0') and (exec.state = S_MEM_RSP)                      else '0'; -- load/store memory wait


  -- ****************************************************************************************************************************
  -- Illegal Instruction Detection
  -- ****************************************************************************************************************************

  -- CSR Access Check -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_check: process(ctrl, exec, csr, debug_ctrl)
  begin
    -- ------------------------------------------------------------
    -- Available at all
    -- ------------------------------------------------------------
    case ctrl.csr_addr is

      -- floating-point-unit CSRs --
      when csr_fflags_c | csr_frm_c | csr_fcsr_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zfinx);

      -- machine trap setup/handling, environment/information registers, etc. --
      when csr_mstatus_c  | csr_mstatush_c      | csr_misa_c      | csr_mie_c     | csr_mtvec_c  |
           csr_mscratch_c | csr_mepc_c          | csr_mcause_c    | csr_mip_c     | csr_mtval_c  |
           csr_mtinst_c   | csr_mcountinhibit_c | csr_mvendorid_c | csr_marchid_c | csr_mimpid_c |
           csr_mhartid_c  | csr_mconfigptr_c    | csr_mxisa_c =>
        csr_valid(2) <= '1';

      -- machine-controlled user-mode CSRs --
      when csr_mcounteren_c | csr_menvcfg_c | csr_menvcfgh_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_U);

      -- physical memory protection (PMP) --
      when csr_pmpcfg0_c   | csr_pmpcfg1_c   | csr_pmpcfg2_c   | csr_pmpcfg3_c   | -- lowest 4 configuration registers only
           csr_pmpaddr0_c  | csr_pmpaddr1_c  | csr_pmpaddr2_c  | csr_pmpaddr3_c  | -- lowest 16 address registers only
           csr_pmpaddr4_c  | csr_pmpaddr5_c  | csr_pmpaddr6_c  | csr_pmpaddr7_c  |
           csr_pmpaddr8_c  | csr_pmpaddr9_c  | csr_pmpaddr10_c | csr_pmpaddr11_c |
           csr_pmpaddr12_c | csr_pmpaddr13_c | csr_pmpaddr14_c | csr_pmpaddr15_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Smpmp);

      -- hardware performance monitors (HPM) --
      when csr_mhpmcounter3_c   | csr_mhpmcounter4_c   | csr_mhpmcounter5_c   | csr_mhpmcounter6_c   | csr_mhpmcounter7_c   |
           csr_mhpmcounter8_c   | csr_mhpmcounter9_c   | csr_mhpmcounter10_c  | csr_mhpmcounter11_c  | csr_mhpmcounter12_c  |
           csr_mhpmcounter13_c  | csr_mhpmcounter14_c  | csr_mhpmcounter15_c  | -- machine counters LOW
           csr_mhpmcounter3h_c  | csr_mhpmcounter4h_c  | csr_mhpmcounter5h_c  | csr_mhpmcounter6h_c  | csr_mhpmcounter7h_c  |
           csr_mhpmcounter8h_c  | csr_mhpmcounter9h_c  | csr_mhpmcounter10h_c | csr_mhpmcounter11h_c | csr_mhpmcounter12h_c |
           csr_mhpmcounter13h_c | csr_mhpmcounter14h_c | csr_mhpmcounter15h_c | -- machine counters HIGH
           csr_mhpmevent3_c     | csr_mhpmevent4_c     | csr_mhpmevent5_c     | csr_mhpmevent6_c     | csr_mhpmevent7_c     |
           csr_mhpmevent8_c     | csr_mhpmevent9_c     | csr_mhpmevent10_c    | csr_mhpmevent11_c    | csr_mhpmevent12_c    |
           csr_mhpmevent13_c    | csr_mhpmevent14_c    | csr_mhpmevent15_c => -- machine event configuration
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zihpm);

      -- counter and timer CSRs --
      when csr_cycle_c | csr_mcycle_c | csr_instret_c | csr_minstret_c | csr_cycleh_c | csr_mcycleh_c | csr_instreth_c | csr_minstreth_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zicntr);

      -- debug-mode CSRs --
      when csr_dcsr_c | csr_dpc_c | csr_dscratch0_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Sdext);

      -- trigger module CSRs --
      when csr_tselect_c | csr_tdata1_c | csr_tdata2_c | csr_tinfo_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Sdtrig);

      -- undefined / not implemented --
      when others =>
        csr_valid(2) <= '0';

    end case;

    -- ------------------------------------------------------------
    -- R/W capabilities
    -- ------------------------------------------------------------
    if (ctrl.csr_addr(11 downto 10) = "11") and -- CSR is read-only
       ((exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_csrrw_c)  or -- will always write to CSR
        (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_csrrwi_c) or -- will always write to CSR
        (exec.ir(instr_rs1_msb_c downto instr_rs1_lsb_c) /= "00000")) then -- clear/set instructions: write to CSR only if rs1/imm5 is NOT zero
      csr_valid(1) <= '0'; -- invalid access
    else
      csr_valid(1) <= '1'; -- access granted
    end if;

    -- ------------------------------------------------------------
    -- Privilege level
    -- ------------------------------------------------------------
    if (ctrl.csr_addr(11 downto 4) = csr_dcsr_c(11 downto 4)) and -- debug-mode-only CSR?
       RISCV_ISA_Sdext and (debug_ctrl.run = '0') then -- debug-mode implemented and not running?
      csr_valid(0) <= '0'; -- invalid access
    elsif RISCV_ISA_Zicntr and RISCV_ISA_U and (csr.prv_level = '0') and -- any user-mode counters available and in user-mode?
          (ctrl.csr_addr(11 downto 8) = csr_cycle_c(11 downto 8)) and -- user-mode counter access
          (((ctrl.csr_addr(1 downto 0) = csr_cycle_c(1 downto 0)) and (csr.mcounteren(0) = '0')) or -- illegal access to cycle
           ((ctrl.csr_addr(1 downto 0) = csr_instret_c(1 downto 0)) and (csr.mcounteren(2) = '0'))) then -- illegal access to instret
      csr_valid(0) <= '0'; -- invalid access
    elsif (ctrl.csr_addr(9 downto 8) /= "00") and (csr.prv_level = '0') then -- invalid privilege level
      csr_valid(0) <= '0'; -- invalid access
    else
      csr_valid(0) <= '1'; -- access granted
    end if;
  end process csr_check;


  -- Illegal Instruction Check --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  illegal_check: process(exec, csr, csr_valid, debug_ctrl)
  begin
    illegal_cmd <= '1'; -- default: illegal
    case exec.ir(instr_opcode_msb_c downto instr_opcode_lsb_c) is -- check entire opcode

      -- U-type instructions --
      when opcode_lui_c | opcode_auipc_c | opcode_jal_c =>
        illegal_cmd <= '0'; -- all encodings are valid

      -- jump-and-link with register --
      when opcode_jalr_c =>
        if (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = "000") then
          illegal_cmd <= '0';
        end if;

      -- conditional branch --
      when opcode_branch_c =>
        if (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c+1) /= "01") or RISCV_ISA_Zibi then
          illegal_cmd <= '0';
        end if;

      -- memory load --
      when opcode_load_c =>
        case exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_lb_c | funct3_lh_c | funct3_lw_c | funct3_lbu_c | funct3_lhu_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      -- memory store --
      when opcode_store_c =>
        case exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_sb_c | funct3_sh_c | funct3_sw_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      -- atomic memory operation --
      when opcode_amo_c =>
        if (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = "010") then -- word-quantity only
          case exec.ir(instr_funct5_msb_c downto instr_funct5_lsb_c) is
            when "00001" | "00000" | "00100" | "01100" | "01000" | "10000" | "10100" | "11000" | "11100" => illegal_cmd <= not bool_to_ulogic_f(RISCV_ISA_Zaamo);
            when "00010" | "00011" => illegal_cmd <= not bool_to_ulogic_f(RISCV_ISA_Zalrsc);
            when others => illegal_cmd <= '1';
          end case;
        end if;

      -- ALU[I] / FPU / custom operations --
      when opcode_alu_c | opcode_alui_c | opcode_fpu_c | opcode_cust0_c | opcode_cust1_c =>
        illegal_cmd <= '0'; -- [NOTE] valid if not terminated/invalidated by the "instruction execution monitor"

      -- memory ordering --
      when opcode_fence_c =>
        if (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c+1) = funct3_fence_c(2 downto 1)) then
          illegal_cmd <= '0';
        end if;

      -- system instruction / may-be-operations / CSR access --
      when opcode_system_c =>
        if (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_env_c) then -- system environment
          if (exec.ir(instr_rs1_msb_c downto instr_rs1_lsb_c) = "00000") and (exec.ir(instr_rd_msb_c downto instr_rd_lsb_c) = "00000") then
            case exec.ir(instr_imm12_msb_c downto instr_imm12_lsb_c) is
              when funct12_ecall_c  => illegal_cmd <= '0'; -- ecall is always allowed
              when funct12_ebreak_c => illegal_cmd <= '0'; -- ebreak is always allowed
              when funct12_mret_c   => illegal_cmd <= (not csr.prv_level) or debug_ctrl.run; -- mret allowed in (real/non-debug) M-mode only
              when funct12_dret_c   => illegal_cmd <= not debug_ctrl.run; -- dret allowed in debug mode only
              when funct12_wfi_c    => illegal_cmd <= (not csr.prv_level) and csr.mstatus_tw; -- wfi allowed in M-mode or if TW is zero
              when others           => illegal_cmd <= '1'; -- undefined
            end case;
          end if;
        elsif (exec.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_zimop_c) then
          illegal_cmd <= not bool_to_ulogic_f(RISCV_ISA_Zimop);
        elsif (csr_valid = "111") then -- valid CSR operation
          illegal_cmd <= '0';
        end if;

      -- undefined/unimplemented/illegal opcode --
      when others =>
        illegal_cmd <= '1';

    end case;
  end process illegal_check;


  -- Instruction Execution Monitor (trap if multi-cycle instruction does not complete) ------
  -- -------------------------------------------------------------------------------------------
  multi_cycle_monitor: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      monitor_cnt <= (others => '0');
    elsif rising_edge(clk_i) then
      if (exec.state = S_ALU_WAIT) then
        monitor_cnt <= std_ulogic_vector(unsigned(monitor_cnt) + 1);
      else
        monitor_cnt <= (others => '0');
      end if;
    end if;
  end process multi_cycle_monitor;


  -- Illegal Operation Check ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap.instr_il <= '1' when ((exec.state = S_EXECUTE) or (exec.state = S_ALU_WAIT)) and -- check execution states
                            ((monitor_cnt(monitor_cnt'left) = '1') or (illegal_cmd = '1')) else '0'; -- timeout or illegal


  -- ****************************************************************************************************************************
  -- Trap Control
  -- ****************************************************************************************************************************

  -- Trap Buffer ----------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap_buffer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap.irq_pnd <= (others => '0');
      trap.irq_buf <= (others => '0');
      trap.exc_buf <= (others => '0');
    elsif rising_edge(clk_i) then
      -- interrupt pending: synchronize requests --
      trap.irq_pnd <= '0' & irq_fast_i & irq_machine_i;
      -- interrupt buffer: local feedback to ensure requests stay active until trap environment has started --
      trap.irq_buf(irq_db_halt_c) <= debug_ctrl.trig_halt                          or (trap.env_pend and trap.irq_buf(irq_db_halt_c));
      trap.irq_buf(irq_msi_irq_c) <= (trap.irq_pnd(irq_msi_irq_c) and csr.mie_msi) or (trap.env_pend and trap.irq_buf(irq_msi_irq_c));
      trap.irq_buf(irq_mei_irq_c) <= (trap.irq_pnd(irq_mei_irq_c) and csr.mie_mei) or (trap.env_pend and trap.irq_buf(irq_mei_irq_c));
      trap.irq_buf(irq_mti_irq_c) <= (trap.irq_pnd(irq_mti_irq_c) and csr.mie_mti) or (trap.env_pend and trap.irq_buf(irq_mti_irq_c));
      for i in 0 to 15 loop
        trap.irq_buf(irq_firq_0_c+i) <= (trap.irq_pnd(irq_firq_0_c+i) and csr.mie_firq(i)) or (trap.env_pend and trap.irq_buf(irq_firq_0_c+i));
      end loop;
      -- exception buffer: accumulate exception requests; clear all requests at once when trap environment starts --
      trap.exc_buf(exc_iaccess_c)  <= (trap.exc_buf(exc_iaccess_c)  or trap.instr_be)         and (not trap.env_enter);
      trap.exc_buf(exc_illegal_c)  <= (trap.exc_buf(exc_illegal_c)  or trap.instr_il)         and (not trap.env_enter);
      trap.exc_buf(exc_ialign_c)   <= (trap.exc_buf(exc_ialign_c)   or trap.instr_ma)         and (not trap.env_enter);
      trap.exc_buf(exc_ecall_c)    <= (trap.exc_buf(exc_ecall_c)    or trap.ecall)            and (not trap.env_enter);
      trap.exc_buf(exc_ebreak_c)   <= (trap.exc_buf(exc_ebreak_c)   or ebreak_trig)           and (not trap.env_enter);
      trap.exc_buf(exc_salign_c)   <= (trap.exc_buf(exc_salign_c)   or lsu_err_i(2))          and (not trap.env_enter);
      trap.exc_buf(exc_lalign_c)   <= (trap.exc_buf(exc_lalign_c)   or lsu_err_i(0))          and (not trap.env_enter);
      trap.exc_buf(exc_saccess_c)  <= (trap.exc_buf(exc_saccess_c)  or lsu_err_i(3))          and (not trap.env_enter);
      trap.exc_buf(exc_laccess_c)  <= (trap.exc_buf(exc_laccess_c)  or lsu_err_i(1))          and (not trap.env_enter);
      trap.exc_buf(exc_db_break_c) <= (trap.exc_buf(exc_db_break_c) or debug_ctrl.trig_break) and (not trap.env_enter);
      trap.exc_buf(exc_db_trig_c)  <= (trap.exc_buf(exc_db_trig_c)  or debug_ctrl.trig_hw)    and (not trap.env_enter);
      trap.exc_buf(exc_db_step_c)  <= (trap.exc_buf(exc_db_step_c)  or debug_ctrl.trig_step)  and (not trap.env_enter);
    end if;
  end process trap_buffer;

  -- environment break exception trigger --
  ebreak_trig <= (trap.ebreak and (    csr.prv_level) and (not csr.dcsr_ebreakm) and (not debug_ctrl.run)) or -- M-mode trap on M-ebreak
                 (trap.ebreak and (not csr.prv_level) and (not csr.dcsr_ebreaku) and (not debug_ctrl.run));   -- M-mode trap on U-ebreak


  -- Trap Priority Encoder ------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap.cause <=
    -- standard RISC-V synchronous exceptions --
    trap_iaf_c      when (trap.exc_buf(exc_iaccess_c)  = '1') else -- instruction access fault
    trap_iil_c      when (trap.exc_buf(exc_illegal_c)  = '1') else -- illegal instruction
    trap_ima_c      when (trap.exc_buf(exc_ialign_c)   = '1') else -- instruction address misaligned
    trap_env        when (trap.exc_buf(exc_ecall_c)    = '1') else -- environment call from U/M-mode
    trap_brk_c      when (trap.exc_buf(exc_ebreak_c)   = '1') else -- environment breakpoint
    trap_sma_c      when (trap.exc_buf(exc_salign_c)   = '1') else -- store address misaligned
    trap_lma_c      when (trap.exc_buf(exc_lalign_c)   = '1') else -- load address misaligned
    trap_saf_c      when (trap.exc_buf(exc_saccess_c)  = '1') else -- store access fault
    trap_laf_c      when (trap.exc_buf(exc_laccess_c)  = '1') else -- load access fault
    -- standard RISC-V debug mode synchronous exceptions and interrupts --
    trap_db_halt_c  when (trap.irq_buf(irq_db_halt_c)  = '1') else -- external halt request
    trap_db_trig_c  when (trap.exc_buf(exc_db_trig_c)  = '1') else -- hardware trigger
    trap_db_break_c when (trap.exc_buf(exc_db_break_c) = '1') else -- breakpoint
    trap_db_step_c  when (trap.exc_buf(exc_db_step_c)  = '1') else -- single stepping
    -- NEORV32-specific fast interrupts --
    trap_firq0_c    when (trap.irq_buf(irq_firq_0_c)   = '1') else -- fast interrupt channel 0
    trap_firq1_c    when (trap.irq_buf(irq_firq_1_c)   = '1') else -- fast interrupt channel 1
    trap_firq2_c    when (trap.irq_buf(irq_firq_2_c)   = '1') else -- fast interrupt channel 2
    trap_firq3_c    when (trap.irq_buf(irq_firq_3_c)   = '1') else -- fast interrupt channel 3
    trap_firq4_c    when (trap.irq_buf(irq_firq_4_c)   = '1') else -- fast interrupt channel 4
    trap_firq5_c    when (trap.irq_buf(irq_firq_5_c)   = '1') else -- fast interrupt channel 5
    trap_firq6_c    when (trap.irq_buf(irq_firq_6_c)   = '1') else -- fast interrupt channel 6
    trap_firq7_c    when (trap.irq_buf(irq_firq_7_c)   = '1') else -- fast interrupt channel 7
    trap_firq8_c    when (trap.irq_buf(irq_firq_8_c)   = '1') else -- fast interrupt channel 8
    trap_firq9_c    when (trap.irq_buf(irq_firq_9_c)   = '1') else -- fast interrupt channel 9
    trap_firq10_c   when (trap.irq_buf(irq_firq_10_c)  = '1') else -- fast interrupt channel 10
    trap_firq11_c   when (trap.irq_buf(irq_firq_11_c)  = '1') else -- fast interrupt channel 11
    trap_firq12_c   when (trap.irq_buf(irq_firq_12_c)  = '1') else -- fast interrupt channel 12
    trap_firq13_c   when (trap.irq_buf(irq_firq_13_c)  = '1') else -- fast interrupt channel 13
    trap_firq14_c   when (trap.irq_buf(irq_firq_14_c)  = '1') else -- fast interrupt channel 14
    trap_firq15_c   when (trap.irq_buf(irq_firq_15_c)  = '1') else -- fast interrupt channel 15
    -- standard RISC-V interrupts --
    trap_mei_c      when (trap.irq_buf(irq_mei_irq_c)  = '1') else -- machine external interrupt (MEI)
    trap_msi_c      when (trap.irq_buf(irq_msi_irq_c)  = '1') else -- machine software interrupt (MSI)
    trap_mti_c;   --when (trap.irq_buf(irq_mti_irq_c)  = '1') else -- machine timer interrupt (MTI)

  -- environment call helper --
  trap_env <= trap_env_c(6 downto 2) & csr.prv_level & csr.prv_level;

  -- exception program counter: async. interrupt or sync. exception? --
  trap.pc <= exec.pc2 when (trap.cause(trap.cause'left) = '1') else exec.pc;


  -- Trap Triggers --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap_pending: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap.env_pend <= '0';
    elsif rising_edge(clk_i) then
      if (trap.env_enter = '1') then -- start of trap environment acknowledged by execute engine
        trap.env_pend <= '0';
      elsif (trap.exc_fire = '1') or (or_reduce_f(trap.irq_fire) = '1') then -- trap trigger
        trap.env_pend <= '1';
      end if;
    end if;
  end process trap_pending;

  -- any sync. exception? --
  trap.exc_fire <= or_reduce_f(trap.exc_buf); -- cannot be masked

  -- any system interrupt? --
  trap.irq_fire(0) <= '1' when
    ((exec.state = S_EXECUTE) or (exec.state = S_SLEEP)) and -- trigger system IRQ only in S_EXECUTE state or in sleep mode
    (or_reduce_f(trap.irq_buf(irq_firq_15_c downto irq_msi_irq_c)) = '1') and -- pending system IRQ
    ((csr.mstatus_mie = '1') or (csr.prv_level = priv_mode_u_c)) and -- IRQ only when in M-mode and MIE=1 OR when in U-mode
    (debug_ctrl.run = '0') and (csr.dcsr_step = '0') else '0'; -- no system IRQs when in debug-mode / during single-stepping

  -- debug-entry halt interrupt? allow halt also after "reset" (#879) --
  trap.irq_fire(1) <= trap.irq_buf(irq_db_halt_c) when (exec.state = S_RESTART) or (exec.state = S_EXECUTE) or (exec.state = S_SLEEP) else '0';


  -- ****************************************************************************************************************************
  -- CPU Debug Mode
  -- ****************************************************************************************************************************

  -- Debug Control --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  debug_mode_enable:
  if RISCV_ISA_Sdext generate

    -- debug mode active? --
    debug_control: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        debug_ctrl.run <= '0';
      elsif rising_edge(clk_i) then
        if (debug_ctrl.run = '0') and (trap.env_enter = '1') and (trap.cause(5) = '1') then -- entry event
          debug_ctrl.run <= '1';
        elsif (trap.env_exit = '1') then -- exit event
          debug_ctrl.run <= '0';
        end if;
      end if;
    end process debug_control;

    -- debug mode entry triggers --
    debug_ctrl.trig_halt  <= irq_dbg_i and (not debug_ctrl.run); -- external halt request (if not halted already)
    debug_ctrl.trig_step  <= (csr.dcsr_step and (not debug_ctrl.run)) when (exec.state = S_EXECUTE) else '0'; -- single-step mode
    debug_ctrl.trig_hw    <= hwtrig_i and (not debug_ctrl.run); -- enter debug-mode by HW trigger module
    debug_ctrl.trig_break <= trap.ebreak and (debug_ctrl.run or ((    csr.prv_level) and csr.dcsr_ebreakm) or -- debug on M-ebreak
                                                                ((not csr.prv_level) and csr.dcsr_ebreaku));  -- debug on U-ebreak

  end generate;

  -- Sdext ISA extension not enabled --
  debug_mode_disable:
  if not RISCV_ISA_Sdext generate
    debug_ctrl.run        <= '0';
    debug_ctrl.trig_halt  <= '0';
    debug_ctrl.trig_step  <= '0';
    debug_ctrl.trig_hw    <= '0';
    debug_ctrl.trig_break <= '0';
  end generate;


  -- Debug Control and Status Register (dcsr) - Read-Back -----------------------------------
  -- -------------------------------------------------------------------------------------------
  dcsr_rdata(31 downto 28) <= "0100"; -- xdebugver: external debug support compatible to spec. version 1.0
  dcsr_rdata(27 downto 16) <= (others => '0'); -- reserved
  dcsr_rdata(15)           <= csr.dcsr_ebreakm; -- ebreakm: what happens on ebreak in m-mode? (normal trap OR debug-enter)
  dcsr_rdata(14)           <= '0'; -- reserved
  dcsr_rdata(13)           <= '0'; -- ebreaks: supervisor mode not implemented
  dcsr_rdata(12)           <= csr.dcsr_ebreaku when RISCV_ISA_U else '0'; -- ebreaku: what happens on ebreak in u-mode? (normal trap OR debug-enter)
  dcsr_rdata(11)           <= '0'; -- stepie: interrupts are disabled during single-stepping
  dcsr_rdata(10)           <= '1'; -- stopcount: standard counters and HPMs are stopped when in debug mode
  dcsr_rdata(9)            <= '0'; -- stoptime: timers increment as usual
  dcsr_rdata(8 downto 6)   <= csr.dcsr_cause; -- debug mode entry cause
  dcsr_rdata(5)            <= '0'; -- reserved
  dcsr_rdata(4)            <= '1'; -- mprven: mstatus.mprv is also evaluated in debug mode
  dcsr_rdata(3)            <= '0'; -- nmip: no pending non-maskable interrupt
  dcsr_rdata(2)            <= csr.dcsr_step; -- step: single-step mode
  dcsr_rdata(1 downto 0)   <= (others => csr.dcsr_prv); -- prv: privilege level when debug mode was entered


  -- ****************************************************************************************************************************
  -- Control and Status Registers (CSRs)
  -- ****************************************************************************************************************************

  -- CSR Write-Data ALU ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_alu: process(exec.ir, rf_rs1_i, csr_rdata)
    variable opb_v : std_ulogic_vector(31 downto 0);
  begin
    if (exec.ir(instr_funct3_msb_c) = '0') then
      opb_v := rf_rs1_i;
    else
      opb_v := replicate_f('0', 32-5) & exec.ir(19 downto 15);
    end if;
    case exec.ir(instr_funct3_msb_c-1 downto instr_funct3_lsb_c) is
      when "10"   => csr_wdata <= csr_rdata or opb_v; -- set
      when "11"   => csr_wdata <= csr_rdata and (not opb_v); -- clear
      when others => csr_wdata <= opb_v; -- write
    end case;
  end process csr_alu;


  -- CSR Write Access -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.prv_level     <= priv_mode_m_c;
      csr.mstatus_mie   <= '0';
      csr.mstatus_mpie  <= '0';
      csr.mstatus_mpp   <= '0';
      csr.mstatus_mprv  <= '0';
      csr.mstatus_tw    <= '0';
      csr.mie_msi       <= '0';
      csr.mie_mei       <= '0';
      csr.mie_mti       <= '0';
      csr.mie_firq      <= (others => '0');
      csr.mtvec         <= (others => '0');
      csr.mscratch      <= (others => '0');
      csr.mepc          <= (others => '0');
      csr.mcause        <= (others => '0');
      csr.mtval         <= (others => '0');
      csr.mtinst        <= (others => '0');
      csr.mcounteren    <= (others => '0');
      csr.dcsr_ebreakm  <= '0';
      csr.dcsr_ebreaku  <= '0';
      csr.dcsr_step     <= '0';
      csr.dcsr_prv      <= '0';
      csr.dcsr_cause    <= (others => '0');
      csr.dpc           <= (others => '0');
      csr.dscratch0     <= (others => '0');
    elsif rising_edge(clk_i) then

      -- ********************************************************************************
      -- Software CSR access
      -- ********************************************************************************
      if (ctrl.csr_we = '1') then
        case ctrl.csr_addr is

          when csr_mstatus_c => -- machine status register
            csr.mstatus_mie  <= csr_wdata(3);
            csr.mstatus_mpie <= csr_wdata(7);
            csr.mstatus_mpp  <= or_reduce_f(csr_wdata(12 downto 11)); -- everything != U will fall back to M
            csr.mstatus_mprv <= csr_wdata(17);
            csr.mstatus_tw   <= csr_wdata(21);

          when csr_mie_c => -- machine interrupt enable register
            csr.mie_msi  <= csr_wdata(3);
            csr.mie_mti  <= csr_wdata(7);
            csr.mie_mei  <= csr_wdata(11);
            csr.mie_firq <= csr_wdata(31 downto 16);

          when csr_mtvec_c => -- machine trap-handler base address
            csr.mtvec <= csr_wdata(31 downto 2) & '0' & csr_wdata(0); -- base + mode (vectored/direct)

          when csr_mcounteren_c => -- machine counter access enable
            csr.mcounteren <= csr_wdata(2 downto 0);

          when csr_mscratch_c => -- machine scratch register
            csr.mscratch <= csr_wdata;

          when csr_mepc_c => -- machine exception program counter
            csr.mepc <= csr_wdata(31 downto 1) & '0';

          when csr_dcsr_c => -- debug mode control and status register
            csr.dcsr_step    <= csr_wdata(2);
            csr.dcsr_ebreakm <= csr_wdata(15);
            csr.dcsr_prv     <= or_reduce_f(csr_wdata(1 downto 0)); -- everything != U will fall back to M
            csr.dcsr_ebreaku <= csr_wdata(12);

          when csr_dpc_c => -- debug mode program counter
            csr.dpc <= csr_wdata(31 downto 1) & '0';

          when csr_dscratch0_c => -- debug mode scratch register 0
            csr.dscratch0 <= csr_wdata;

          when others => -- undefined or implemented somewhere else
            NULL;

        end case;

      -- ********************************************************************************
      -- Hardware CSR access: trap enter
      -- ********************************************************************************
      elsif (trap.env_enter = '1') then
        if (debug_ctrl.run = '0') then -- no CSE update when in debug-mode
          if RISCV_ISA_Sdext and (trap.cause(5) = '1') then -- trap to debug-mode
            csr.prv_level  <= priv_mode_m_c;
            csr.dcsr_cause <= trap.cause(2 downto 0);
            csr.dcsr_prv   <= csr.prv_level;
            csr.dpc        <= trap.pc(31 downto 1) & '0';
          else -- trap to machine-mode
            csr.prv_level    <= priv_mode_m_c;
            csr.mstatus_mpp  <= csr.prv_level;
            csr.mstatus_mie  <= '0';
            csr.mstatus_mpie <= csr.mstatus_mie;
            csr.mcause       <= trap.cause(6) & trap.cause(4 downto 0);
            csr.mepc         <= trap.pc(31 downto 1) & '0';
            if (trap.cause(6) = '0') and (trap.cause(2) = '1') then -- load/store misaligned/access fault
              csr.mtval <= lsu_mar_i; -- faulting data access address
            else -- everything else including all interrupts
              csr.mtval <= (others => '0');
            end if;
            csr.mtinst <= exec.ir; -- transformed trapping instruction
            if (exec.ci = '1') and RISCV_ISA_C then
              csr.mtinst(1) <= '0'; -- RISC-V priv. spec: clear bit 1 if compressed instruction
            end if;
          end if;
        end if;

      -- ********************************************************************************
      -- Hardware CSR access: trap exit
      -- ********************************************************************************
      elsif (trap.env_exit = '1') then
        if RISCV_ISA_Sdext and (debug_ctrl.run = '1') then -- return from debug-mode
          csr.prv_level <= csr.dcsr_prv;
          if (csr.dcsr_prv /= priv_mode_m_c) then
            csr.mstatus_mprv <= '0'; -- clear if return to priv. level less than M
          end if;
        else -- return from machine-mode trap
          csr.prv_level <= csr.mstatus_mpp;
          if (csr.mstatus_mpp /= priv_mode_m_c) then
            csr.mstatus_mprv <= '0'; -- clear if return to priv. level less than M
          end if;
          csr.mstatus_mpp  <= priv_mode_u_c; -- set to least-privileged level that is supported
          csr.mstatus_mie  <= csr.mstatus_mpie;
          csr.mstatus_mpie <= '1';
        end if;

      end if;

      -- ********************************************************************************
      -- Override: terminate unavailable registers and bits
      -- ********************************************************************************
      -- undefined --
      csr.mcounteren(1) <= '0';
      -- no base counters --
      if not RISCV_ISA_Zicntr then
        csr.mcounteren <= (others => '0');
      end if;
      -- no user mode --
      if not RISCV_ISA_U then
        csr.prv_level    <= priv_mode_m_c;
        csr.mstatus_mpp  <= priv_mode_m_c;
        csr.mstatus_mprv <= '0';
        csr.mstatus_tw   <= '0';
        csr.dcsr_ebreaku <= '0';
        csr.dcsr_prv     <= '0';
        csr.mcounteren   <= (others => '0');
      end if;
      -- no debug mode --
      if not RISCV_ISA_Sdext then
        csr.dcsr_ebreakm <= '0';
        csr.dcsr_step    <= '0';
        csr.dcsr_ebreaku <= '0';
        csr.dcsr_prv     <= priv_mode_m_c;
        csr.dcsr_cause   <= (others => '0');
        csr.dpc          <= (others => '0');
        csr.dscratch0    <= (others => '0');
      end if;
      -- no compressed instructions --
      if not RISCV_ISA_C then
        csr.mepc(1) <= '0'; -- xPC[1] is masked when IALIGN == 32
        csr.dpc(1)  <= '0';
      end if;

    end if;
  end process csr_write_access;


  -- CSR Read Access ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_read_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr_rdata <= (others => '0');
    elsif rising_edge(clk_i) then
      csr_rdata <= (others => '0'); -- output all-zero if there is no CSR read operation
      if (ctrl.csr_re = '1') then
        case ctrl.csr_addr is

          -- --------------------------------------------------------------------
          -- machine trap setup
          -- --------------------------------------------------------------------
          when csr_mstatus_c => -- machine status register, low word
            csr_rdata(3)  <= csr.mstatus_mie;
            csr_rdata(7)  <= csr.mstatus_mpie;
            csr_rdata(11) <= csr.mstatus_mpp;
            csr_rdata(12) <= csr.mstatus_mpp;
            csr_rdata(17) <= csr.mstatus_mprv;
            csr_rdata(21) <= csr.mstatus_tw and bool_to_ulogic_f(RISCV_ISA_U);

          when csr_misa_c => -- ISA and extensions
            csr_rdata(0)  <= bool_to_ulogic_f(RISCV_ISA_A);
            csr_rdata(1)  <= bool_to_ulogic_f(RISCV_ISA_B);
            csr_rdata(2)  <= bool_to_ulogic_f(RISCV_ISA_C);
            csr_rdata(4)  <= bool_to_ulogic_f(RISCV_ISA_E);
            csr_rdata(8)  <= bool_to_ulogic_f(not RISCV_ISA_E);
            csr_rdata(12) <= bool_to_ulogic_f(RISCV_ISA_M);
            csr_rdata(20) <= bool_to_ulogic_f(RISCV_ISA_U);
            csr_rdata(23) <= '1'; -- X CPU extension (non-standard / NEORV32-specific)
            csr_rdata(31 downto 30) <= "01"; -- MXL = 32

          when csr_mie_c => -- machine interrupt-enable register
            csr_rdata(3)  <= csr.mie_msi;
            csr_rdata(7)  <= csr.mie_mti;
            csr_rdata(11) <= csr.mie_mei;
            csr_rdata(31 downto 16) <= csr.mie_firq;

          when csr_mtvec_c => -- machine trap-handler base address
            csr_rdata <= csr.mtvec;

          when csr_mcounteren_c => -- machine counter enable register
            if RISCV_ISA_U and RISCV_ISA_Zicntr then
              csr_rdata(2 downto 0) <= csr.mcounteren;
            end if;

          -- --------------------------------------------------------------------
          -- machine trap handling
          -- --------------------------------------------------------------------
          when csr_mscratch_c => -- machine scratch register
            csr_rdata <= csr.mscratch;

          when csr_mepc_c => -- machine exception program counter
            csr_rdata <= csr.mepc(31 downto 1) & '0';

          when csr_mcause_c => -- machine trap cause
            csr_rdata(31) <= csr.mcause(5);
            csr_rdata(4 downto 0) <= csr.mcause(4 downto 0);

          when csr_mtval_c => -- machine trap value
            csr_rdata <= csr.mtval;

          when csr_mip_c => -- machine interrupt pending
            csr_rdata(3)  <= trap.irq_pnd(irq_msi_irq_c);
            csr_rdata(7)  <= trap.irq_pnd(irq_mti_irq_c);
            csr_rdata(11) <= trap.irq_pnd(irq_mei_irq_c);
            csr_rdata(31 downto 16) <= trap.irq_pnd(irq_firq_15_c downto irq_firq_0_c);

          when csr_mtinst_c => -- machine trap instruction
            csr_rdata <= csr.mtinst;

          -- --------------------------------------------------------------------
          -- machine information
          -- --------------------------------------------------------------------
          when csr_mvendorid_c => csr_rdata <= VENDOR_ID; -- vendor ID
          when csr_marchid_c   => csr_rdata(4 downto 0) <= "10011"; -- architecture ID
          when csr_mimpid_c    => csr_rdata <= hw_version_c; -- implementation ID
          when csr_mhartid_c   => csr_rdata(9 downto 0) <= std_ulogic_vector(to_unsigned(HART_ID, 10)); -- hardware thread ID

          -- --------------------------------------------------------------------
          -- debug-mode
          -- --------------------------------------------------------------------
          when csr_dcsr_c      => if RISCV_ISA_Sdext then csr_rdata <= dcsr_rdata;    end if; -- control and status
          when csr_dpc_c       => if RISCV_ISA_Sdext then csr_rdata <= csr.dpc;       end if; -- program counter
          when csr_dscratch0_c => if RISCV_ISA_Sdext then csr_rdata <= csr.dscratch0; end if; -- scratch register 0

          -- --------------------------------------------------------------------
          -- NEORV32-specific
          -- --------------------------------------------------------------------
          when csr_mxisa_c => -- machine extended ISA extensions information
            csr_rdata(0)  <= '1';                                -- Zicsr: CSR access (always enabled)
            csr_rdata(1)  <= '1';                                -- Zifencei: instruction stream sync. (always enabled)
            csr_rdata(2)  <= bool_to_ulogic_f(RISCV_ISA_Zmmul);  -- Zmmul: mul/div
            csr_rdata(3)  <= bool_to_ulogic_f(RISCV_ISA_Zxcfu);  -- Zxcfu: custom instructions
            csr_rdata(4)  <= bool_to_ulogic_f(RISCV_ISA_Zkt);    -- Zkt: data independent execution latency
            csr_rdata(5)  <= bool_to_ulogic_f(RISCV_ISA_Zfinx);  -- Zfinx: FPU using x registers
            csr_rdata(6)  <= bool_to_ulogic_f(RISCV_ISA_Zicond); -- Zicond: integer conditional operations
            csr_rdata(7)  <= bool_to_ulogic_f(RISCV_ISA_Zicntr); -- Zicntr: base counters
            csr_rdata(8)  <= bool_to_ulogic_f(RISCV_ISA_Smpmp);  -- Smpmp: physical memory protection
            csr_rdata(9)  <= bool_to_ulogic_f(RISCV_ISA_Zihpm);  -- Zihpm: hardware performance monitors
            csr_rdata(10) <= bool_to_ulogic_f(RISCV_ISA_Sdext);  -- Sdext: external debug
            csr_rdata(11) <= bool_to_ulogic_f(RISCV_ISA_Sdtrig); -- Sdtrig: trigger module
            csr_rdata(12) <= bool_to_ulogic_f(RISCV_ISA_Zbkx);   -- Zbkx: cryptography crossbar permutation
            csr_rdata(13) <= bool_to_ulogic_f(RISCV_ISA_Zknd);   -- Zknd: cryptography NIST AES decryption
            csr_rdata(14) <= bool_to_ulogic_f(RISCV_ISA_Zkne);   -- Zkne: cryptography NIST AES encryption
            csr_rdata(15) <= bool_to_ulogic_f(RISCV_ISA_Zknh);   -- Zknh: cryptography NIST hash functions
            csr_rdata(16) <= bool_to_ulogic_f(RISCV_ISA_Zbkb);   -- Zbkb: bit manipulation instructions for cryptography
            csr_rdata(17) <= bool_to_ulogic_f(RISCV_ISA_Zbkc);   -- Zbkc: carry-less multiplication for cryptography
            csr_rdata(18) <= bool_to_ulogic_f(RISCV_ISA_Zkn);    -- Zkn: NIST algorithm suite
            csr_rdata(19) <= bool_to_ulogic_f(RISCV_ISA_Zksh);   -- Zksh: ShangMi hash functions
            csr_rdata(20) <= bool_to_ulogic_f(RISCV_ISA_Zksed);  -- Zksed: ShangMi block ciphers
            csr_rdata(21) <= bool_to_ulogic_f(RISCV_ISA_Zks);    -- Zks: ShangMi algorithm suite
            csr_rdata(22) <= bool_to_ulogic_f(RISCV_ISA_Zba);    -- Zba: shifted-add bit-manipulation
            csr_rdata(23) <= bool_to_ulogic_f(RISCV_ISA_Zbb);    -- Zbb: basic bit-manipulation
            csr_rdata(24) <= bool_to_ulogic_f(RISCV_ISA_Zbs);    -- Zbs: single-bit bit-manipulation
            csr_rdata(25) <= bool_to_ulogic_f(RISCV_ISA_Zaamo);  -- Zaamo: atomic memory operations
            csr_rdata(26) <= bool_to_ulogic_f(RISCV_ISA_Zalrsc); -- Zalrsc: reservation-set operations
            csr_rdata(27) <= bool_to_ulogic_f(RISCV_ISA_Zcb);    -- Zcb: additional code size reduction instructions
            csr_rdata(28) <= bool_to_ulogic_f(RISCV_ISA_C);      -- Zca: C without floating-point
            csr_rdata(29) <= bool_to_ulogic_f(RISCV_ISA_Zibi);   -- Zibi: branch with immediate-comparison
            csr_rdata(30) <= bool_to_ulogic_f(RISCV_ISA_Zimop);  -- Zimop: may-be-operations
            csr_rdata(31) <= '0';                                -- reserved

          -- --------------------------------------------------------------------
          -- undefined/unavailable or implemented externally
          -- --------------------------------------------------------------------
          when others => -- FPU, PMP, HPM, base counters, trigger module, etc.
            csr_rdata <= xcsr_rdata_i;

        end case;
      end if;
    end if;
  end process csr_read_access;

  -- CSR read data output (to register file mux) --
  csr_rdata_o <= csr_rdata;

end neorv32_cpu_control_rtl;
