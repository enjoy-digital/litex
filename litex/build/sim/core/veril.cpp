/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "Vsim.h"
#include "verilated.h"

#if VM_TRACE
#ifdef TRACE_FST
#include "verilated_fst_c.h"
#else
#include "verilated_vcd_c.h"
#endif
#endif

#if VM_TRACE
#ifdef TRACE_FST
VerilatedFstC *tfp;
#else
VerilatedVcdC *tfp;
#endif
uint64_t tfp_start;
uint64_t tfp_end;
uint64_t tfp_timescale_ps = 1;
Vsim *g_sim = nullptr;
#endif

uint64_t main_time = 0;
uint64_t save_time = -1;
uint64_t load_time = 0;
static bool finalized = false;

#if defined(__GNUC__) || defined(__clang__)
extern "C" void litex_sim_user_pre_eval(void *vsim, uint64_t time_ps) __attribute__((weak));
extern "C" void litex_sim_user_post_eval(void *vsim, uint64_t time_ps) __attribute__((weak));

static void litex_sim_call_user_pre_eval(void *vsim, uint64_t time_ps)
{
  if (litex_sim_user_pre_eval != nullptr)
    litex_sim_user_pre_eval(vsim, time_ps);
}

static void litex_sim_call_user_post_eval(void *vsim, uint64_t time_ps)
{
  if (litex_sim_user_post_eval != nullptr)
    litex_sim_user_post_eval(vsim, time_ps);
}
#else
static void litex_sim_call_user_pre_eval(void *vsim, uint64_t time_ps)
{
  (void)vsim;
  (void)time_ps;
}

static void litex_sim_call_user_post_eval(void *vsim, uint64_t time_ps)
{
  (void)vsim;
  (void)time_ps;
}
#endif

#ifdef SAVABLE
static void litex_sim_save_state(void *vsim, const char *filename);
static void litex_sim_restore_state(void *vsim, const char *filename);
#endif

#if VM_TRACE
static void litex_sim_tracer_flush(void)
{
  if (tfp != nullptr) {
    tfp->flush();
  }
}

static void litex_sim_tracer_close(void)
{
  if (tfp != nullptr) {
    tfp->flush();
    tfp->close();
    delete tfp;
    tfp = nullptr;
    g_sim = nullptr;
  }
}
#endif

extern "C" void litex_sim_eval(void *vsim, uint64_t time_ps)
{
#ifdef SAVABLE
  if (main_time == load_time && load_time > 0) {
    printf("MDEBUG: Restoring state at time %ld\n", load_time);
    litex_sim_restore_state(vsim, "sim_default.vlt");
  }
  if (main_time == save_time) {
    printf("MDEBUG: Saving state at time %ld\n", save_time);
    litex_sim_save_state(vsim, "sim_default.vlt");
  }
#endif
  Vsim *sim = (Vsim *)vsim;
  litex_sim_call_user_pre_eval(sim, time_ps);
  sim->eval();
  litex_sim_call_user_post_eval(sim, time_ps);
  main_time = time_ps;
}

extern "C" void litex_sim_init_cmdargs(int argc, char *argv[])
{
  Verilated::commandArgs(argc, argv);
}

extern "C" void litex_sim_init_runtime(long load_start, long save_start)
{
  save_time = save_start;
  load_time = load_start;
  printf("MDEBUG: Save time: %ld, load_time: %ld\n", save_time, load_time);
}

extern "C" void litex_sim_init_tracer(void *vsim, long start, long end,
                                      const char *timescale, uint64_t timescale_ps)
{
#if VM_TRACE
  Vsim *sim = (Vsim *)vsim;
  tfp_start = start;
  tfp_end = end >= 0 ? end : UINT64_MAX;
  tfp_timescale_ps = timescale_ps == 0 ? 1 : timescale_ps;
  Verilated::traceEverOn(true);
#ifdef TRACE_FST
  tfp = new VerilatedFstC;
  sim->trace(tfp, 99);
#else
  tfp = new VerilatedVcdC;
  sim->trace(tfp, 99);
#endif
  tfp->set_time_unit(timescale);
  tfp->set_time_resolution(timescale);
#ifdef TRACE_FST
  tfp->open("sim.fst");
#else
  tfp->open("sim.vcd");
#endif
  g_sim = sim;
#else
  (void)vsim;
  (void)start;
  (void)end;
  (void)timescale;
  (void)timescale_ps;
#endif
}

#ifdef SAVABLE
static void litex_sim_save_state(void *vsim, const char *filename)
{
  Vsim *sim = (Vsim *)vsim;
  VerilatedSave vs;
  vs.open(filename);
  vs << main_time;
  vs << *sim;
  vs.close();
}

static void litex_sim_restore_state(void *vsim, const char *filename)
{
  Vsim *sim = (Vsim *)vsim;
  VerilatedRestore vr;
  vr.open(filename);
  vr >> main_time;
  vr >> *sim;
  vr.close();
}
#endif

extern "C" void litex_sim_tracer_dump()
{
#if VM_TRACE
  static int last_enabled = 0;
  bool dump_enabled = true;

  if (g_sim != nullptr) {
    dump_enabled = (g_sim->sim_trace != 0);
    if (last_enabled == 0 && dump_enabled) {
      printf("<DUMP ON>");
      fflush(stdout);
    } else if (last_enabled == 1 && !dump_enabled) {
      printf("<DUMP OFF>");
      fflush(stdout);
    }
    last_enabled = (int) dump_enabled;
  }

  if (dump_enabled && tfp != nullptr && tfp_start <= main_time && main_time <= tfp_end) {
    tfp->dump((vluint64_t)(main_time / tfp_timescale_ps));
  }
#endif
}

extern "C" int litex_sim_got_finish()
{
  int finished = Verilated::gotFinish();

#if VM_TRACE
  litex_sim_tracer_flush();
#endif

  return finished;
}

extern "C" void litex_sim_finalize(void *vsim)
{
  Vsim *sim = (Vsim *)vsim;

  if (finalized)
    return;

  finalized = true;

  if (sim != nullptr)
    sim->final();

#if VM_TRACE
  litex_sim_tracer_close();
#endif
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
