`ifdef LM32_CONFIG_V
`else
`define LM32_CONFIG_V

//
// EXCEPTION VECTORS BASE ADDRESS
//

// Base address for exception vectors
`define CFG_EBA_RESET 32'h00000000

// Base address for the debug exception vectors. If the DC_RE flag is
// set or the at_debug signal is asserted (see CFG_ALTERNATE_EBA) this
// will also be used for normal exception vectors.
`define CFG_DEBA_RESET 32'h10000000

// Enable exception vector remapping by external signal
//`define CFG_ALTERNATE_EBA


//
// ALU OPTIONS
//

// Enable sign-extension instructions
`define CFG_SIGN_EXTEND_ENABLED

// Shifter
// You may either enable the piplined or the multi-cycle barrel
// shifter. The multi-cycle shifter will stall the pipeline until
// the result is available after 32 cycles.
// If both options are disabled, only "right shift by one bit" is
// available.
//`define CFG_MC_BARREL_SHIFT_ENABLED
`define CFG_PL_BARREL_SHIFT_ENABLED

// Multiplier
// The multiplier is available either in a multi-cycle version or
// in a pipelined one. The multi-cycle multiplier stalls the pipe
// for 32 cycles. If both options are disabled, multiply operations
// are not supported.
//`define CFG_MC_MULTIPLY_ENABLED
`define CFG_PL_MULTIPLY_ENABLED

// Enable the multi-cycle divider. Stalls the pipe until the result
// is ready after 32 cycles. If disabled, the divide operation is not
// supported.
`define CFG_MC_DIVIDE_ENABLED


//
// INTERRUPTS
//

// Enable support for 32 hardware interrupts
`define CFG_INTERRUPTS_ENABLED

// Enable level-sensitive interrupts. The interrupt line status is
// reflected in the IP register, which is then read-only.
`define CFG_LEVEL_SENSITIVE_INTERRUPTS


//
// USER INSTRUCTION
//

// Enable support for the user opcode.
//`define CFG_USER_ENABLED


//
// MEMORY MANAGEMENT UNIT
//

// Enable instruction and data translation lookaside buffers and
// restricted user mode.
//`define CFG_MMU_ENABLED


//
// CACHE
//

// Instruction cache
`define CFG_ICACHE_ENABLED
`define CFG_ICACHE_ASSOCIATIVITY   1
`define CFG_ICACHE_SETS            256
`define CFG_ICACHE_BYTES_PER_LINE  16
`define CFG_ICACHE_BASE_ADDRESS    32'h00000000
`define CFG_ICACHE_LIMIT           32'h7fffffff

// Data cache
`define CFG_DCACHE_ENABLED
`define CFG_DCACHE_ASSOCIATIVITY   1
`define CFG_DCACHE_SETS            256
`define CFG_DCACHE_BYTES_PER_LINE  16
`define CFG_DCACHE_BASE_ADDRESS    32'h00000000
`define CFG_DCACHE_LIMIT           32'h7fffffff


//
// DEBUG OPTION
//

// Globally enable debugging
//`define CFG_DEBUG_ENABLED

// Enable the hardware JTAG debugging interface.
// Note: to use this, there must be a special JTAG module for your
//       device. At the moment, there is only support for the
//       Spartan-6.
//`define CFG_JTAG_ENABLED

// JTAG UART is a communication channel which uses JTAG to transmit
// and receive bytes to and from the host computer.
//`define CFG_JTAG_UART_ENABLED

// Enable reading and writing to the memory and writing CSRs using
// the JTAG interface.
//`define CFG_HW_DEBUG_ENABLED

// Number of hardware watchpoints, max. 4
//`define CFG_WATCHPOINTS 32'h4

// Enable hardware breakpoints
//`define CFG_ROM_DEBUG_ENABLED

// Number of hardware breakpoints, max. 4
//`define CFG_BREAKPOINTS 32'h4

// Put the processor into debug mode by an external signal. That is,
// raise a breakpoint exception. This is useful if you have a debug
// monitor and a serial line and you want to trap into the monitor on a
// BREAK symbol on the serial line.
//`define CFG_EXTERNAL_BREAK_ENABLED


//
// REGISTER FILE
//

// The following option explicitly infers block RAM for the register
// file. There is extra logic to avoid parallel writes and reads.
// Normally, if your synthesizer is smart enough, this should not be
// necessary because it will automatically infer block RAM for you.
//`define CFG_EBR_POSEDGE_REGISTER_FILE

// Explicitly infers block RAM, too. But it uses two different clocks,
// one being shifted by 180deg, for the read and write port. Therefore,
// no additional logic to avoid the parallel write/reads.
//`define CFG_EBR_NEGEDGE_REGISTER_FILE


//
// MISCELLANEOUS
//

// Exceptions on wishbone bus errors
//`define CFG_BUS_ERRORS_ENABLED

// Enable the cycle counter
`define CFG_CYCLE_COUNTER_ENABLED

// Embedded instruction ROM using on-chip block RAM
//`define CFG_IROM_ENABLED
//`define CFG_IROM_INIT_FILE     "NONE"
//`define CFG_IROM_BASE_ADDRESS  32'h10000000
//`define CFG_IROM_LIMIT         32'h10000fff

// Embedded data RAM using on-chip block RAM
//`define CFG_DRAM_ENABLED
//`define CFG_DRAM_INIT_FILE     "NONE"
//`define CFG_DRAM_BASE_ADDRESS  32'h20000000
//`define CFG_DRAM_LIMIT         32'h20000fff

// Trace unit
//`define CFG_TRACE_ENABLED

// Resolve unconditional branches already in the X stage (UNTESTED!)
//`define CFG_FAST_UNCONDITIONAL_BRANCH

// log2 function
// If your simulator/synthesizer does not support the $clog2 system
// function you can use a constant function instead.

function integer clog2;
  input integer value;
  begin
    value = value - 1;
    for (clog2 = 0; value > 0; clog2 = clog2 + 1)
      value = value >> 1;
  end
endfunction

`define CLOG2 clog2

//`define CLOG2 $clog2

`endif
