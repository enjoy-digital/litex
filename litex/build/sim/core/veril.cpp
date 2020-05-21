/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "Vdut.h"
#include "verilated.h"
#if VM_TRACE
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
vluint64_t tfp_start;
vluint64_t tfp_end;
#endif
vluint64_t main_time;

extern "C" void litex_sim_eval(void *vdut)
{
  Vdut *dut = (Vdut*)vdut;
  dut->eval();
}

extern "C" void litex_sim_increment_time()
{
  main_time += 125; // ps
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
  Verilated::commandArgs(argc, argv);
}

extern "C" void litex_sim_init_tracer(void *vdut, long start, long end)
{
#if VM_TRACE
  Vdut *dut = (Vdut*)vdut;
  tfp_start = start;
  tfp_end = end >= 0 ? end : UINT64_MAX;
  Verilated::traceEverOn(true);
#ifdef TRACE_FST
      tfp = new VerilatedFstC;
      tfp->set_time_unit("1ps");
      tfp->set_time_resolution("1ps");
      dut->trace(tfp, 99);
      tfp->open("dut.fst");
#else
      tfp = new VerilatedVcdC;
      tfp->set_time_unit("1ps");
      tfp->set_time_resolution("1ps");
      dut->trace(tfp, 99);
      tfp->open("dut.vcd");
#endif
#endif
}

extern "C" void litex_sim_tracer_dump()
{
#if VM_TRACE
  if (tfp_start <= main_time && main_time <= tfp_end)
    tfp->dump(main_time);
#endif
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

double sc_time_stamp()
{
  return main_time;
}
