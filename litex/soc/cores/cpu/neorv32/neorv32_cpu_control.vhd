-- ================================================================================ --
-- NEORV32 CPU - Central Control Unit                                               --
-- -------------------------------------------------------------------------------- --
-- + Execute engine:  Multi-cycle execution of instructions ("back-end")            --
-- + Trap controller: Handles interrupts and exceptions                             --
-- + CSR module:      Read/write access to control and status registers             --
-- + Debug module:    CPU debug mode handling (on-chip debugger)                    --
-- + Trigger module:  Hardware-assisted breakpoints (on-chip debugger)              --
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
    HART_ID             : natural range 0 to 1023; -- hardware thread ID
    BOOT_ADDR           : std_ulogic_vector(31 downto 0); -- cpu boot address
    DEBUG_PARK_ADDR     : std_ulogic_vector(31 downto 0); -- cpu debug-mode parking loop entry address, 4-byte aligned
    DEBUG_EXC_ADDR      : std_ulogic_vector(31 downto 0); -- cpu debug-mode exception entry address, 4-byte aligned
    -- RISC-V ISA Extensions --
    RISCV_ISA_A         : boolean; -- implement atomic memory operations extension
    RISCV_ISA_B         : boolean; -- implement bit-manipulation extension
    RISCV_ISA_C         : boolean; -- implement compressed extension
    RISCV_ISA_E         : boolean; -- implement embedded-class register file extension
    RISCV_ISA_M         : boolean; -- implement mul/div extension
    RISCV_ISA_U         : boolean; -- implement user mode extension
    RISCV_ISA_Zaamo     : boolean; -- implement atomic read-modify-write extension
    RISCV_ISA_Zalrsc    : boolean; -- implement atomic reservation-set operations extension
    RISCV_ISA_Zba       : boolean; -- implement shifted-add bit-manipulation extension
    RISCV_ISA_Zbb       : boolean; -- implement basic bit-manipulation extension
    RISCV_ISA_Zbkb      : boolean; -- implement bit-manipulation instructions for cryptography
    RISCV_ISA_Zbkc      : boolean; -- implement carry-less multiplication instructions
    RISCV_ISA_Zbkx      : boolean; -- implement cryptography crossbar permutation extension
    RISCV_ISA_Zbs       : boolean; -- implement single-bit bit-manipulation extension
    RISCV_ISA_Zfinx     : boolean; -- implement 32-bit floating-point extension
    RISCV_ISA_Zicntr    : boolean; -- implement base counters
    RISCV_ISA_Zicond    : boolean; -- implement integer conditional operations
    RISCV_ISA_Zihpm     : boolean; -- implement hardware performance monitors
    RISCV_ISA_Zkn       : boolean; -- NIST algorithm suite available
    RISCV_ISA_Zknd      : boolean; -- implement cryptography NIST AES decryption extension
    RISCV_ISA_Zkne      : boolean; -- implement cryptography NIST AES encryption extension
    RISCV_ISA_Zknh      : boolean; -- implement cryptography NIST hash extension
    RISCV_ISA_Zks       : boolean; -- ShangMi algorithm suite available
    RISCV_ISA_Zksed     : boolean; -- implement ShangMi block cipher extension
    RISCV_ISA_Zksh      : boolean; -- implement ShangMi hash extension
    RISCV_ISA_Zkt       : boolean; -- data-independent execution time available (for cryptography operations)
    RISCV_ISA_Zmmul     : boolean; -- implement multiply-only M sub-extension
    RISCV_ISA_Zxcfu     : boolean; -- implement custom (instr.) functions unit
    RISCV_ISA_Sdext     : boolean; -- implement external debug mode extension
    RISCV_ISA_Sdtrig    : boolean; -- implement trigger module extension
    RISCV_ISA_Smpmp     : boolean; -- implement physical memory protection
    -- Tuning Options --
    CPU_CLOCK_GATING_EN : boolean; -- enable clock gating when in sleep mode
    CPU_FAST_MUL_EN     : boolean; -- use DSPs for M extension's multiplier
    CPU_FAST_SHIFT_EN   : boolean; -- use barrel shifter for shift operations
    CPU_RF_HW_RST_EN    : boolean  -- implement full hardware reset for register file
  );
  port (
    -- global control --
    clk_i         : in  std_ulogic; -- global clock, rising edge
    clk_aux_i     : in  std_ulogic; -- always-on clock, rising edge
    rstn_i        : in  std_ulogic; -- global reset, low-active, async
    ctrl_o        : out ctrl_bus_t; -- main control bus
    -- instruction fetch (front-end) interface --
    frontend_i    : in  if_bus_t;   -- front-end status and data
    -- pmp fault --
    pmp_fault_i   : in  std_ulogic; -- instruction fetch / execute pmp fault
    -- data path interface --
    alu_cp_done_i : in  std_ulogic; -- ALU iterative operation done
    alu_cmp_i     : in  std_ulogic_vector(1 downto 0); -- comparator status
    alu_add_i     : in  std_ulogic_vector(XLEN-1 downto 0); -- ALU address result
    rf_rs1_i      : in  std_ulogic_vector(XLEN-1 downto 0); -- rf source 1
    csr_rdata_o   : out std_ulogic_vector(XLEN-1 downto 0); -- CSR read data
    xcsr_rdata_i  : in  std_ulogic_vector(XLEN-1 downto 0); -- external CSR read data
    -- interrupts --
    irq_dbg_i     : in  std_ulogic; -- debug mode (halt) request
    irq_machine_i : in  std_ulogic_vector(2 downto 0); -- risc-v mti, mei, msi
    irq_fast_i    : in  std_ulogic_vector(15 downto 0); -- fast interrupts
    -- load/store unit interface --
    lsu_wait_i    : in  std_ulogic; -- wait for data bus
    lsu_mar_i     : in  std_ulogic_vector(XLEN-1 downto 0); -- memory address register
    lsu_err_i     : in  std_ulogic_vector(3 downto 0); -- alignment/access errors
    -- memory synchronization --
    mem_sync_i    : in  std_ulogic -- synchronization operation done
  );
end neorv32_cpu_control;

architecture neorv32_cpu_control_rtl of neorv32_cpu_control is

  -- instruction execution engine --
  type exe_engine_state_t is (EX_DISPATCH, EX_TRAP_ENTER, EX_TRAP_EXIT, EX_RESTART, EX_SLEEP, EX_EXECUTE,
                              EX_ALU_WAIT, EX_FENCE, EX_BRANCH, EX_BRANCHED, EX_SYSTEM, EX_MEM_REQ, EX_MEM_RSP);
  type exe_engine_t is record
    state : exe_engine_state_t;
    ir    : std_ulogic_vector(31 downto 0); -- instruction word being executed right now
    ci    : std_ulogic; -- current instruction is de-compressed instruction
    pc    : std_ulogic_vector(XLEN-1 downto 0); -- current PC (current instruction)
    pc2   : std_ulogic_vector(XLEN-1 downto 0); -- next PC (next linear instruction)
    ra    : std_ulogic_vector(XLEN-1 downto 0); -- return address
    msync : std_ulogic; -- memory synchronization completed
  end record;
  signal exe_engine, exe_engine_nxt : exe_engine_t;

  -- trap controller --
  type trap_ctrl_t is record
    exc_buf     : std_ulogic_vector(exc_width_c-1 downto 0); -- synchronous exception buffer (one bit per exception)
    exc_fire    : std_ulogic; -- set if there is a valid source in the exception buffer
    irq_pnd     : std_ulogic_vector(irq_width_c-1 downto 0); -- pending interrupt
    irq_buf     : std_ulogic_vector(irq_width_c-1 downto 0); -- asynchronous exception/interrupt buffer (one bit per interrupt source)
    irq_fire    : std_ulogic_vector(2 downto 0); -- set if an interrupt is actually kicking in
    cause       : std_ulogic_vector(6 downto 0); -- trap ID for mcause CSR & debug-mode entry identifier
    epc         : std_ulogic_vector(XLEN-1 downto 0); -- exception program counter
    --
    env_pending : std_ulogic; -- start of trap environment if pending
    env_enter   : std_ulogic; -- enter trap environment
    env_entered : std_ulogic; -- trap environment has just been entered
    env_exit    : std_ulogic; -- leave trap environment
    wakeup      : std_ulogic; -- wakeup from sleep due to an enabled pending IRQ
    --
    instr_be    : std_ulogic; -- instruction fetch bus error
    instr_ma    : std_ulogic; -- instruction fetch misaligned address
    instr_il    : std_ulogic; -- illegal instruction
    ecall       : std_ulogic; -- ecall instruction
    ebreak      : std_ulogic; -- ebreak instruction
    hwtrig      : std_ulogic; -- hardware trigger module
  end record;
  signal trap_ctrl : trap_ctrl_t;

  -- CPU control bus --
  signal ctrl, ctrl_nxt : ctrl_bus_t;

  -- control and status registers (CSRs) --
  type csr_t is record
    addr           : std_ulogic_vector(11 downto 0); -- physical access address
    we, we_nxt     : std_ulogic; -- write enable
    re, re_nxt     : std_ulogic; -- read enable
    operand        : std_ulogic_vector(XLEN-1 downto 0); -- write operand
    wdata          : std_ulogic_vector(XLEN-1 downto 0); -- write data
    rdata          : std_ulogic_vector(XLEN-1 downto 0); -- read data
    --
    mstatus_mie    : std_ulogic; -- machine-mode IRQ enable
    mstatus_mpie   : std_ulogic; -- previous machine-mode IRQ enable
    mstatus_mpp    : std_ulogic; -- machine previous privilege mode
    mstatus_mprv   : std_ulogic; -- effective privilege level for load/stores
    mstatus_tw     : std_ulogic; -- do not allow user mode to execute WFI instruction when set
    --
    mie_msi        : std_ulogic; -- machine software interrupt enable
    mie_mei        : std_ulogic; -- machine external interrupt enable
    mie_mti        : std_ulogic; -- machine timer interrupt enable
    mie_firq       : std_ulogic_vector(15 downto 0); -- fast interrupt enable
    --
    prv_level      : std_ulogic; -- current privilege level
    prv_level_eff  : std_ulogic; -- current *effective* privilege level
    --
    mepc           : std_ulogic_vector(XLEN-1 downto 0); -- machine exception PC
    mcause         : std_ulogic_vector(5 downto 0); -- machine trap cause
    mtvec          : std_ulogic_vector(XLEN-1 downto 0); -- machine trap-handler base address
    mtval          : std_ulogic_vector(XLEN-1 downto 0); -- machine bad address or instruction
    mtinst         : std_ulogic_vector(XLEN-1 downto 0); -- machine trap instruction
    mscratch       : std_ulogic_vector(XLEN-1 downto 0); -- machine scratch register
    mcounteren_cy  : std_ulogic; -- machine counter access enable: cycle counter
    mcounteren_ir  : std_ulogic; -- machine counter access enable: instruction counter
    mcountinhibit  : std_ulogic_vector(15 downto 0); -- inhibit counter increment
    --
    dcsr_ebreakm   : std_ulogic; -- behavior of ebreak instruction in m-mode
    dcsr_ebreaku   : std_ulogic; -- behavior of ebreak instruction in u-mode
    dcsr_step      : std_ulogic; -- single-step mode
    dcsr_prv       : std_ulogic; -- current privilege level when entering debug mode
    dcsr_cause     : std_ulogic_vector(2 downto 0); -- why was debug mode entered
    dcsr_rd        : std_ulogic_vector(XLEN-1 downto 0); -- debug mode control and status register
    dpc            : std_ulogic_vector(XLEN-1 downto 0); -- mode program counter
    dscratch0      : std_ulogic_vector(XLEN-1 downto 0); -- debug mode scratch register 0
    --
    tdata1_execute : std_ulogic; -- enable instruction address match trigger
    tdata1_action  : std_ulogic; -- enter debug mode / ebreak exception when trigger fires
    tdata1_dmode   : std_ulogic; -- set to ignore tdata* CSR access from machine-mode
    tdata1_rd      : std_ulogic_vector(XLEN-1 downto 0); -- trigger register read-back
    tdata2         : std_ulogic_vector(XLEN-1 downto 0); -- address-match register
  end record;
  signal csr : csr_t;

  -- debug-mode controller --
  type debug_ctrl_t is record
    run, trig_hw, trig_break, trig_halt, trig_step : std_ulogic;
  end record;
  signal debug_ctrl : debug_ctrl_t;

  -- misc/helpers --
  signal if_ack       : std_ulogic; -- acknowledge instruction data from instruction fetch (front-end)
  signal if_reset     : std_ulogic; -- reset instruction fetch (front-end)
  signal branch_taken : std_ulogic; -- fulfilled branch condition or unconditional jump
  signal monitor_cnt  : std_ulogic_vector(monitor_mc_tmo_c downto 0); -- execution monitor cycle counter
  signal monitor_exc  : std_ulogic; -- execution monitor timeout exception
  signal opcode       : std_ulogic_vector(6 downto 0); -- simplified opcode (2 LSBs hardwired to "11" to indicate rv32)
  signal immediate    : std_ulogic_vector(XLEN-1 downto 0); -- instruction's immediate
  signal illegal_cmd  : std_ulogic; -- illegal instruction check
  signal sleep_mode   : std_ulogic; -- CPU is in sleep-mode
  signal csr_valid    : std_ulogic_vector(2 downto 0); -- CSR access: [2] implemented, [1] r/w access, [0] privilege
  signal cnt_event    : std_ulogic_vector(11 downto 0); -- counter events
  signal hwtrig_match : std_ulogic; -- hardware trigger matches programmed address
  signal hwtrig_fired : std_ulogic; -- hardware trigger has fired

begin

  -- ****************************************************************************************************************************
  -- Instruction Execution
  -- ****************************************************************************************************************************

  -- Immediate Generator --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  imm_gen: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      immediate <= (others => '0');
    elsif rising_edge(clk_i) then
      if (exe_engine.state = EX_DISPATCH) then -- prepare update of next PC (using ALU's PC + IMM in EX_EXECUTE state)
        if RISCV_ISA_C and (frontend_i.compr = '1') then -- is decompressed C instruction?
          immediate <= x"00000002";
        else
          immediate <= x"00000004";
        end if;
      else
        case opcode is
          when opcode_store_c => -- S-immediate
            immediate <= replicate_f(exe_engine.ir(31), 21) & exe_engine.ir(30 downto 25) & exe_engine.ir(11 downto 7);
          when opcode_branch_c => -- B-immediate
            immediate <= replicate_f(exe_engine.ir(31), 20) & exe_engine.ir(7) & exe_engine.ir(30 downto 25) & exe_engine.ir(11 downto 8) & '0';
          when opcode_lui_c | opcode_auipc_c => -- U-immediate
            immediate <= exe_engine.ir(31 downto 12) & x"000";
          when opcode_jal_c => -- J-immediate
            immediate <= replicate_f(exe_engine.ir(31), 12) & exe_engine.ir(19 downto 12) & exe_engine.ir(20) & exe_engine.ir(30 downto 21) & '0';
          when opcode_amo_c => -- atomic memory access
            immediate <= (others => '0');
          when others => -- I-immediate
            immediate <= replicate_f(exe_engine.ir(31), 21) & exe_engine.ir(30 downto 21) & exe_engine.ir(20);
        end case;
      end if;
    end if;
  end process imm_gen;


  -- Branch Condition Check -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  branch_check: process(exe_engine.ir, alu_cmp_i)
  begin
    if (exe_engine.ir(instr_opcode_lsb_c+2) = '0') then -- conditional branch
      if (exe_engine.ir(instr_funct3_msb_c) = '0') then -- beq / bne
        branch_taken <= alu_cmp_i(cmp_equal_c) xor exe_engine.ir(instr_funct3_lsb_c);
      else -- blt(u) / bge(u)
        branch_taken <= alu_cmp_i(cmp_less_c) xor exe_engine.ir(instr_funct3_lsb_c);
      end if;
    else -- unconditional branch
      branch_taken <= '1';
    end if;
  end process branch_check;


  -- Execute Engine FSM Sync ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  execute_engine_fsm_sync: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      ctrl             <= ctrl_bus_zero_c;
      exe_engine.state <= EX_RESTART;
      exe_engine.ir    <= (others => '0');
      exe_engine.ci    <= '0';
      exe_engine.pc    <= BOOT_ADDR(XLEN-1 downto 2) & "00"; -- 32-bit-aligned boot address
      exe_engine.pc2   <= BOOT_ADDR(XLEN-1 downto 2) & "00"; -- 32-bit-aligned boot address
      exe_engine.ra    <= (others => '0');
      exe_engine.msync <= '0';
    elsif rising_edge(clk_i) then
      ctrl       <= ctrl_nxt;
      exe_engine <= exe_engine_nxt;
    end if;
  end process execute_engine_fsm_sync;

  -- simplified rv32 opcode --
  opcode <= exe_engine.ir(instr_opcode_msb_c downto instr_opcode_lsb_c+2) & "11";


  -- Execute Engine FSM Comb ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  execute_engine_fsm_comb: process(exe_engine, debug_ctrl, trap_ctrl, hwtrig_match, opcode, frontend_i, csr,
                                   ctrl, alu_cp_done_i, lsu_wait_i, alu_add_i, branch_taken, pmp_fault_i, mem_sync_i)
    variable funct3_v : std_ulogic_vector(2 downto 0);
    variable funct7_v : std_ulogic_vector(6 downto 0);
  begin
    -- shortcuts --
    funct3_v := exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c);
    funct7_v := exe_engine.ir(instr_funct7_msb_c downto instr_funct7_lsb_c);

    -- arbiter defaults --
    exe_engine_nxt.state <= exe_engine.state;
    exe_engine_nxt.ir    <= exe_engine.ir;
    exe_engine_nxt.ci    <= exe_engine.ci;
    exe_engine_nxt.pc    <= exe_engine.pc;
    exe_engine_nxt.pc2   <= exe_engine.pc2;
    exe_engine_nxt.ra    <= (others => '0'); -- output zero if not a branch instruction
    exe_engine_nxt.msync <= mem_sync_i and (not ctrl.lsu_fence);
    if_ack               <= '0';
    if_reset             <= '0';
    trap_ctrl.env_enter  <= '0';
    trap_ctrl.env_exit   <= '0';
    trap_ctrl.instr_be   <= '0';
    trap_ctrl.instr_ma   <= '0';
    trap_ctrl.ecall      <= '0';
    trap_ctrl.ebreak     <= '0';
    trap_ctrl.hwtrig     <= '0';
    csr.we_nxt           <= '0';
    csr.re_nxt           <= '0';
    ctrl_nxt             <= ctrl_bus_zero_c; -- all zero/off by default (ALU operation = ZERO, ALU.adder_out = ADD)

    -- ALU sign control --
    if (opcode(4) = '1') then -- ALU ops
      ctrl_nxt.alu_unsigned <= funct3_v(0); -- unsigned ALU operation? (SLTIU, SLTU)
    else -- branches
      ctrl_nxt.alu_unsigned <= funct3_v(1); -- unsigned branches? (BLTU, BGEU)
    end if;

    -- ALU operand A: is PC? --
    case opcode is
      when opcode_auipc_c | opcode_jal_c | opcode_branch_c =>
        ctrl_nxt.alu_opa_mux <= '1';
      when others =>
        ctrl_nxt.alu_opa_mux <= '0';
    end case;

    -- ALU operand B: is immediate? --
    case opcode is
      when opcode_alui_c | opcode_lui_c | opcode_auipc_c | opcode_load_c | opcode_store_c | opcode_amo_c | opcode_branch_c | opcode_jal_c | opcode_jalr_c =>
        ctrl_nxt.alu_opb_mux <= '1';
      when others =>
        ctrl_nxt.alu_opb_mux <= '0';
    end case;

    -- (atomic) memory read/write access --
    if RISCV_ISA_Zaamo and (opcode(2) = opcode_amo_c(2)) and (exe_engine.ir(instr_funct5_lsb_c+1) = '0') then -- atomic read-modify-write operation
      ctrl_nxt.lsu_amo <= '1';
      ctrl_nxt.lsu_rw  <= '0'; -- executed as single load for the CPU
    elsif RISCV_ISA_Zalrsc and (opcode(2) = opcode_amo_c(2)) and (exe_engine.ir(instr_funct5_lsb_c+1) = '1') then -- atomic reservation-set operation
      ctrl_nxt.lsu_amo <= '1';
      ctrl_nxt.lsu_rw  <= exe_engine.ir(instr_funct5_lsb_c);
    else -- normal load/store
      ctrl_nxt.lsu_amo <= '0';
      ctrl_nxt.lsu_rw  <= exe_engine.ir(instr_opcode_lsb_c+5);
    end if;

    -- state machine --
    case exe_engine.state is

      when EX_DISPATCH => -- wait for ISSUE ENGINE to emit a valid instruction word
      -- ------------------------------------------------------------
        ctrl_nxt.alu_opa_mux <= '1'; -- prepare update of next PC in EX_EXECUTE (opa = current PC)
        ctrl_nxt.alu_opb_mux <= '1'; -- prepare update of next PC in EX_EXECUTE (opb = imm = +2/4)
        --
        if (trap_ctrl.env_pending = '1') or (trap_ctrl.exc_fire = '1') then -- pending trap or pending exception (fast)
          exe_engine_nxt.state <= EX_TRAP_ENTER;
        elsif RISCV_ISA_Sdtrig and (hwtrig_match = '1') then -- hardware breakpoint
          exe_engine_nxt.pc    <= exe_engine.pc2(XLEN-1 downto 1) & '0'; -- PC <= next PC; intercept BEFORE executing the instruction
          trap_ctrl.hwtrig     <= '1';
          exe_engine_nxt.state <= EX_DISPATCH; -- stay here another round until trap_ctrl.hwtrig arrives in trap_ctrl.env_pending
        elsif (frontend_i.valid = '1') then -- new instruction word available
          if_ack               <= '1'; -- instruction data is about to be consumed
          trap_ctrl.instr_be   <= frontend_i.error; -- access fault during instruction fetch
          exe_engine_nxt.ci    <= frontend_i.compr; -- this is a de-compressed instruction
          exe_engine_nxt.ir    <= frontend_i.instr; -- instruction word
          exe_engine_nxt.pc    <= exe_engine.pc2(XLEN-1 downto 1) & '0'; -- PC <= next PC
          exe_engine_nxt.state <= EX_EXECUTE; -- start executing new instruction
        end if;

      when EX_TRAP_ENTER => -- enter trap environment and jump to trap vector
      -- ------------------------------------------------------------
        if (trap_ctrl.cause(5) = '1') and RISCV_ISA_Sdext then -- debug mode (re-)entry
          exe_engine_nxt.pc2 <= DEBUG_PARK_ADDR(XLEN-1 downto 2) & "00"; -- debug mode enter; start at "parking loop" <normal_entry>
        elsif (debug_ctrl.run = '1') and RISCV_ISA_Sdext then -- any other trap INSIDE debug mode
          exe_engine_nxt.pc2 <= DEBUG_EXC_ADDR(XLEN-1 downto 2) & "00"; -- debug mode enter: start at "parking loop" <exception_entry>
        else -- normal start of trap
          if (csr.mtvec(0) = '1') and (trap_ctrl.cause(6) = '1') then -- vectored mode + interrupt
            exe_engine_nxt.pc2 <= csr.mtvec(XLEN-1 downto 7) & trap_ctrl.cause(4 downto 0) & "00"; -- PC = mtvec + 4 * mcause
          else
            exe_engine_nxt.pc2 <= csr.mtvec(XLEN-1 downto 2) & "00"; -- PC = mtvec
          end if;
        end if;
        --
        if (trap_ctrl.env_pending = '1') then -- wait for sync. exceptions to become pending
          trap_ctrl.env_enter  <= '1';
          exe_engine_nxt.state <= EX_RESTART; -- restart instruction fetch
        end if;

      when EX_TRAP_EXIT => -- return from trap environment and jump to trap PC
      -- ------------------------------------------------------------
        if (debug_ctrl.run = '1') and RISCV_ISA_Sdext then -- debug mode exit
          exe_engine_nxt.pc2 <= csr.dpc(XLEN-1 downto 1) & '0';
        else -- normal end of trap
          exe_engine_nxt.pc2 <= csr.mepc(XLEN-1 downto 1) & '0';
        end if;
        trap_ctrl.env_exit   <= '1';
        exe_engine_nxt.state <= EX_RESTART; -- restart instruction fetch

      when EX_RESTART => -- reset and restart instruction fetch at next PC
      -- ------------------------------------------------------------
        ctrl_nxt.rf_zero_we  <= not bool_to_ulogic_f(CPU_RF_HW_RST_EN); -- house keeping: force writing zero to x0 if it's a phys. register
        if_reset             <= '1';
        exe_engine_nxt.state <= EX_BRANCHED; -- delay cycle to restart front-end

      when EX_EXECUTE => -- decode and execute instruction (control will be here for exactly 1 cycle in any case)
      -- ------------------------------------------------------------
        exe_engine_nxt.pc2 <= alu_add_i(XLEN-1 downto 1) & '0'; -- next PC (= PC + immediate)
        trap_ctrl.instr_be <= pmp_fault_i; -- did this instruction fetch cause a PMP-execute violation?

        -- decode instruction class/type; [NOTE] register file is read in THIS stage; due to the sync read data will be available in the NEXT state --
        case opcode is

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
               ((funct3_v = funct3_sadd_c) and (opcode(5) = '1') and (exe_engine.ir(instr_funct7_msb_c-1) = '1')) then -- SUB
              ctrl_nxt.alu_sub <= '1';
            end if;

            -- is base rv32i/e ALU[I] instruction (excluding shifts)? --
            if ((opcode(5) = '0') and (funct3_v /= funct3_sll_c) and (funct3_v /= funct3_sr_c)) or -- base ALUI instruction (excluding SLLI, SRLI, SRAI)
               ((opcode(5) = '1') and (((funct3_v = funct3_sadd_c) and (funct7_v = "0000000")) or ((funct3_v = funct3_sadd_c) and (funct7_v = "0100000")) or
                                       ((funct3_v = funct3_slt_c)  and (funct7_v = "0000000")) or ((funct3_v = funct3_sltu_c) and (funct7_v = "0000000")) or
                                       ((funct3_v = funct3_xor_c)  and (funct7_v = "0000000")) or ((funct3_v = funct3_or_c)   and (funct7_v = "0000000")) or
                                       ((funct3_v = funct3_and_c)  and (funct7_v = "0000000")))) then -- base ALU instruction (excluding SLL, SRL, SRA)
              ctrl_nxt.rf_wb_en    <= '1'; -- valid RF write-back (won't happen if exception)
              exe_engine_nxt.state <= EX_DISPATCH;
            else -- [NOTE] illegal ALU[I] instructions are handled as multi-cycle operations that will time-out as no ALU co-processor responds
              ctrl_nxt.alu_cp_alu  <= '1'; -- trigger ALU[I] opcode-space co-processor
              exe_engine_nxt.state <= EX_ALU_WAIT;
            end if;

          -- load upper immediate --
          when opcode_lui_c =>
            ctrl_nxt.alu_op      <= alu_op_movb_c; -- pass immediate
            ctrl_nxt.rf_wb_en    <= '1'; -- valid RF write-back (won't happen if exception)
            exe_engine_nxt.state <= EX_DISPATCH;

          -- add upper immediate to PC --
          when opcode_auipc_c =>
            ctrl_nxt.alu_op      <= alu_op_add_c; -- add PC and immediate
            ctrl_nxt.rf_wb_en    <= '1'; -- valid RF write-back (won't happen if exception)
            exe_engine_nxt.state <= EX_DISPATCH;

          -- memory access --
          when opcode_load_c | opcode_store_c | opcode_amo_c =>
            exe_engine_nxt.state <= EX_MEM_REQ;

          -- branch / jump-and-link (with register) --
          when opcode_branch_c | opcode_jal_c | opcode_jalr_c =>
            exe_engine_nxt.state <= EX_BRANCH;

          -- memory fence operations (execute even if illegal funct3) --
          when opcode_fence_c =>
            ctrl_nxt.lsu_fence   <= '1'; -- load/store fence (always executed)
            exe_engine_nxt.state <= EX_FENCE;

          -- FPU: floating-point operations --
          when opcode_fop_c =>
            ctrl_nxt.alu_cp_fpu  <= '1'; -- trigger FPU co-processor
            exe_engine_nxt.state <= EX_ALU_WAIT; -- will be aborted via monitor timeout if FPU is not implemented

          -- CFU: custom RISC-V instructions --
          when opcode_cust0_c | opcode_cust1_c =>
            ctrl_nxt.alu_cp_cfu  <= '1'; -- trigger CFU co-processor
            exe_engine_nxt.state <= EX_ALU_WAIT; -- will be aborted via monitor timeout if CFU is not implemented

          -- environment/CSR operation or ILLEGAL opcode --
          when others =>
            if ((funct3_v = funct3_csrrw_c) or (funct3_v = funct3_csrrwi_c)) and (exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c) = "00000") then
              csr.re_nxt <= '0'; -- no read if CSRRW[I] and rd = 0
            else
              csr.re_nxt <= '1';
            end if;
            exe_engine_nxt.state <= EX_SYSTEM;

        end case; -- /EX_EXECUTE

      when EX_ALU_WAIT => -- wait for multi-cycle ALU co-processor operation to finish or trap
      -- ------------------------------------------------------------
        ctrl_nxt.alu_op <= alu_op_cp_c;
        if (alu_cp_done_i = '1') or (trap_ctrl.exc_buf(exc_illegal_c) = '1') then
          ctrl_nxt.rf_wb_en    <= '1'; -- valid RF write-back (won't happen if exception)
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when EX_FENCE => -- wait for LOAD/STORE memory synchronization
      -- ------------------------------------------------------------
        if (exe_engine.msync = '1') then -- wait for pending synchronization request to complete
          if (exe_engine.ir(instr_funct3_lsb_c) = '1') then -- fence.i
            ctrl_nxt.if_fence <= '1';
          end if;
          exe_engine_nxt.state <= EX_RESTART; -- reset instruction fetch + IPB (EX_DISPATCH would be sufficient for normal FENCE)
        end if;

      when EX_BRANCH => -- update next PC on taken branches and jumps
      -- ------------------------------------------------------------
        exe_engine_nxt.ra <= exe_engine.pc2(XLEN-1 downto 1) & '0'; -- output return address
        ctrl_nxt.rf_wb_en <= opcode(2); -- save return address if link operation (won't happen if exception)
        if (trap_ctrl.exc_buf(exc_illegal_c) = '0') and (branch_taken = '1') then -- valid taken branch / jump
          trap_ctrl.instr_ma   <= alu_add_i(1) and bool_to_ulogic_f(not RISCV_ISA_C); -- branch destination is misaligned?
          if_reset             <= '1'; -- reset instruction fetch to restart at modified PC
          exe_engine_nxt.pc2   <= alu_add_i(XLEN-1 downto 1) & '0';
          exe_engine_nxt.state <= EX_BRANCHED; -- shortcut (faster than going to EX_RESTART)
        else
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when EX_BRANCHED => -- delay cycle to wait for reset of front-end (instruction fetch)
      -- ------------------------------------------------------------
        exe_engine_nxt.state <= EX_DISPATCH;

      when EX_MEM_REQ => -- trigger memory request
      -- ------------------------------------------------------------
        if (trap_ctrl.exc_buf(exc_illegal_c) = '0') then -- memory request only if not an illegal instruction
          ctrl_nxt.lsu_req <= '1'; -- memory access request
        end if;
        exe_engine_nxt.state <= EX_MEM_RSP;

      when EX_MEM_RSP => -- wait for memory response
      -- ------------------------------------------------------------
        if (lsu_wait_i = '0') or -- bus system has completed the transaction (if there was any)
           (trap_ctrl.exc_buf(exc_saccess_c) = '1') or (trap_ctrl.exc_buf(exc_laccess_c) = '1') or -- access exception
           (trap_ctrl.exc_buf(exc_salign_c)  = '1') or (trap_ctrl.exc_buf(exc_lalign_c)  = '1') or -- alignment exception
           (trap_ctrl.exc_buf(exc_illegal_c) = '1') then -- illegal instruction exception
          ctrl_nxt.rf_wb_en    <= (not ctrl.lsu_rw) or ctrl.lsu_amo; -- write-back to register file if read operation (won't happen in case of exception)
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when EX_SLEEP => -- sleep mode
      -- ------------------------------------------------------------
        if (trap_ctrl.wakeup = '1') then
          exe_engine_nxt.state <= EX_DISPATCH;
        end if;

      when others => -- EX_SYSTEM - CSR/ENVIRONMENT operation; no effect if illegal instruction
      -- ------------------------------------------------------------
        exe_engine_nxt.state <= EX_DISPATCH; -- default
        if (funct3_v = funct3_env_c) and (trap_ctrl.exc_buf(exc_illegal_c) = '0') then -- non-illegal ENVIRONMENT
          case exe_engine.ir(instr_funct12_lsb_c+2 downto instr_funct12_lsb_c) is -- three LSBs are sufficient here
            when "000"  => trap_ctrl.ecall      <= '1'; -- ecall
            when "001"  => trap_ctrl.ebreak     <= '1'; -- ebreak
            when "010"  => exe_engine_nxt.state <= EX_TRAP_EXIT; -- xret
            when "101"  => exe_engine_nxt.state <= EX_SLEEP; -- wfi
            when others => exe_engine_nxt.state <= EX_DISPATCH; -- illegal or CSR operation
          end case;
        end if;
        -- always write to CSR (if CSR instruction); ENVIRONMENT operations have rs1/imm5 = zero so this won't happen then --
        if (funct3_v = funct3_csrrw_c) or (funct3_v = funct3_csrrwi_c) or (exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c) /= "00000") then
          csr.we_nxt <= '1'; -- CSRRW[I]: always write CSR; CSRR[S/C][I]: write CSR if rs1/imm5 is NOT zero
        end if;
        -- always write to RF (even if csr.re = 0, but then we have rd = 0); ENVIRONMENT operations have rd = zero so this does not hurt --
        ctrl_nxt.rf_wb_en <= '1'; -- won't happen if exception

    end case;
  end process execute_engine_fsm_comb;


  -- CPU Control Bus Output -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------

  -- instruction fetch --
  ctrl_o.if_fence     <= ctrl.if_fence;
  ctrl_o.if_reset     <= if_reset;
  ctrl_o.if_ack       <= if_ack;
  -- program counter --
  ctrl_o.pc_cur       <= exe_engine.pc(XLEN-1 downto 1) & '0';
  ctrl_o.pc_nxt       <= exe_engine.pc2(XLEN-1 downto 1) & '0';
  ctrl_o.pc_ret       <= exe_engine.ra(XLEN-1 downto 1) & '0';
  -- register file --
  ctrl_o.rf_wb_en     <= ctrl.rf_wb_en and (not trap_ctrl.exc_fire); -- inhibit write-back if exception
  ctrl_o.rf_rs1       <= exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c);
  ctrl_o.rf_rs2       <= exe_engine.ir(instr_rs2_msb_c downto instr_rs2_lsb_c);
  ctrl_o.rf_rd        <= exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c);
  ctrl_o.rf_zero_we   <= ctrl.rf_zero_we;
  -- alu --
  ctrl_o.alu_op       <= ctrl.alu_op;
  ctrl_o.alu_sub      <= ctrl.alu_sub;
  ctrl_o.alu_opa_mux  <= ctrl.alu_opa_mux;
  ctrl_o.alu_opb_mux  <= ctrl.alu_opb_mux;
  ctrl_o.alu_unsigned <= ctrl.alu_unsigned;
  ctrl_o.alu_imm      <= immediate;
  ctrl_o.alu_cp_alu   <= ctrl.alu_cp_alu;
  ctrl_o.alu_cp_cfu   <= ctrl.alu_cp_cfu;
  ctrl_o.alu_cp_fpu   <= ctrl.alu_cp_fpu;
  -- load/store unit --
  ctrl_o.lsu_req      <= ctrl.lsu_req;
  ctrl_o.lsu_rw       <= ctrl.lsu_rw;
  ctrl_o.lsu_amo      <= ctrl.lsu_amo;
  ctrl_o.lsu_mo_we    <= '1' when (exe_engine.state = EX_MEM_REQ) else '0'; -- write memory output registers (data & address)
  ctrl_o.lsu_fence    <= ctrl.lsu_fence;
  ctrl_o.lsu_priv     <= csr.mstatus_mpp when (csr.mstatus_mprv = '1') else csr.prv_level_eff; -- effective privilege level for loads/stores in M-mode
  -- control and status registers --
  ctrl_o.csr_we       <= csr.we;
  ctrl_o.csr_re       <= csr.re;
  ctrl_o.csr_addr     <= csr.addr;
  ctrl_o.csr_wdata    <= csr.wdata;
  ctrl_o.cnt_halt     <= csr.mcountinhibit;
  ctrl_o.cnt_event    <= cnt_event;
  -- instruction word bit fields --
  ctrl_o.ir_funct3    <= exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c);
  ctrl_o.ir_funct12   <= exe_engine.ir(instr_funct12_msb_c downto instr_funct12_lsb_c);
  ctrl_o.ir_opcode    <= opcode;
  -- cpu status --
  ctrl_o.cpu_priv     <= csr.prv_level_eff;
  ctrl_o.cpu_sleep    <= sleep_mode;
  ctrl_o.cpu_trap     <= trap_ctrl.env_enter;
  ctrl_o.cpu_debug    <= debug_ctrl.run;


  -- ****************************************************************************************************************************
  -- Illegal Instruction Detection
  -- ****************************************************************************************************************************

  -- Instruction Execution Monitor (trap if multi-cycle instruction does not complete) ------
  -- -------------------------------------------------------------------------------------------
  multi_cycle_monitor: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      monitor_cnt <= (others => '0');
    elsif rising_edge(clk_i) then
      if (exe_engine.state = EX_ALU_WAIT) then
        monitor_cnt <= std_ulogic_vector(unsigned(monitor_cnt) + 1);
      else
        monitor_cnt <= (others => '0');
      end if;
    end if;
  end process multi_cycle_monitor;

  -- raise illegal instruction exception if a multi-cycle instruction takes longer than a bound amount of time --
  monitor_exc <= monitor_cnt(monitor_cnt'left);


  -- CSR Access Check -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_check: process(exe_engine.ir, debug_ctrl.run, csr)
    variable csr_addr_v : std_ulogic_vector(11 downto 0);
  begin
    -- shortcut: CSR address right from the instruction word --
    csr_addr_v := exe_engine.ir(instr_imm12_msb_c downto instr_imm12_lsb_c);

    -- ------------------------------------------------------------
    -- Available at all
    -- ------------------------------------------------------------
    case csr_addr_v is

      -- user-defined U-mode CFU CSRs --
      when csr_cfureg0_c | csr_cfureg1_c | csr_cfureg2_c | csr_cfureg3_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zxcfu); -- available if CFU implemented

      -- floating-point CSRs --
      when csr_fflags_c | csr_frm_c | csr_fcsr_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zfinx); -- available if FPU implemented

      -- machine trap setup/handling, environment/information registers, etc. --
      when csr_mstatus_c   | csr_mstatush_c      | csr_misa_c      | csr_mie_c       | csr_mtvec_c  |
           csr_mscratch_c  | csr_mepc_c          | csr_mcause_c    | csr_mip_c       | csr_mtval_c  |
           csr_mtinst_c    | csr_mcountinhibit_c | csr_mvendorid_c | csr_marchid_c   | csr_mimpid_c |
           csr_mhartid_c   | csr_mconfigptr_c    | csr_mxisa_c     | csr_mxiccsreg_c | csr_mxiccdata_c =>
        csr_valid(2) <= '1'; -- always implemented

      -- machine-controlled user-mode CSRs --
      when csr_mcounteren_c | csr_menvcfg_c | csr_menvcfgh_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_U); -- available if U-mode implemented

      -- physical memory protection (PMP) --
      when csr_pmpcfg0_c   | csr_pmpcfg1_c   | csr_pmpcfg2_c   | csr_pmpcfg3_c   | -- configuration
           csr_pmpaddr0_c  | csr_pmpaddr1_c  | csr_pmpaddr2_c  | csr_pmpaddr3_c  |
           csr_pmpaddr4_c  | csr_pmpaddr5_c  | csr_pmpaddr6_c  | csr_pmpaddr7_c  | -- address
           csr_pmpaddr8_c  | csr_pmpaddr9_c  | csr_pmpaddr10_c | csr_pmpaddr11_c |
           csr_pmpaddr12_c | csr_pmpaddr13_c | csr_pmpaddr14_c | csr_pmpaddr15_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Smpmp); -- available if PMP implemented

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
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zihpm); -- available if Zihpm implemented

      -- counter and timer CSRs --
      when csr_cycle_c | csr_mcycle_c | csr_instret_c | csr_minstret_c | csr_cycleh_c | csr_mcycleh_c | csr_instreth_c | csr_minstreth_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Zicntr); -- available if Zicntr implemented

      -- debug-mode CSRs --
      when csr_dcsr_c | csr_dpc_c | csr_dscratch0_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Sdext); -- available if debug-mode implemented

      -- trigger module CSRs --
      when csr_tselect_c | csr_tdata1_c | csr_tdata2_c | csr_tinfo_c =>
        csr_valid(2) <= bool_to_ulogic_f(RISCV_ISA_Sdtrig); -- available if trigger module implemented

      -- undefined / not implemented --
      when others =>
        csr_valid(2) <= '0'; -- invalid access

    end case;

    -- ------------------------------------------------------------
    -- R/W capabilities
    -- ------------------------------------------------------------
    if (csr_addr_v(11 downto 10) = "11") and -- CSR is read-only
       ((exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_csrrw_c)  or -- will always write to CSR
        (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_csrrwi_c) or -- will always write to CSR
        (exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c) /= "00000")) then -- clear/set instructions: write to CSR only if rs1/imm5 is NOT zero
      csr_valid(1) <= '0'; -- invalid access
    else
      csr_valid(1) <= '1'; -- access granted
    end if;

    -- ------------------------------------------------------------
    -- Privilege level
    -- ------------------------------------------------------------
    if (csr_addr_v(11 downto 4) = csr_dcsr_c(11 downto 4)) and -- debug-mode-only CSR?
       RISCV_ISA_Sdext and (debug_ctrl.run = '0') then -- debug-mode implemented and not running?
      csr_valid(0) <= '0'; -- invalid access
    elsif RISCV_ISA_Zicntr and RISCV_ISA_U and (csr.prv_level_eff = '0') and -- any user-mode counters available and in user-mode?
          (csr_addr_v(11 downto 8) = csr_cycle_c(11 downto 8)) and -- user-mode counter access
          (((csr_addr_v(1 downto 0) = csr_cycle_c(1 downto 0)) and (csr.mcounteren_cy = '0')) or -- illegal access to cycle
           ((csr_addr_v(1 downto 0) = csr_instret_c(1 downto 0)) and (csr.mcounteren_ir = '0'))) then -- illegal access to instret
      csr_valid(0) <= '0'; -- invalid access
    elsif (csr_addr_v(9 downto 8) /= "00") and (csr.prv_level_eff = '0') then -- invalid privilege level
      csr_valid(0) <= '0'; -- invalid access
    else
      csr_valid(0) <= '1'; -- access granted
    end if;

  end process csr_check;


  -- Illegal Instruction Check --------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  illegal_check: process(exe_engine, csr, csr_valid, debug_ctrl)
  begin
    illegal_cmd <= '1'; -- default: illegal
    case exe_engine.ir(instr_opcode_msb_c downto instr_opcode_lsb_c) is -- check entire opcode

      when opcode_lui_c | opcode_auipc_c | opcode_jal_c => -- U-instruction type
        illegal_cmd <= '0'; -- all encodings are valid

      when opcode_jalr_c => -- unconditional jump-and-link
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = "000") then
          illegal_cmd <= '0';
        end if;

      when opcode_branch_c => -- conditional branch
        case exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_beq_c | funct3_bne_c | funct3_blt_c | funct3_bge_c | funct3_bltu_c | funct3_bgeu_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      when opcode_load_c => -- memory load
        case exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_lb_c | funct3_lh_c | funct3_lw_c | funct3_lbu_c | funct3_lhu_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      when opcode_store_c => -- memory store
        case exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) is
          when funct3_sb_c | funct3_sh_c | funct3_sw_c => illegal_cmd <= '0';
          when others => illegal_cmd <= '1';
        end case;

      when opcode_amo_c => -- atomic memory operation
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = "010") then -- word-quantity only
          case exe_engine.ir(instr_funct5_msb_c downto instr_funct5_lsb_c) is
            when "00001" | "00000" | "00100" | "01100" | "01000" | "10000" | "10100" | "11000" | "11100" => illegal_cmd <= not bool_to_ulogic_f(RISCV_ISA_Zaamo);
            when "00010" | "00011" => illegal_cmd <= not bool_to_ulogic_f(RISCV_ISA_Zalrsc);
            when others => illegal_cmd <= '1';
          end case;
        end if;

      when opcode_alu_c | opcode_alui_c | opcode_fop_c | opcode_cust0_c | opcode_cust1_c => -- ALU[I] / FPU / custom operations
        illegal_cmd <= '0'; -- [NOTE] valid if not terminated/invalidated by the "instruction execution monitor"

      when opcode_fence_c => -- memory ordering
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c+1) = funct3_fence_c(2 downto 1)) then
          illegal_cmd <= '0';
        end if;

      when opcode_system_c => -- CSR / system instruction
        if (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) = funct3_env_c) then -- system environment
          if (exe_engine.ir(instr_rs1_msb_c downto instr_rs1_lsb_c) = "00000") and (exe_engine.ir(instr_rd_msb_c downto instr_rd_lsb_c) = "00000") then
            case exe_engine.ir(instr_funct12_msb_c downto instr_funct12_lsb_c) is
              when funct12_ecall_c  => illegal_cmd <= '0'; -- ecall is always allowed
              when funct12_ebreak_c => illegal_cmd <= '0'; -- ebreak is always allowed
              when funct12_mret_c   => illegal_cmd <= (not csr.prv_level) or debug_ctrl.run; -- mret allowed in (real/non-debug) M-mode only
              when funct12_dret_c   => illegal_cmd <= not debug_ctrl.run; -- dret allowed in debug mode only
              when funct12_wfi_c    => illegal_cmd <= (not csr.prv_level) and csr.mstatus_tw; -- wfi allowed in M-mode or if TW is zero
              when others           => illegal_cmd <= '1'; -- undefined
            end case;
          end if;
        elsif (csr_valid = "111") and (exe_engine.ir(instr_funct3_msb_c downto instr_funct3_lsb_c) /= funct3_csril_c) then -- valid CSR operation
          illegal_cmd <= '0';
        end if;

      when others => -- undefined/unimplemented/illegal opcode
        illegal_cmd <= '1';

    end case;
  end process illegal_check;


  -- Illegal Operation Check ----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap_ctrl.instr_il <= '1' when ((exe_engine.state = EX_EXECUTE) or (exe_engine.state = EX_ALU_WAIT)) and -- check in execution states only
                                 ((monitor_exc = '1') or (illegal_cmd = '1')) else '0'; -- instruction timeout or illegal instruction


  -- ****************************************************************************************************************************
  -- Trap Controller
  -- ****************************************************************************************************************************

  -- Exception Buffer -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  exception_buffer: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap_ctrl.exc_buf <= (others => '0');
    elsif rising_edge(clk_i) then

      -- Exception Buffer -----------------------------------------------------
      -- If several exception sources trigger at once, all the requests will
      -- stay active until the trap environment is started. Only the exception
      -- with highest priority will be used to update the MCAUSE CSR. All
      -- remaining ones will be discarded.
      -- ----------------------------------------------------------------------

      -- misaligned load/store/instruction address --
      trap_ctrl.exc_buf(exc_lalign_c) <= (trap_ctrl.exc_buf(exc_lalign_c) or lsu_err_i(0))       and (not trap_ctrl.env_enter);
      trap_ctrl.exc_buf(exc_salign_c) <= (trap_ctrl.exc_buf(exc_salign_c) or lsu_err_i(2))       and (not trap_ctrl.env_enter);
      trap_ctrl.exc_buf(exc_ialign_c) <= (trap_ctrl.exc_buf(exc_ialign_c) or trap_ctrl.instr_ma) and (not trap_ctrl.env_enter);

      -- load/store/instruction access fault --
      trap_ctrl.exc_buf(exc_laccess_c) <= (trap_ctrl.exc_buf(exc_laccess_c) or lsu_err_i(1))       and (not trap_ctrl.env_enter);
      trap_ctrl.exc_buf(exc_saccess_c) <= (trap_ctrl.exc_buf(exc_saccess_c) or lsu_err_i(3))       and (not trap_ctrl.env_enter);
      trap_ctrl.exc_buf(exc_iaccess_c) <= (trap_ctrl.exc_buf(exc_iaccess_c) or trap_ctrl.instr_be) and (not trap_ctrl.env_enter);

      -- illegal instruction & environment call --
      trap_ctrl.exc_buf(exc_ecall_c)   <= (trap_ctrl.exc_buf(exc_ecall_c)   or trap_ctrl.ecall)    and (not trap_ctrl.env_enter);
      trap_ctrl.exc_buf(exc_illegal_c) <= (trap_ctrl.exc_buf(exc_illegal_c) or trap_ctrl.instr_il) and (not trap_ctrl.env_enter);

      -- break point --
      if RISCV_ISA_Sdext then
        trap_ctrl.exc_buf(exc_ebreak_c) <= (not trap_ctrl.env_enter) and (trap_ctrl.exc_buf(exc_ebreak_c) or
          (trap_ctrl.hwtrig and (not csr.tdata1_action)) or -- trigger module fires and enter-debug-action is disabled
          (trap_ctrl.ebreak and (    csr.prv_level) and (not csr.dcsr_ebreakm) and (not debug_ctrl.run)) or -- enter M-mode handler on ebreak in M-mode
          (trap_ctrl.ebreak and (not csr.prv_level) and (not csr.dcsr_ebreaku) and (not debug_ctrl.run)));  -- enter M-mode handler on ebreak in U-mode
      else
        trap_ctrl.exc_buf(exc_ebreak_c) <= (trap_ctrl.exc_buf(exc_ebreak_c) or trap_ctrl.ebreak or (trap_ctrl.hwtrig and (not csr.tdata1_action))) and (not trap_ctrl.env_enter);
      end if;

      -- debug-mode entry --
      trap_ctrl.exc_buf(exc_db_break_c) <= (trap_ctrl.exc_buf(exc_db_break_c) or debug_ctrl.trig_break) and (not trap_ctrl.env_enter);
      trap_ctrl.exc_buf(exc_db_hw_c)    <= (trap_ctrl.exc_buf(exc_db_hw_c)    or debug_ctrl.trig_hw)    and (not trap_ctrl.env_enter);
    end if;
  end process exception_buffer;


  -- Interrupt Buffer -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  interrupt_buffer: process(rstn_i, clk_aux_i) -- always-on clock domain
  begin
    if (rstn_i = '0') then
      trap_ctrl.irq_pnd <= (others => '0');
      trap_ctrl.irq_buf <= (others => '0');
    elsif rising_edge(clk_aux_i) then

      -- Interrupt-Pending Buffer ---------------------------------------------
      -- Once triggered the interrupt line should stay active until explicitly
      -- cleared by a mechanism specific to the interrupt-causing source.
      -- ----------------------------------------------------------------------

      -- RISC-V machine interrupts --
      trap_ctrl.irq_pnd(irq_msi_irq_c) <= irq_machine_i(0);
      trap_ctrl.irq_pnd(irq_mei_irq_c) <= irq_machine_i(1);
      trap_ctrl.irq_pnd(irq_mti_irq_c) <= irq_machine_i(2);

      -- NEORV32-specific fast interrupts --
      trap_ctrl.irq_pnd(irq_firq_15_c downto irq_firq_0_c) <= irq_fast_i(15 downto 0);

      -- debug-mode entry --
      trap_ctrl.irq_pnd(irq_db_halt_c) <= '0'; -- unused
      trap_ctrl.irq_pnd(irq_db_step_c) <= '0'; -- unused

      -- Interrupt Buffer -----------------------------------------------------
      -- Masking of interrupt request lines. Additionally, this buffer ensures
      -- that an active interrupt request line stays active (even when
      -- disabled via MIE) if the trap environment is already starting.
      -- ----------------------------------------------------------------------

      -- RISC-V machine interrupts --
      trap_ctrl.irq_buf(irq_msi_irq_c) <= (trap_ctrl.irq_pnd(irq_msi_irq_c) and csr.mie_msi) or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_msi_irq_c));
      trap_ctrl.irq_buf(irq_mei_irq_c) <= (trap_ctrl.irq_pnd(irq_mei_irq_c) and csr.mie_mei) or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_mei_irq_c));
      trap_ctrl.irq_buf(irq_mti_irq_c) <= (trap_ctrl.irq_pnd(irq_mti_irq_c) and csr.mie_mti) or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_mti_irq_c));

      -- NEORV32-specific fast interrupts --
      for i in 0 to 15 loop
        trap_ctrl.irq_buf(irq_firq_0_c+i) <= (trap_ctrl.irq_pnd(irq_firq_0_c+i) and csr.mie_firq(i)) or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_firq_0_c+i));
      end loop;

      -- debug-mode entry --
      trap_ctrl.irq_buf(irq_db_halt_c) <= debug_ctrl.trig_halt or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_db_halt_c));
      trap_ctrl.irq_buf(irq_db_step_c) <= debug_ctrl.trig_step or (trap_ctrl.env_pending and trap_ctrl.irq_buf(irq_db_step_c));
    end if;
  end process interrupt_buffer;


  -- Trap Priority Logic --------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap_priority: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap_ctrl.cause <= (others => '0');
    elsif rising_edge(clk_i) then
      trap_ctrl.cause <= (others => '0'); -- default
      -- standard RISC-V exceptions --
      if    (trap_ctrl.exc_buf(exc_iaccess_c)  = '1') then trap_ctrl.cause <= trap_iaf_c; -- instruction access fault
      elsif (trap_ctrl.exc_buf(exc_illegal_c)  = '1') then trap_ctrl.cause <= trap_iil_c; -- illegal instruction
      elsif (trap_ctrl.exc_buf(exc_ialign_c)   = '1') then trap_ctrl.cause <= trap_ima_c; -- instruction address misaligned
      elsif (trap_ctrl.exc_buf(exc_ecall_c)    = '1') then trap_ctrl.cause <= trap_env_c(6 downto 2) & replicate_f(csr.prv_level, 2); -- environment call (U/M)
      elsif (trap_ctrl.exc_buf(exc_ebreak_c)   = '1') then trap_ctrl.cause <= trap_brk_c; -- environment breakpoint
      elsif (trap_ctrl.exc_buf(exc_salign_c)   = '1') then trap_ctrl.cause <= trap_sma_c; -- store address misaligned
      elsif (trap_ctrl.exc_buf(exc_lalign_c)   = '1') then trap_ctrl.cause <= trap_lma_c; -- load address misaligned
      elsif (trap_ctrl.exc_buf(exc_saccess_c)  = '1') then trap_ctrl.cause <= trap_saf_c; -- store access fault
      elsif (trap_ctrl.exc_buf(exc_laccess_c)  = '1') then trap_ctrl.cause <= trap_laf_c; -- load access fault
      -- standard RISC-V debug mode exceptions and interrupts --
      elsif (trap_ctrl.irq_buf(irq_db_halt_c)  = '1') then trap_ctrl.cause <= trap_db_halt_c;  -- external halt request (async)
      elsif (trap_ctrl.exc_buf(exc_db_hw_c)    = '1') then trap_ctrl.cause <= trap_db_trig_c;  -- hardware trigger (sync)
      elsif (trap_ctrl.exc_buf(exc_db_break_c) = '1') then trap_ctrl.cause <= trap_db_break_c; -- breakpoint (sync)
      elsif (trap_ctrl.irq_buf(irq_db_step_c)  = '1') then trap_ctrl.cause <= trap_db_step_c;  -- single stepping (async)
      -- NEORV32-specific fast interrupts --
      elsif (trap_ctrl.irq_buf(irq_firq_0_c)   = '1') then trap_ctrl.cause <= trap_firq0_c;  -- fast interrupt channel 0
      elsif (trap_ctrl.irq_buf(irq_firq_1_c)   = '1') then trap_ctrl.cause <= trap_firq1_c;  -- fast interrupt channel 1
      elsif (trap_ctrl.irq_buf(irq_firq_2_c)   = '1') then trap_ctrl.cause <= trap_firq2_c;  -- fast interrupt channel 2
      elsif (trap_ctrl.irq_buf(irq_firq_3_c)   = '1') then trap_ctrl.cause <= trap_firq3_c;  -- fast interrupt channel 3
      elsif (trap_ctrl.irq_buf(irq_firq_4_c)   = '1') then trap_ctrl.cause <= trap_firq4_c;  -- fast interrupt channel 4
      elsif (trap_ctrl.irq_buf(irq_firq_5_c)   = '1') then trap_ctrl.cause <= trap_firq5_c;  -- fast interrupt channel 5
      elsif (trap_ctrl.irq_buf(irq_firq_6_c)   = '1') then trap_ctrl.cause <= trap_firq6_c;  -- fast interrupt channel 6
      elsif (trap_ctrl.irq_buf(irq_firq_7_c)   = '1') then trap_ctrl.cause <= trap_firq7_c;  -- fast interrupt channel 7
      elsif (trap_ctrl.irq_buf(irq_firq_8_c)   = '1') then trap_ctrl.cause <= trap_firq8_c;  -- fast interrupt channel 8
      elsif (trap_ctrl.irq_buf(irq_firq_9_c)   = '1') then trap_ctrl.cause <= trap_firq9_c;  -- fast interrupt channel 9
      elsif (trap_ctrl.irq_buf(irq_firq_10_c)  = '1') then trap_ctrl.cause <= trap_firq10_c; -- fast interrupt channel 10
      elsif (trap_ctrl.irq_buf(irq_firq_11_c)  = '1') then trap_ctrl.cause <= trap_firq11_c; -- fast interrupt channel 11
      elsif (trap_ctrl.irq_buf(irq_firq_12_c)  = '1') then trap_ctrl.cause <= trap_firq12_c; -- fast interrupt channel 12
      elsif (trap_ctrl.irq_buf(irq_firq_13_c)  = '1') then trap_ctrl.cause <= trap_firq13_c; -- fast interrupt channel 13
      elsif (trap_ctrl.irq_buf(irq_firq_14_c)  = '1') then trap_ctrl.cause <= trap_firq14_c; -- fast interrupt channel 14
      elsif (trap_ctrl.irq_buf(irq_firq_15_c)  = '1') then trap_ctrl.cause <= trap_firq15_c; -- fast interrupt channel 15
      -- standard RISC-V interrupts --
      elsif (trap_ctrl.irq_buf(irq_mei_irq_c)  = '1') then trap_ctrl.cause <= trap_mei_c; -- machine external interrupt (MEI)
      elsif (trap_ctrl.irq_buf(irq_msi_irq_c)  = '1') then trap_ctrl.cause <= trap_msi_c; -- machine software interrupt (MSI)
      elsif (trap_ctrl.irq_buf(irq_mti_irq_c)  = '1') then trap_ctrl.cause <= trap_mti_c; -- machine timer interrupt (MTI)
      end if;
    end if;
  end process trap_priority;

  -- exception program counter: async. interrupt or sync. exception? --
  trap_ctrl.epc <= exe_engine.pc2 when (trap_ctrl.cause(trap_ctrl.cause'left) = '1') else exe_engine.pc;


  -- Trap Controller ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  trap_controller: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      trap_ctrl.env_pending <= '0';
      trap_ctrl.env_entered <= '0';
    elsif rising_edge(clk_i) then
      -- pending trap environment --
      if (trap_ctrl.env_pending = '0') then -- no pending trap environment yet
        if (trap_ctrl.exc_fire = '1') or (or_reduce_f(trap_ctrl.irq_fire) = '1') then
          trap_ctrl.env_pending <= '1'; -- execute engine can start trap handling
        end if;
      else -- trap waiting to be served
        if (trap_ctrl.env_enter = '1') then -- start of trap environment acknowledged by execute engine
          trap_ctrl.env_pending <= '0';
        end if;
      end if;
      -- trap environment has just been entered --
      if (exe_engine.state = EX_EXECUTE) then -- first instruction of trap environment is executing
        trap_ctrl.env_entered <= '0';
      elsif (trap_ctrl.env_enter = '1') then
        trap_ctrl.env_entered <= '1';
      end if;
    end if;
  end process trap_controller;

  -- any exception? --
  trap_ctrl.exc_fire <= '1' when (or_reduce_f(trap_ctrl.exc_buf) = '1') else '0'; -- sync. exceptions CANNOT be masked

  -- system interrupt? --
  trap_ctrl.irq_fire(0) <= '1' when
    (exe_engine.state = EX_EXECUTE) and -- trigger system IRQ only in EX_EXECUTE state
    (or_reduce_f(trap_ctrl.irq_buf(irq_firq_15_c downto irq_msi_irq_c)) = '1') and -- pending system IRQ
    ((csr.mstatus_mie = '1') or (csr.prv_level = priv_mode_u_c)) and -- IRQ only when in M-mode and MIE=1 OR when in U-mode
    (debug_ctrl.run = '0') and (csr.dcsr_step = '0') else '0'; -- no system IRQs when in debug-mode / during single-stepping

  -- debug-entry halt interrupt? --
  trap_ctrl.irq_fire(1) <= '1' when
    ((exe_engine.state = EX_EXECUTE) or (exe_engine.state = EX_BRANCHED)) and -- allow halt also after "reset" (#879)
    (trap_ctrl.irq_buf(irq_db_halt_c) = '1') else '0'; -- pending external halt

  -- debug-entry single-step interrupt? --
  trap_ctrl.irq_fire(2) <= '1' when
    ((exe_engine.state = EX_EXECUTE) or -- trigger single-step in EX_EXECUTE state
     ((trap_ctrl.env_entered = '1') and (exe_engine.state = EX_BRANCHED))) and -- also allow triggering when entering a system trap (#887)
    (trap_ctrl.irq_buf(irq_db_step_c) = '1') else '0'; -- pending single-step halt


  -- CPU Sleep Mode Control -----------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  sleep_control: process(rstn_i, clk_aux_i) -- always-on clock domain
  begin
    if (rstn_i = '0') then
      sleep_mode <= '0';
    elsif rising_edge(clk_aux_i) then
      if (exe_engine.state = EX_SLEEP) and -- instruction execution has halted
         (frontend_i.halted = '1') and -- instruction fetch has halted
         (trap_ctrl.wakeup = '0') then -- no wake-up request
        sleep_mode <= '1';
      else
        sleep_mode <= '0';
      end if;
    end if;
  end process sleep_control;

  -- wake-up from / do not enter sleep mode: during debugging or on pending IRQ --
  trap_ctrl.wakeup <= or_reduce_f(trap_ctrl.irq_buf) or debug_ctrl.run or csr.dcsr_step;


  -- ****************************************************************************************************************************
  -- Control and Status Registers (CSRs)
  -- ****************************************************************************************************************************

  -- CSR Address Register -------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_addr_reg: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.addr <= (others => '0');
    elsif rising_edge(clk_i) then
      if (opcode = opcode_system_c) then -- update only for actual CSR operations to reduce switching activity on csr.addr net
        csr.addr <= exe_engine.ir(instr_imm12_msb_c downto instr_imm12_lsb_c);
      end if;
    end if;
  end process csr_addr_reg;


  -- CSR Write-Data ALU ---------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr.operand <= rf_rs1_i when (exe_engine.ir(instr_funct3_msb_c) = '0') else (x"000000" & "000" & exe_engine.ir(19 downto 15));

  -- tiny ALU to compute CSR write data --
  with exe_engine.ir(instr_funct3_msb_c-1 downto instr_funct3_lsb_c) select csr.wdata <=
    csr.rdata or       csr.operand  when "10", -- set
    csr.rdata and (not csr.operand) when "11", -- clear
    csr.operand                     when others; -- write


  -- CSR Write Access -----------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_write_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.we             <= '0';
      csr.prv_level      <= priv_mode_m_c;
      csr.mstatus_mie    <= '0';
      csr.mstatus_mpie   <= '0';
      csr.mstatus_mpp    <= priv_mode_m_c;
      csr.mstatus_mprv   <= '0';
      csr.mstatus_tw     <= '0';
      csr.mie_msi        <= '0';
      csr.mie_mei        <= '0';
      csr.mie_mti        <= '0';
      csr.mie_firq       <= (others => '0');
      csr.mtvec          <= (others => '0');
      csr.mscratch       <= (others => '0');
      csr.mepc           <= (others => '0');
      csr.mcause         <= (others => '0');
      csr.mtval          <= (others => '0');
      csr.mtinst         <= (others => '0');
      csr.mcounteren_cy  <= '0';
      csr.mcounteren_ir  <= '0';
      csr.mcountinhibit  <= (others => '0');
      csr.dcsr_ebreakm   <= '0';
      csr.dcsr_ebreaku   <= '0';
      csr.dcsr_step      <= '0';
      csr.dcsr_prv       <= '0';
      csr.dcsr_cause     <= (others => '0');
      csr.dpc            <= (others => '0');
      csr.dscratch0      <= (others => '0');
      csr.tdata1_execute <= '0';
      csr.tdata1_action  <= '0';
      csr.tdata1_dmode   <= '0';
      csr.tdata2         <= (others => '0');
    elsif rising_edge(clk_i) then

      -- write if not an illegal instruction --
      csr.we <= csr.we_nxt and (not trap_ctrl.exc_buf(exc_illegal_c));

      -- ********************************************************************************
      -- Software CSR access
      -- ********************************************************************************
      if (csr.we = '1') then

        -- --------------------------------------------------------------------
        -- machine trap setup
        -- --------------------------------------------------------------------

        -- machine status register --
        if (csr.addr = csr_mstatus_c) then
          csr.mstatus_mie  <= csr.wdata(3);
          csr.mstatus_mpie <= csr.wdata(7);
          if RISCV_ISA_U then
            csr.mstatus_mpp  <= csr.wdata(11) or csr.wdata(12); -- everything /= U will fall back to M
            csr.mstatus_mprv <= csr.wdata(17);
            csr.mstatus_tw   <= csr.wdata(21);
          end if;
        end if;

        -- machine interrupt enable register --
        if (csr.addr = csr_mie_c) then
          csr.mie_msi  <= csr.wdata(3);
          csr.mie_mti  <= csr.wdata(7);
          csr.mie_mei  <= csr.wdata(11);
          csr.mie_firq <= csr.wdata(31 downto 16);
        end if;

        -- machine trap-handler base address --
        if (csr.addr = csr_mtvec_c) then
          csr.mtvec <= csr.wdata(XLEN-1 downto 2) & '0' & csr.wdata(0); -- base + mode (vectored/direct)
        end if;

        -- machine counter access enable --
        if (csr.addr = csr_mcounteren_c) and RISCV_ISA_U and RISCV_ISA_Zicntr then
          csr.mcounteren_cy <= csr.wdata(0);
          csr.mcounteren_ir <= csr.wdata(2);
        end if;

        -- --------------------------------------------------------------------
        -- machine trap handling
        -- --------------------------------------------------------------------

        -- machine scratch register --
        if (csr.addr = csr_mscratch_c) then
          csr.mscratch <= csr.wdata;
        end if;

        -- machine exception program counter --
        if (csr.addr = csr_mepc_c) then
          csr.mepc <= csr.wdata(XLEN-1 downto 1) & '0';
          if not RISCV_ISA_C then -- RISC-V priv. spec.: MEPC[1] is masked when IALIGN = 32
            csr.mepc(1) <= '0';
          end if;
        end if;

        -- machine trap cause --
        if (csr.addr = csr_mcause_c) then
          csr.mcause <= csr.wdata(31) & csr.wdata(4 downto 0); -- type (exception/interrupt) & identifier
        end if;

        -- --------------------------------------------------------------------
        -- machine counter setup
        -- --------------------------------------------------------------------

        -- machine counter-inhibit register --
        if (csr.addr = csr_mcountinhibit_c) then
          if RISCV_ISA_Zicntr then
            csr.mcountinhibit(0) <= csr.wdata(0);
            csr.mcountinhibit(2) <= csr.wdata(2);
          end if;
          if RISCV_ISA_Zihpm then
            csr.mcountinhibit(15 downto 3) <= csr.wdata(15 downto 3);
          end if;
        end if;

        -- --------------------------------------------------------------------
        -- debug mode CSRs
        -- --------------------------------------------------------------------

        -- debug mode control and status register --
        if (csr.addr = csr_dcsr_c) and RISCV_ISA_Sdext then
          csr.dcsr_ebreakm <= csr.wdata(15);
          csr.dcsr_step    <= csr.wdata(2);
          if RISCV_ISA_U then
            csr.dcsr_ebreaku <= csr.wdata(12);
            csr.dcsr_prv     <= csr.wdata(1) or csr.wdata(0); -- everything /= U will fall back to M
          end if;
        end if;

        -- debug mode program counter --
        if (csr.addr = csr_dpc_c) and RISCV_ISA_Sdext then
          csr.dpc <= csr.wdata(XLEN-1 downto 1) & '0';
          if not RISCV_ISA_C then -- RISC-V priv. spec.: DPC[1] is masked when IALIGN = 32
            csr.dpc(1) <= '0';
          end if;
        end if;

        -- debug mode scratch register 0 --
        if (csr.addr = csr_dscratch0_c) and RISCV_ISA_Sdext then
          csr.dscratch0 <= csr.wdata;
        end if;

        -- --------------------------------------------------------------------
        -- trigger module CSRs
        -- --------------------------------------------------------------------

        -- match control --
        if (csr.addr = csr_tdata1_c) and RISCV_ISA_Sdtrig then
          if (csr.tdata1_dmode = '0') or (debug_ctrl.run = '1') then -- write access from debug-mode only?
            csr.tdata1_execute <= csr.wdata(2);
            csr.tdata1_action  <= csr.wdata(12);
          end if;
          if (debug_ctrl.run = '1') then -- writable from debug-mode only
            csr.tdata1_dmode <= csr.wdata(27);
          end if;
        end if;

        -- address compare --
        if (csr.addr = csr_tdata2_c) and RISCV_ISA_Sdtrig then
          if (csr.tdata1_dmode = '0') or (debug_ctrl.run = '1') then -- write access from debug-mode only?
            csr.tdata2 <= csr.wdata(XLEN-1 downto 1) & '0';
          end if;
        end if;

      -- ********************************************************************************
      -- Hardware CSR access: TRAP ENTER
      -- ********************************************************************************
      elsif (trap_ctrl.env_enter = '1') then

        -- NORMAL trap entry - no CSR update when in debug-mode! --
        if (not RISCV_ISA_Sdext) or ((trap_ctrl.cause(5) = '0') and (debug_ctrl.run = '0')) then
          csr.mcause <= trap_ctrl.cause(trap_ctrl.cause'left) & trap_ctrl.cause(4 downto 0); -- trap type & identifier
          csr.mepc   <= trap_ctrl.epc(XLEN-1 downto 1) & '0'; -- trap PC
          -- trap value (load/store trap address only, permitted by RISC-V priv. spec.) --
          if (trap_ctrl.cause(6) = '0') and (trap_ctrl.cause(2) = '1') then -- load/store misaligned/access faults [hacky!]
            csr.mtval <= lsu_mar_i; -- faulting data access address
          else -- everything else including all interrupts
            csr.mtval <= (others => '0');
          end if;
          -- trap instruction --
          if (trap_ctrl.cause(6) = '0') then -- exception
            csr.mtinst <= exe_engine.ir;
            if (exe_engine.ci = '1') and RISCV_ISA_C then
              csr.mtinst(1) <= '0'; -- RISC-V priv. spec: clear bit 1 if compressed instruction
            end if;
          else -- interrupt
            csr.mtinst <= (others => '0');
          end if;
          -- update privilege level and interrupt-enable stack --
          csr.prv_level    <= priv_mode_m_c; -- execute trap in machine mode
          csr.mstatus_mie  <= '0'; -- disable interrupts
          csr.mstatus_mpie <= csr.mstatus_mie; -- backup previous mie state
          csr.mstatus_mpp  <= csr.prv_level; -- backup previous privilege level
        end if;

        -- DEBUG trap entry - no CSR update when already in debug-mode! --
        if RISCV_ISA_Sdext and (trap_ctrl.cause(5) = '1') and (debug_ctrl.run = '0') then
          csr.dcsr_cause <= trap_ctrl.cause(2 downto 0); -- trap cause
          csr.dcsr_prv   <= csr.prv_level; -- current privilege level when debug mode was entered
          csr.dpc        <= trap_ctrl.epc(XLEN-1 downto 1) & '0'; -- trap PC
        end if;

      -- ********************************************************************************
      -- Hardware CSR access: TRAP EXIT
      -- ********************************************************************************
      elsif (trap_ctrl.env_exit = '1') then

        -- return from debug mode --
        if RISCV_ISA_Sdext and (debug_ctrl.run = '1') then
          if RISCV_ISA_U then
            csr.prv_level <= csr.dcsr_prv;
            if (csr.dcsr_prv /= priv_mode_m_c) then
              csr.mstatus_mprv <= '0'; -- clear if return to priv. level less than M
            end if;
          end if;
        -- return from normal trap --
        else
          if RISCV_ISA_U then
            csr.prv_level   <= csr.mstatus_mpp; -- restore previous privilege level
            csr.mstatus_mpp <= priv_mode_u_c; -- set to least-privileged level that is supported
            if (csr.mstatus_mpp /= priv_mode_m_c) then
              csr.mstatus_mprv <= '0'; -- clear if return to priv. level less than M
            end if;
          end if;
          csr.mstatus_mie  <= csr.mstatus_mpie; -- restore machine-mode IRQ enable flag
          csr.mstatus_mpie <= '1';
        end if;

      end if;

      -- ********************************************************************************
      -- Override - terminate unavailable registers and bits
      -- ********************************************************************************

      -- hardwired bits --
      csr.mcountinhibit(1) <= '0'; -- "time" not defined

      -- no base counters --
      if not RISCV_ISA_Zicntr then
        csr.mcountinhibit(2 downto 0) <= (others => '0');
      end if;

      -- no hardware performance monitors --
      if not RISCV_ISA_Zihpm then
        csr.mcountinhibit(15 downto 3) <= (others => '0');
      end if;

      -- no user-mode counters at all --
      if not RISCV_ISA_Zicntr then
        csr.mcounteren_cy <= '0';
        csr.mcounteren_ir <= '0';
      end if;

      -- no user mode --
      if not RISCV_ISA_U then
        csr.prv_level     <= priv_mode_m_c;
        csr.mstatus_mpp   <= priv_mode_m_c;
        csr.mstatus_mprv  <= '0';
        csr.mstatus_tw    <= '0';
        csr.dcsr_ebreaku  <= '0';
        csr.dcsr_prv      <= '0';
        csr.mcounteren_cy <= '0';
        csr.mcounteren_ir <= '0';
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

      -- no trigger module --
      if not RISCV_ISA_Sdtrig then
        csr.tdata1_execute <= '0';
        csr.tdata1_action  <= '0';
        csr.tdata1_dmode   <= '0';
        csr.tdata2         <= (others => '0');
      end if;

    end if;
  end process csr_write_access;

  -- effective privilege level is MACHINE when in debug mode --
  csr.prv_level_eff <= priv_mode_m_c when (debug_ctrl.run = '1') else csr.prv_level;


  -- CSR Read Access ------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr_read_access: process(rstn_i, clk_i)
  begin
    if (rstn_i = '0') then
      csr.re    <= '0';
      csr.rdata <= (others => '0');
    elsif rising_edge(clk_i) then
      csr.re    <= csr.re_nxt and (not trap_ctrl.exc_buf(exc_illegal_c)); -- read if not an illegal instruction
      csr.rdata <= (others => '0'); -- default; output all-zero if there is no explicit CSR read operation
      if (csr.re = '1') then
        case csr.addr is -- address is zero if there is no CSR operation

          -- --------------------------------------------------------------------
          -- floating-point unit
          -- --------------------------------------------------------------------
          when csr_fflags_c | csr_frm_c | csr_fcsr_c =>
            if RISCV_ISA_Zfinx then
              csr.rdata <= xcsr_rdata_i; -- implemented externally
            end if;

          -- --------------------------------------------------------------------
          -- custom functions unit
          -- --------------------------------------------------------------------
          when csr_cfureg0_c | csr_cfureg1_c | csr_cfureg2_c | csr_cfureg3_c =>
            if RISCV_ISA_Zxcfu then
              csr.rdata <= xcsr_rdata_i; -- implemented externally
            end if;

          -- --------------------------------------------------------------------
          -- inter-core communication
          -- --------------------------------------------------------------------
          when csr_mxiccsreg_c | csr_mxiccdata_c =>
            csr.rdata <= xcsr_rdata_i; -- implemented externally

          -- --------------------------------------------------------------------
          -- machine trap setup
          -- --------------------------------------------------------------------
          when csr_mstatus_c => -- machine status register - low word
            csr.rdata(3)  <= csr.mstatus_mie;
            csr.rdata(7)  <= csr.mstatus_mpie;
            csr.rdata(12 downto 11) <= (others => csr.mstatus_mpp);
            csr.rdata(17) <= csr.mstatus_mprv;
            csr.rdata(21) <= csr.mstatus_tw and bool_to_ulogic_f(RISCV_ISA_U);

--        when csr_mstatush_c => csr.rdata <= (others => '0'); -- machine status register, high word - hardwired to zero

          when csr_misa_c => -- ISA and extensions
            csr.rdata(0)  <= bool_to_ulogic_f(RISCV_ISA_A);
            csr.rdata(1)  <= bool_to_ulogic_f(RISCV_ISA_B);
            csr.rdata(2)  <= bool_to_ulogic_f(RISCV_ISA_C);
            csr.rdata(4)  <= bool_to_ulogic_f(RISCV_ISA_E);
            csr.rdata(8)  <= bool_to_ulogic_f(not RISCV_ISA_E); -- I = not E
            csr.rdata(12) <= bool_to_ulogic_f(RISCV_ISA_M);
            csr.rdata(20) <= bool_to_ulogic_f(RISCV_ISA_U);
            csr.rdata(23) <= '1'; -- X CPU extension (non-standard / NEORV32-specific)
            csr.rdata(31 downto 30) <= "01"; -- MXL = 32

          when csr_mie_c => -- machine interrupt-enable register
            csr.rdata(3)  <= csr.mie_msi;
            csr.rdata(7)  <= csr.mie_mti;
            csr.rdata(11) <= csr.mie_mei;
            csr.rdata(31 downto 16) <= csr.mie_firq;

          when csr_mtvec_c => -- machine trap-handler base address
            csr.rdata <= csr.mtvec;

          when csr_mcounteren_c => -- machine counter enable register
            if RISCV_ISA_U and RISCV_ISA_Zicntr then
              csr.rdata(0) <= csr.mcounteren_cy;
              csr.rdata(2) <= csr.mcounteren_ir;
            end if;

          -- --------------------------------------------------------------------
          -- machine configuration
          -- --------------------------------------------------------------------
--        when csr_menvcfg_c  => csr.rdata <= (others => '0'); -- hardwired to zero
--        when csr_menvcfgh_c => csr.rdata <= (others => '0'); -- hardwired to zero

          -- --------------------------------------------------------------------
          -- machine trap handling
          -- --------------------------------------------------------------------
          when csr_mscratch_c => -- machine scratch register
            csr.rdata <= csr.mscratch;

          when csr_mepc_c => -- machine exception program counter
            csr.rdata <= csr.mepc(XLEN-1 downto 1) & '0';

          when csr_mcause_c => -- machine trap cause
            csr.rdata(31)         <= csr.mcause(5);
            csr.rdata(4 downto 0) <= csr.mcause(4 downto 0);

          when csr_mtval_c => -- machine trap value
            csr.rdata <= csr.mtval;

          when csr_mip_c => -- machine interrupt pending
            csr.rdata(3)            <= trap_ctrl.irq_pnd(irq_msi_irq_c);
            csr.rdata(7)            <= trap_ctrl.irq_pnd(irq_mti_irq_c);
            csr.rdata(11)           <= trap_ctrl.irq_pnd(irq_mei_irq_c);
            csr.rdata(31 downto 16) <= trap_ctrl.irq_pnd(irq_firq_15_c downto irq_firq_0_c);

          when csr_mtinst_c => -- machine trap instruction
            csr.rdata <= csr.mtinst;

          -- --------------------------------------------------------------------
          -- physical memory protection
          -- --------------------------------------------------------------------
          when csr_pmpcfg0_c   | csr_pmpcfg1_c   | csr_pmpcfg2_c   | csr_pmpcfg3_c   |
               csr_pmpaddr0_c  | csr_pmpaddr1_c  | csr_pmpaddr2_c  | csr_pmpaddr3_c  |
               csr_pmpaddr4_c  | csr_pmpaddr5_c  | csr_pmpaddr6_c  | csr_pmpaddr7_c  |
               csr_pmpaddr8_c  | csr_pmpaddr9_c  | csr_pmpaddr10_c | csr_pmpaddr11_c |
               csr_pmpaddr12_c | csr_pmpaddr13_c | csr_pmpaddr14_c | csr_pmpaddr15_c =>
            if RISCV_ISA_Smpmp then
              csr.rdata <= xcsr_rdata_i; -- implemented externally
            end if;

          -- --------------------------------------------------------------------
          -- machine counter setup
          -- --------------------------------------------------------------------
          when csr_mcountinhibit_c => -- machine counter-inhibit register
            if RISCV_ISA_Zicntr then
              csr.rdata(0) <= csr.mcountinhibit(0); -- [m]cycle[h]
              csr.rdata(2) <= csr.mcountinhibit(2); -- [m]instret[h]
            end if;
            if RISCV_ISA_Zihpm then
              csr.rdata(15 downto 3) <= csr.mcountinhibit(15 downto 3); -- [m]hpmcounter*[h]
            end if;

          -- HPM event configuration --
          when csr_mhpmevent3_c  | csr_mhpmevent4_c  | csr_mhpmevent5_c  | csr_mhpmevent6_c  |
               csr_mhpmevent7_c  | csr_mhpmevent8_c  | csr_mhpmevent9_c  | csr_mhpmevent10_c |
               csr_mhpmevent11_c | csr_mhpmevent12_c | csr_mhpmevent13_c | csr_mhpmevent14_c |
               csr_mhpmevent15_c =>
            if RISCV_ISA_Zihpm then
              csr.rdata <= xcsr_rdata_i; -- implemented externally
            end if;

          -- --------------------------------------------------------------------
          -- counters and timers
          -- --------------------------------------------------------------------
          -- base counters --
          when csr_cycle_c   | csr_cycleh_c   | csr_mcycle_c   | csr_mcycleh_c   |
               csr_time_c    | csr_timeh_c    | csr_mtime_c    | csr_mtimeh_c    |
               csr_instret_c | csr_instreth_c | csr_minstret_c | csr_minstreth_c =>
            if RISCV_ISA_Zicntr then
              csr.rdata <= xcsr_rdata_i; -- implemented externally
            end if;

          -- hardware performance monitors --
          when csr_hpmcounter3_c  | csr_hpmcounter3h_c  | csr_mhpmcounter3_c  | csr_mhpmcounter3h_c  |
               csr_hpmcounter4_c  | csr_hpmcounter4h_c  | csr_mhpmcounter4_c  | csr_mhpmcounter4h_c  |
               csr_hpmcounter5_c  | csr_hpmcounter5h_c  | csr_mhpmcounter5_c  | csr_mhpmcounter5h_c  |
               csr_hpmcounter6_c  | csr_hpmcounter6h_c  | csr_mhpmcounter6_c  | csr_mhpmcounter6h_c  |
               csr_hpmcounter7_c  | csr_hpmcounter7h_c  | csr_mhpmcounter7_c  | csr_mhpmcounter7h_c  |
               csr_hpmcounter8_c  | csr_hpmcounter8h_c  | csr_mhpmcounter8_c  | csr_mhpmcounter8h_c  |
               csr_hpmcounter9_c  | csr_hpmcounter9h_c  | csr_mhpmcounter9_c  | csr_mhpmcounter9h_c  |
               csr_hpmcounter10_c | csr_hpmcounter10h_c | csr_mhpmcounter10_c | csr_mhpmcounter10h_c |
               csr_hpmcounter11_c | csr_hpmcounter11h_c | csr_mhpmcounter11_c | csr_mhpmcounter11h_c |
               csr_hpmcounter12_c | csr_hpmcounter12h_c | csr_mhpmcounter12_c | csr_mhpmcounter12h_c |
               csr_hpmcounter13_c | csr_hpmcounter13h_c | csr_mhpmcounter13_c | csr_mhpmcounter13h_c |
               csr_hpmcounter14_c | csr_hpmcounter14h_c | csr_mhpmcounter14_c | csr_mhpmcounter14h_c |
               csr_hpmcounter15_c | csr_hpmcounter15h_c | csr_mhpmcounter15_c | csr_mhpmcounter15h_c =>
            if RISCV_ISA_Zihpm then
              csr.rdata <= xcsr_rdata_i; -- implemented externally
            end if;

          -- --------------------------------------------------------------------
          -- machine information registers
          -- --------------------------------------------------------------------
--        when csr_mvendorid_c  => csr.rdata <= (others => '0'); -- vendor's JEDEC ID
          when csr_marchid_c    => csr.rdata(4 downto 0) <= "10011"; -- architecture ID - official RISC-V open-source arch ID
          when csr_mimpid_c     => csr.rdata <= hw_version_c; -- implementation ID -- NEORV32 hardware version
          when csr_mhartid_c    => csr.rdata(9 downto 0) <= std_ulogic_vector(to_unsigned(HART_ID, 10)); -- hardware thread ID
--        when csr_mconfigptr_c => csr.rdata <= (others => '0'); -- machine configuration pointer register - hardwired to zero

          -- --------------------------------------------------------------------
          -- debug-mode CSRs
          -- --------------------------------------------------------------------
          when csr_dcsr_c      => if RISCV_ISA_Sdext then csr.rdata <= csr.dcsr_rd;   end if; -- debug mode control and status
          when csr_dpc_c       => if RISCV_ISA_Sdext then csr.rdata <= csr.dpc;       end if; -- debug mode program counter
          when csr_dscratch0_c => if RISCV_ISA_Sdext then csr.rdata <= csr.dscratch0; end if; -- debug mode scratch register 0

          -- --------------------------------------------------------------------
          -- trigger module CSRs
          -- --------------------------------------------------------------------
--        when csr_tselect_c => if RISCV_ISA_Sdtrig then csr.rdata <= (others => '0'); end if; -- hardwired to zero = only 1 trigger available
          when csr_tdata1_c  => if RISCV_ISA_Sdtrig then csr.rdata <= csr.tdata1_rd;   end if; -- match control
          when csr_tdata2_c  => if RISCV_ISA_Sdtrig then csr.rdata <= csr.tdata2;      end if; -- address-compare
          when csr_tinfo_c   => if RISCV_ISA_Sdtrig then csr.rdata <= x"01000006";     end if; -- trigger information (Sdtrig v1.0; mcontrol6-type only)

          -- --------------------------------------------------------------------
          -- NEORV32-specific (RISC-V "custom") read-only machine-mode CSRs
          -- --------------------------------------------------------------------
          -- machine extended ISA extensions information --
          when csr_mxisa_c =>
            -- extended ISA (sub-)extensions --
            csr.rdata(0)  <= '1';                                   -- Zicsr: CSR access (always enabled)
            csr.rdata(1)  <= '1';                                   -- Zifencei: instruction stream sync. (always enabled)
            csr.rdata(2)  <= bool_to_ulogic_f(RISCV_ISA_Zmmul);     -- Zmmul: mul/div
            csr.rdata(3)  <= bool_to_ulogic_f(RISCV_ISA_Zxcfu);     -- Zxcfu: custom RISC-V instructions
            csr.rdata(4)  <= bool_to_ulogic_f(RISCV_ISA_Zkt);       -- Zkt: data independent execution latency
            csr.rdata(5)  <= bool_to_ulogic_f(RISCV_ISA_Zfinx);     -- Zfinx: FPU using x registers
            csr.rdata(6)  <= bool_to_ulogic_f(RISCV_ISA_Zicond);    -- Zicond: integer conditional operations
            csr.rdata(7)  <= bool_to_ulogic_f(RISCV_ISA_Zicntr);    -- Zicntr: base counters
            csr.rdata(8)  <= bool_to_ulogic_f(RISCV_ISA_Smpmp);     -- Smpmp: physical memory protection
            csr.rdata(9)  <= bool_to_ulogic_f(RISCV_ISA_Zihpm);     -- Zihpm: hardware performance monitors
            csr.rdata(10) <= bool_to_ulogic_f(RISCV_ISA_Sdext);     -- Sdext: RISC-V external debug
            csr.rdata(11) <= bool_to_ulogic_f(RISCV_ISA_Sdtrig);    -- Sdtrig: trigger module
            csr.rdata(12) <= bool_to_ulogic_f(RISCV_ISA_Zbkx);      -- Zbkx: cryptography crossbar permutation
            csr.rdata(13) <= bool_to_ulogic_f(RISCV_ISA_Zknd);      -- Zknd: cryptography NIST AES decryption
            csr.rdata(14) <= bool_to_ulogic_f(RISCV_ISA_Zkne);      -- Zkne: cryptography NIST AES encryption
            csr.rdata(15) <= bool_to_ulogic_f(RISCV_ISA_Zknh);      -- Zknh: cryptography NIST hash functions
            csr.rdata(16) <= bool_to_ulogic_f(RISCV_ISA_Zbkb);      -- Zbkb: bit manipulation instructions for cryptography
            csr.rdata(17) <= bool_to_ulogic_f(RISCV_ISA_Zbkc);      -- Zbkc: carry-less multiplication for cryptography
            csr.rdata(18) <= bool_to_ulogic_f(RISCV_ISA_Zkn);       -- Zkn: NIST algorithm suite
            csr.rdata(19) <= bool_to_ulogic_f(RISCV_ISA_Zksh);      -- Zksh: ShangMi hash functions
            csr.rdata(20) <= bool_to_ulogic_f(RISCV_ISA_Zksed);     -- Zksed: ShangMi block ciphers
            csr.rdata(21) <= bool_to_ulogic_f(RISCV_ISA_Zks);       -- Zks: ShangMi algorithm suite
            csr.rdata(22) <= bool_to_ulogic_f(RISCV_ISA_Zba);       -- Zba: shifted-add bit-manipulation
            csr.rdata(23) <= bool_to_ulogic_f(RISCV_ISA_Zbb);       -- Zbb: basic bit-manipulation
            csr.rdata(24) <= bool_to_ulogic_f(RISCV_ISA_Zbs);       -- Zbs: single-bit bit-manipulation
            csr.rdata(25) <= bool_to_ulogic_f(RISCV_ISA_Zaamo);     -- Zaamo: atomic memory operations
            csr.rdata(26) <= bool_to_ulogic_f(RISCV_ISA_Zalrsc);    -- Zalrsc: reservation-set operations
            -- tuning options --
            csr.rdata(27) <= bool_to_ulogic_f(CPU_CLOCK_GATING_EN); -- enable clock gating when in sleep mode
            csr.rdata(28) <= bool_to_ulogic_f(CPU_RF_HW_RST_EN);    -- full hardware reset of register file
            csr.rdata(29) <= bool_to_ulogic_f(CPU_FAST_MUL_EN);     -- DSP-based multiplication (M extensions only)
            csr.rdata(30) <= bool_to_ulogic_f(CPU_FAST_SHIFT_EN);   -- parallel logic for shifts (barrel shifters)
            -- misc --
            csr.rdata(31) <= bool_to_ulogic_f(is_simulation_c);     -- is this a simulation?

          -- --------------------------------------------------------------------
          -- undefined/unavailable
          -- --------------------------------------------------------------------
          when others => NULL; -- use default: read as zero

        end case;
      end if;
    end if;
  end process csr_read_access;

  -- CSR read data output (to register file mux) --
  csr_rdata_o <= csr.rdata;


  -- ****************************************************************************************************************************
  -- CPU Counter Increment Control (Trigger Events)
  -- ****************************************************************************************************************************

  -- RISC-V-compliant counter events --
  cnt_event(cnt_event_cy_c) <= '1' when (sleep_mode = '0') else '0'; -- active cycle
  cnt_event(cnt_event_tm_c) <= '0'; -- time: not available
  cnt_event(cnt_event_ir_c) <= '1' when (exe_engine.state = EX_EXECUTE) else '0'; -- retired (=executed) instruction

  -- NEORV32-specific counter events --
  cnt_event(cnt_event_compr_c)    <= '1' when (exe_engine.state = EX_EXECUTE)  and (exe_engine.ci = '1')        else '0'; -- executed compressed instruction
  cnt_event(cnt_event_wait_dis_c) <= '1' when (exe_engine.state = EX_DISPATCH) and (frontend_i.valid = '0')     else '0'; -- instruction dispatch wait cycle
  cnt_event(cnt_event_wait_alu_c) <= '1' when (exe_engine.state = EX_ALU_WAIT)                                  else '0'; -- multi-cycle ALU wait cycle
  cnt_event(cnt_event_branch_c)   <= '1' when (exe_engine.state = EX_BRANCH)                                    else '0'; -- executed branch instruction
  cnt_event(cnt_event_branched_c) <= '1' when (exe_engine.state = EX_BRANCHED)                                  else '0'; -- control flow transfer
  cnt_event(cnt_event_load_c)     <= '1' when (ctrl.lsu_req = '1') and ((opcode(5) = '0') or (opcode(2) = '1')) else '0'; -- executed load operation
  cnt_event(cnt_event_store_c)    <= '1' when (ctrl.lsu_req = '1') and ((opcode(5) = '1') or (opcode(2) = '1')) else '0'; -- executed store operation
  cnt_event(cnt_event_wait_lsu_c) <= '1' when (ctrl.lsu_req = '0') and (exe_engine.state = EX_MEM_RSP)          else '0'; -- load/store memory wait cycle
  cnt_event(cnt_event_trap_c)     <= '1' when (trap_ctrl.env_enter = '1')                                       else '0'; -- entered trap


  -- ****************************************************************************************************************************
  -- CPU Debug Mode
  -- ****************************************************************************************************************************

  -- Debug Control --------------------------------------------------------------------------
  -- -------------------------------------------------------------------------------------------
  debug_mode_enable:
  if RISCV_ISA_Sdext generate

    debug_control: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        debug_ctrl.run <= '0';
      elsif rising_edge(clk_i) then
        if (debug_ctrl.run = '0') then -- debug mode OFFLINE
          if (trap_ctrl.env_enter = '1') and (trap_ctrl.cause(5) = '1') then -- waiting for entry event
            debug_ctrl.run <= '1';
          end if;
        else -- debug mode ONLINE
          if (trap_ctrl.env_exit = '1') then -- waiting for exit event
            debug_ctrl.run <= '0';
          end if;
        end if;
      end if;
    end process debug_control;

    -- debug mode entry triggers --
    debug_ctrl.trig_hw    <= trap_ctrl.hwtrig and (not debug_ctrl.run) and csr.tdata1_action and csr.tdata1_dmode; -- enter debug mode by HW trigger module
    debug_ctrl.trig_break <= trap_ctrl.ebreak and (debug_ctrl.run or -- re-enter debug mode
                             ((    csr.prv_level) and csr.dcsr_ebreakm) or -- enabled goto-debug-mode in machine mode on "ebreak"
                             ((not csr.prv_level) and csr.dcsr_ebreaku));  -- enabled goto-debug-mode in user mode on "ebreak"
    debug_ctrl.trig_halt  <= irq_dbg_i     and (not debug_ctrl.run); -- external halt request (if not halted already)
    debug_ctrl.trig_step  <= csr.dcsr_step and (not debug_ctrl.run); -- single-step mode (trigger when NOT CURRENTLY in debug mode)

  end generate;

  -- Sdext ISA extension not enabled --
  debug_mode_disable:
  if not RISCV_ISA_Sdext generate
    debug_ctrl.run        <= '0';
    debug_ctrl.trig_hw    <= '0';
    debug_ctrl.trig_break <= '0';
    debug_ctrl.trig_halt  <= '0';
    debug_ctrl.trig_step  <= '0';
  end generate;


  -- Debug Control and Status Register (dcsr) - Read-Back -----------------------------------
  -- -------------------------------------------------------------------------------------------
  csr.dcsr_rd(31 downto 28) <= "0100"; -- xdebugver: external debug support compatible to spec. version 1.0
  csr.dcsr_rd(27 downto 16) <= (others => '0'); -- reserved
  csr.dcsr_rd(15)           <= csr.dcsr_ebreakm; -- ebreakm: what happens on ebreak in m-mode? (normal trap OR debug-enter)
  csr.dcsr_rd(14)           <= '0'; -- reserved
  csr.dcsr_rd(13)           <= '0'; -- ebreaks: supervisor mode not implemented
  csr.dcsr_rd(12)           <= csr.dcsr_ebreaku when RISCV_ISA_U else '0'; -- ebreaku: what happens on ebreak in u-mode? (normal trap OR debug-enter)
  csr.dcsr_rd(11)           <= '0'; -- stepie: interrupts are disabled during single-stepping
  csr.dcsr_rd(10)           <= '1'; -- stopcount: standard counters and HPMs are stopped when in debug mode
  csr.dcsr_rd(9)            <= '0'; -- stoptime: timers increment as usual
  csr.dcsr_rd(8 downto 6)   <= csr.dcsr_cause; -- debug mode entry cause
  csr.dcsr_rd(5)            <= '0'; -- reserved
  csr.dcsr_rd(4)            <= '1'; -- mprven: mstatus.mprv is also evaluated in debug mode
  csr.dcsr_rd(3)            <= '0'; -- nmip: no pending non-maskable interrupt
  csr.dcsr_rd(2)            <= csr.dcsr_step; -- step: single-step mode
  csr.dcsr_rd(1 downto 0)   <= (others => csr.dcsr_prv); -- prv: privilege level when debug mode was entered


  -- ****************************************************************************************************************************
  -- Hardware Trigger Module
  -- ****************************************************************************************************************************

  trigger_module_enable:
  if RISCV_ISA_Sdtrig generate

    -- trigger on instruction address match (trigger right BEFORE execution) --
    hwtrig_match <= '1' when (csr.tdata1_execute = '1') and -- trigger enabled to match on instruction address
                             (hwtrig_fired = '0') and -- trigger has not fired yet
                             (csr.tdata2(XLEN-1 downto 1) = exe_engine.pc2(XLEN-1 downto 1)) -- address match
                             else '0';

    -- status flag - set when trigger has fired --
    hwtrig_exception: process(rstn_i, clk_i)
    begin
      if (rstn_i = '0') then
        hwtrig_fired <= '0';
      elsif rising_edge(clk_i) then
        if (hwtrig_fired = '0') then
          hwtrig_fired <= hwtrig_match and trap_ctrl.exc_buf(exc_ebreak_c); -- trigger has fired and breakpoint exception is pending
        elsif (csr.we = '1') and (csr.addr = csr_tdata1_c) and (csr.wdata(22) = '0') then -- tdata1 write access
          hwtrig_fired <= '0';
        end if;
      end if;
    end process hwtrig_exception;

  end generate;

  -- Sdtrig ISA extension not enabled --
  trigger_module_disable:
  if not RISCV_ISA_Sdtrig generate
    hwtrig_match <= '0';
    hwtrig_fired <= '0';
  end generate;


  -- Match Control CSR (mcontrol6 @ tdata1) - Read-Back -------------------------------------
  -- -------------------------------------------------------------------------------------------
  csr.tdata1_rd(31 downto 28) <= x"6"; -- type: address match trigger (mcontrol6)
  csr.tdata1_rd(27)           <= csr.tdata1_dmode; -- dmode: set to ignore machine-mode write access to tdata* CSRs
  csr.tdata1_rd(26)           <= '0'; -- uncertain: trigger satisfies the configured conditions
  csr.tdata1_rd(25)           <= '0'; -- hit1: hardwired to zero
  csr.tdata1_rd(24)           <= '0'; -- vs: VS-mode not implemented
  csr.tdata1_rd(23)           <= '0'; -- vu: VU-mode not implemented
  csr.tdata1_rd(22)           <= hwtrig_fired; -- hit0: set when trigger has fired
  csr.tdata1_rd(21)           <= '0'; -- select: only address matching is supported
  csr.tdata1_rd(20 downto 19) <= "00"; -- reserved
  csr.tdata1_rd(18 downto 16) <= "000"; -- size: match accesses of any size
  csr.tdata1_rd(15 downto 12) <= "000" & csr.tdata1_action; -- action = 1: enter debug mode on trigger, action = 0: ebreak exception on trigger
  csr.tdata1_rd(11)           <= '0'; -- chain: chaining not supported - there is only one trigger
  csr.tdata1_rd(10 downto 7)  <= "0000"; -- match: equal-match only
  csr.tdata1_rd(6)            <= '1'; -- m: trigger always enabled when in machine-mode
  csr.tdata1_rd(5)            <= '0'; -- uncertainen: hardwired to zero
  csr.tdata1_rd(4)            <= '0'; -- s: supervisor-mode not supported
  csr.tdata1_rd(3)            <= bool_to_ulogic_f(RISCV_ISA_U); -- u: trigger always enabled when in user-mode (if implemented)
  csr.tdata1_rd(2)            <= csr.tdata1_execute; -- execute: enable trigger on instruction match
  csr.tdata1_rd(1)            <= '0'; -- store: store address or data matching not supported
  csr.tdata1_rd(0)            <= '0'; -- load: load address or data matching not supported


end neorv32_cpu_control_rtl;
