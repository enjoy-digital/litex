/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Vdut.h"
#include "verilated.h"
#ifdef TRACE_FST
#include "verilated_fst_c.h"
#else
#include "verilated_vcd_c.h"
#endif

#ifdef TRACE_FST
VerilatedFstC* tfp;
#else
VerilatedVcdC* tfp;
#endif
long tfp_start;
long tfp_end;

extern "C" void litex_sim_eval(void *vdut)
{
  Vdut *dut = (Vdut*)vdut;
  dut->eval();
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
  Verilated::commandArgs(argc, argv);
}

extern "C" void litex_sim_init_tracer(void *vdut, long start, long end)
{
  Vdut *dut = (Vdut*)vdut;
  tfp_start = start;
  tfp_end = end;
  Verilated::traceEverOn(true);
#ifdef TRACE_FST
      tfp = new VerilatedFstC;
      dut->trace(tfp, 99);
      tfp->open("dut.fst");
#else
      tfp = new VerilatedVcdC;
      dut->trace(tfp, 99);
      tfp->open("dut.vcd");
#endif
}

extern "C" void litex_sim_tracer_dump()
{
  static unsigned int ticks=0;
  int dump = 1;
  if (ticks < tfp_start)
      dump = 0;
  if (tfp_end != -1)
      if (ticks > tfp_end)
          dump = 0;
  if (dump)
      tfp->dump(ticks);
  ticks++;
}

extern "C" int litex_sim_got_finish()
{
  return Verilated::gotFinish();
}

#if VM_COVERAGE
extern "C" void litex_sim_coverage_dump()
{
  VerilatedCov::write("dut.cov");
}
#endif

vluint64_t main_time = 0;
double sc_time_stamp()
{
  return main_time;
}
