/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Vdut.h"
#include "Vdut.h"
#include "verilated.h"
#include "verilated_vcd_c.h"
#include <verilated.h>

VerilatedVcdC* tfp;

extern "C" void litex_sim_eval(void *vdut)
{
  Vdut *dut = (Vdut*)vdut;
  dut->eval();
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
  Verilated::commandArgs(argc, argv);
}

extern "C" void litex_sim_init_tracer(void *vdut)
{
  Vdut *dut = (Vdut*)vdut;
  Verilated::traceEverOn(true);
  tfp = new VerilatedVcdC;
  dut->trace(tfp, 99);
  tfp->open("dut.vcd");
}

extern "C" void litex_sim_tracer_dump()
{
  static unsigned int ticks=0;
  tfp->dump(ticks++);
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
