/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "Vsim.h"
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
uint64_t tfp_start;
uint64_t tfp_end;
uint64_t main_time = 0;
uint64_t save_time = -1;
uint64_t load_time = 0;
Vsim *g_sim = nullptr;


#ifdef SAVABLE
static void litex_sim_save_state(void *vsim,const char* filename);
static void litex_sim_restore_state(void *vsim,const char* filename);
#endif


extern "C" void litex_sim_eval(void *vsim, uint64_t time_ps)
{
  #ifdef SAVABLE
  if (main_time == load_time && load_time > 0) {
    printf("MDEBUG: Restoring state at time %ld\n", load_time);
    litex_sim_restore_state(vsim,"sim_default.vlt");
  }
  if (main_time == save_time) {
    printf("MDEBUG: Saving state at time %ld\n", save_time);
    litex_sim_save_state(vsim,"sim_default.vlt");
  }
  #endif
  Vsim *sim = (Vsim*)vsim;
  sim->eval();
  main_time = time_ps;
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
  Verilated::commandArgs(argc, argv);
}

extern "C" void litex_sim_init_tracer(void *vsim, long start, long end,long load_start, long save_start)
{
  save_time = save_start;
  load_time = load_start;
  printf("MDEBUG: Save time: %ld, load_time: %ld\n", save_time, load_time);
  Vsim *sim = (Vsim*)vsim;
  tfp_start = start;
  tfp_end = end >= 0 ? end : UINT64_MAX;
  Verilated::traceEverOn(true);
#ifdef TRACE_FST
      tfp = new VerilatedFstC;
      sim->trace(tfp, 99);
      tfp->open("sim.fst");
#else
      tfp = new VerilatedVcdC;
      sim->trace(tfp, 99);
      tfp->open("sim.vcd");
#endif
  tfp->set_time_unit("1ps");
  tfp->set_time_resolution("1ps");
  g_sim = sim;
}


#ifdef SAVABLE
// --- Save Function ---
static void litex_sim_save_state(void *vsim,const char* filename) {
    Vsim *sim = (Vsim*)vsim;
    VerilatedSave vs;
    vs.open(filename);
    vs << main_time;
    vs << *sim;
    vs.close();
}

// --- Restore Function ---
static void litex_sim_restore_state(void *vsim,const char* filename) {
    Vsim *sim = (Vsim*)vsim;
    VerilatedRestore vr;
    vr.open(filename);
    vr >> main_time;
    vr >> *sim;
    vr.close();
}
#endif


extern "C" void litex_sim_tracer_dump()
{
  static int last_enabled = 0;
  bool dump_enabled = true;

  if (g_sim != nullptr) {
    dump_enabled = g_sim->sim_trace != 0 ? true : false;
    if (last_enabled == 0 && dump_enabled) {
      printf("<DUMP ON>");
      fflush(stdout);
    } else if (last_enabled == 1 && !dump_enabled) {
      printf("<DUMP OFF>");
      fflush(stdout);
    }
    last_enabled = (int) dump_enabled;
  }

  if (dump_enabled && tfp_start <= main_time && main_time <= tfp_end) {
    tfp->dump((vluint64_t) main_time);
  }
}

extern "C" int litex_sim_got_finish()
{
  int finished;
  tfp->flush();
  if((finished = Verilated::gotFinish())) {
    tfp->close();
  }
  return Verilated::gotFinish();
}

#if VM_COVERAGE
extern "C" void litex_sim_coverage_dump()
{
  VerilatedCov::write("sim.cov");
}
#endif

double sc_time_stamp()
{
  return main_time;
}
