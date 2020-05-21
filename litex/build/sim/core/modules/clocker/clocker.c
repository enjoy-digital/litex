#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>
#include "error.h"
#include "modules.h"

struct session_s {
  char *sys_clk;
  char *dram_full_clk;
  char *dram_half_a_clk;
  char *dram_half_b_clk;
};

static int litex_sim_module_pads_get( struct pad_s *pads, char *name, void **signal)
{
  int ret;
  void *sig=NULL;
  int i;

  if(!pads || !name || !signal) {
    ret=RC_INVARG;
    goto out;
  }

  i = 0;
  while(pads[i].name) {
    if(!strcmp(pads[i].name, name))
    {
      sig=(void*)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal=sig;
  return ret;
}

static int clocker_start()
{
  printf("[clocker] loaded\n");
  return RC_OK;
}

static int clocker_new(void **sess, char *args)
{
  int ret=RC_OK;

  struct session_s *s=NULL;

  if(!sess) {
    ret = RC_INVARG;
    goto out;
  }

  s=(struct session_s*)malloc(sizeof(struct session_s));
  if(!s) {
    ret=RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));

out:
  *sess=(void*)s;
  return ret;
}

static int clocker_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*)sess;

  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }

  if(!strcmp("sys_clk", plist->name)) {
    litex_sim_module_pads_get(plist->pads, "sys_clk", (void**)&s->sys_clk);
    *s->sys_clk=0;
  } else if(!strcmp("dram_clk", plist->name)) {
    litex_sim_module_pads_get(plist->pads, "full_clk", (void**)&s->dram_full_clk);
    litex_sim_module_pads_get(plist->pads, "half_a_clk", (void**)&s->dram_half_a_clk);
    litex_sim_module_pads_get(plist->pads, "half_b_clk", (void**)&s->dram_half_b_clk);
    *s->dram_full_clk = 0;
    *s->dram_half_a_clk = 0;
    *s->dram_half_b_clk = 0;
  }

out:
  return ret;
}

inline static unsigned clock_gen(unsigned freq_hz, unsigned phase_deg, uint64_t tick, unsigned tick_period_ps) {
  static uint64_t const ps_in_s = 1000000000000ull;
  unsigned const period_ticks = ps_in_s / freq_hz / tick_period_ps;
  unsigned const phase_ticks = (phase_deg * period_ticks + 180) / 360;
  return tick >= phase_ticks ? ((tick - phase_ticks) % period_ticks < (period_ticks/2)) : 0;
}

static int clocker_tick(void *sess)
{
  static uint64_t const tick_period_ps = 125;
  struct session_s *s=(struct session_s*)sess;
  static uint64_t tick = 0;

  *s->sys_clk         = clock_gen(200000000, 0,   tick, tick_period_ps);
  *s->dram_full_clk   = clock_gen(800000000, 0,   tick, tick_period_ps);
  *s->dram_half_a_clk = clock_gen(400000000, 270, tick, tick_period_ps);
  *s->dram_half_b_clk = clock_gen(400000000, 180, tick, tick_period_ps);

  tick++;

  return 0;
}

static struct ext_module_s ext_mod = {
  "clocker",
  clocker_start,
  clocker_new,
  clocker_add_pads,
  NULL,
  clocker_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
