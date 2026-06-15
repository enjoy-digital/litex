/* Copyright (C) 2017 LambdaConcept */

#include <string.h>
#include <errno.h>
#include <stdio.h>
#include <signal.h>
#ifndef _WIN32
#include <netinet/in.h>
# ifdef _XOPEN_SOURCE_EXTENDED
#  include <arpa/inet.h>
# endif
#include <sys/socket.h>
#endif
#include <stdlib.h>
#include "error.h"
#include "modules.h"
#include "pads.h"
#include "veril.h"

#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>
#include <json-c/json.h>

void litex_sim_init(void **out);
void litex_sim_dump();

struct session_list_s {
  void *session;
  char tickfirst;
  struct ext_module_s *module;
  struct session_list_s *next;
};

uint64_t timebase_ps = 1;
uint64_t sim_time_ps = 0;
static double sim_start_time_s = 0.0;
static int sim_started = 0;
static int sim_stop_signal = 0;
static char sim_main_clk_name[64] = "";
static uint64_t sim_main_clk_requested_freq_hz = 0;
static double sim_main_clk_actual_freq_hz = 0.0;
struct session_list_s *sesslist=NULL;
struct event_base *base=NULL;

static double litex_sim_wall_time_s(void)
{
  struct timeval tv;
  evutil_gettimeofday(&tv, NULL);
  return (double)tv.tv_sec + (double)tv.tv_usec / 1000000.0;
}

static const char *litex_sim_signal_name(int signum)
{
  switch(signum)
  {
    case SIGINT:
      return "SIGINT";
#ifdef SIGTERM
    case SIGTERM:
      return "SIGTERM";
#endif
    default:
      return "SIGNAL";
  }
}

static int litex_sim_module_has_interface(struct module_s *m, const char *name)
{
  size_t i;

  if(m == NULL || name == NULL)
  {
    return 0;
  }

  for(i = 0; i < m->niface; i++)
  {
    if(m->iface[i].name != NULL && !strcmp(m->iface[i].name, name))
    {
      return 1;
    }
  }

  return 0;
}

static const char *litex_sim_module_first_interface(struct module_s *m)
{
  if(m == NULL || m->niface == 0)
  {
    return NULL;
  }

  return m->iface[0].name;
}

static double litex_sim_clocker_actual_freq_hz(uint64_t freq_hz)
{
  static const uint64_t ps_in_sec = 1000000000000ull;
  uint64_t period_ps;

  if(freq_hz == 0)
  {
    return 0.0;
  }

  period_ps = ps_in_sec / freq_hz;
  if(period_ps == 0)
  {
    return 0.0;
  }

  return (double)ps_in_sec / (double)period_ps;
}

static void litex_sim_select_main_clocker(struct module_s *m)
{
  json_object *args_json = NULL;
  json_object *freq_json = NULL;
  const char *clock_name;
  uint64_t freq_hz;
  int is_sys_clk;

  if(m == NULL || strcmp(m->name, "clocker") || m->args == NULL)
  {
    return;
  }

  clock_name = litex_sim_module_has_interface(m, "sys_clk") ?
    "sys_clk" : litex_sim_module_first_interface(m);
  if(clock_name == NULL)
  {
    return;
  }

  is_sys_clk = !strcmp(clock_name, "sys_clk");
  if(sim_main_clk_requested_freq_hz != 0)
  {
    if(!strcmp(sim_main_clk_name, "sys_clk"))
      return;
    if(!is_sys_clk)
      return;
  }

  args_json = json_tokener_parse(m->args);
  if(args_json == NULL)
  {
    return;
  }

  if(!json_object_object_get_ex(args_json, "freq_hz", &freq_json))
  {
    json_object_put(args_json);
    return;
  }

  freq_hz = json_object_get_int64(freq_json);
  if(freq_hz == 0)
  {
    json_object_put(args_json);
    return;
  }

  snprintf(sim_main_clk_name, sizeof(sim_main_clk_name), "%s", clock_name);
  sim_main_clk_requested_freq_hz = freq_hz;
  sim_main_clk_actual_freq_hz = litex_sim_clocker_actual_freq_hz(freq_hz);
  json_object_put(args_json);
}

static void litex_sim_select_main_clockers(struct module_s *ml)
{
  struct module_s *m;

  for(m = ml; m; m=m->next)
  {
    litex_sim_select_main_clocker(m);
  }
}

static void litex_sim_format_frequency(char *buf, size_t buf_size, double freq_hz)
{
  const char *unit = "Hz";
  double value = freq_hz;

  if(freq_hz >= 1e9)
  {
    unit = "GHz";
    value = freq_hz / 1e9;
  }
  else if(freq_hz >= 1e6)
  {
    unit = "MHz";
    value = freq_hz / 1e6;
  }
  else if(freq_hz >= 1e3)
  {
    unit = "kHz";
    value = freq_hz / 1e3;
  }

  snprintf(buf, buf_size, "%.3f%s", value, unit);
}

static void litex_sim_format_time(char *buf, size_t buf_size, double time_s)
{
  const char *unit = "s";
  double value = time_s;

  if(time_s > 0.0 && time_s < 1e-6)
  {
    unit = "ns";
    value = time_s * 1e9;
  }
  else if(time_s > 0.0 && time_s < 1e-3)
  {
    unit = "us";
    value = time_s * 1e6;
  }
  else if(time_s > 0.0 && time_s < 1.0)
  {
    unit = "ms";
    value = time_s * 1e3;
  }

  snprintf(buf, buf_size, "%.3f%s", value, unit);
}

static void litex_sim_print_summary(void)
{
  char sys_clk_freq[32];
  char requested_freq[32];
  char simulated_time[32];
  char elapsed_time[32];
  double wall_time_s;
  double sim_time_s;
  double realtime_ratio;

  wall_time_s = litex_sim_wall_time_s() - sim_start_time_s;
  sim_time_s = (double)sim_time_ps / 1000000000000.0;
  realtime_ratio = wall_time_s > 0.0 ? sim_time_s / wall_time_s : 0.0;

  printf("\n[sim] ");
  if(sim_main_clk_actual_freq_hz != 0.0)
  {
    litex_sim_format_frequency(sys_clk_freq, sizeof(sys_clk_freq),
      sim_main_clk_actual_freq_hz);
    printf("%s=%s", sim_main_clk_name, sys_clk_freq);
    if(sim_main_clk_actual_freq_hz != (double)sim_main_clk_requested_freq_hz)
    {
      litex_sim_format_frequency(requested_freq, sizeof(requested_freq),
        (double)sim_main_clk_requested_freq_hz);
      printf(" (requested %s)", requested_freq);
    }
    printf(", ");
  }
  litex_sim_format_time(simulated_time, sizeof(simulated_time), sim_time_s);
  litex_sim_format_time(elapsed_time, sizeof(elapsed_time), wall_time_s);
  printf("simulated=%s, elapsed=%s, performance=%.3fx realtime",
    simulated_time, elapsed_time, realtime_ratio);
  if(sim_stop_signal)
  {
    printf(", stop=%s", litex_sim_signal_name(sim_stop_signal));
  }
  printf("\n");
  fflush(stdout);
}

#ifndef _WIN32
static void litex_sim_signal_cb(evutil_socket_t signum, short events, void *arg)
{
  (void)events;
  (void)arg;

  sim_stop_signal = signum;
  if(base != NULL)
  {
    event_base_loopbreak(base);
  }
}
#endif

static int litex_sim_initialize_all(void **sim, void *base)
{
  struct module_s *ml=NULL;
  struct module_s *mli=NULL;
  struct ext_module_list_s *mlist=NULL;
  struct ext_module_list_s *pmlist=NULL;
  //struct ext_module_list_s *mlisti=NULL;
  struct pad_list_s *plist=NULL;
  struct pad_list_s *pplist=NULL;
  struct session_list_s *slist=NULL;
  void *vsim=NULL;
  int i;
  int ret = RC_OK;

  /* Load external modules */
  ret = litex_sim_load_ext_modules(&mlist);
  if(RC_OK != ret)
  {
    goto out;
  }
  for(pmlist = mlist; pmlist; pmlist=pmlist->next)
  {
    if(pmlist->module->start)
    {
      pmlist->module->start(base);
    }
  }

  /* Load configuration */
  ret = litex_sim_file_parse("sim_config.js", &ml, &timebase_ps);
  if(RC_OK != ret)
  {
    goto out;
  }
  litex_sim_select_main_clockers(ml);

  /* Init generated */
  litex_sim_init(&vsim);
  *sim = vsim;

  /* Get pads from generated */
  ret = litex_sim_pads_get_list(&plist);
  if(RC_OK != ret)
  {
    goto out;
  }

  for(mli = ml; mli; mli=mli->next)
  {

    /* Find the module in the external module */
    pmlist = NULL;
    ret = litex_sim_find_ext_module(mlist, mli->name, &pmlist );
    if(RC_OK != ret)
    {
      goto out;
    }
    if(NULL == pmlist)
    {
      eprintf("Could not find module %s\n", mli->name);
      continue;
    }

    slist=(struct session_list_s *)malloc(sizeof(struct session_list_s));
    if(NULL == slist)
    {
      ret = RC_NOENMEM;
      goto out;
    }
    memset(slist, 0, sizeof(struct session_list_s));

    slist->tickfirst = mli->tickfirst;
    slist->module = pmlist->module;
    slist->next = sesslist;
    ret = pmlist->module->new_sess(&slist->session, mli->args);
    if(RC_OK != ret)
    {
      goto out;
    }
    sesslist = slist;

    /* For each interface */
    for(i = 0; i < mli->niface; i++)
    {
      /*Find the pads */
      pplist=NULL;
      ret = litex_sim_pads_find(plist, mli->iface[i].name, mli->iface[i].index, &pplist);
      if(RC_OK != ret)
      {
	goto out;
      }
      if(NULL == pplist)
      {
	eprintf("Could not find interface %s with index %d\n", mli->iface[i].name, mli->iface[i].index);
	continue;
      }
      ret = pmlist->module->add_pads(slist->session, pplist);
      if(RC_OK != ret)
      {
	goto out;
      }
    }
  }
out:
  return ret;
}

int litex_sim_sort_session()
{
  struct session_list_s *s;
  struct session_list_s *sprev=sesslist;

  if(!sesslist->next)
  {
    return RC_OK;
  }

  for(s = sesslist->next; s; s=s->next)
  {
    if(s->tickfirst)
    {
      sprev->next = s->next;
      s->next = sesslist;
      sesslist=s;
      s=sprev;
      continue;
    }
    sprev = s;
  }

  return RC_OK;
}

struct event *ev;

static void cb(int sock, short which, void *arg)
{
  struct session_list_s *s;
  void *vsim=arg;
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 0;
  int i;

  for(i = 0; i < 1000; i++)
  {
    for(s = sesslist; s; s=s->next)
    {
      if(s->tickfirst)
        s->module->tick(s->session, sim_time_ps);
    }

    litex_sim_eval(vsim, sim_time_ps);
    litex_sim_dump();

    for(s = sesslist; s; s=s->next)
    {
      if(!s->tickfirst)
        s->module->tick(s->session, sim_time_ps);
    }

    sim_time_ps += timebase_ps;

    if (litex_sim_got_finish()) {
        event_base_loopbreak(base);
        break;
    }
  }

  if (!evtimer_pending(ev, NULL)) {
    event_del(ev);
    evtimer_add(ev, &tv);
  }
}

int main(int argc, char *argv[])
{
  void *vsim=NULL;
  struct timeval tv;
#ifndef _WIN32
  struct event *sigint_ev=NULL;
#ifdef SIGTERM
  struct event *sigterm_ev=NULL;
#endif
#endif

  int ret;

#ifdef _WIN32
  WSADATA wsa_data;
  WSAStartup(0x0201, &wsa_data);
#endif


  base = event_base_new();
  if(!base)
  {
    eprintf("Can't allocate base\n");
    ret=RC_ERROR;
    goto out;
  }

#ifndef _WIN32
  sigint_ev = evsignal_new(base, SIGINT, litex_sim_signal_cb, NULL);
  if(sigint_ev != NULL)
  {
    event_add(sigint_ev, NULL);
  }
#ifdef SIGTERM
  sigterm_ev = evsignal_new(base, SIGTERM, litex_sim_signal_cb, NULL);
  if(sigterm_ev != NULL)
  {
    event_add(sigterm_ev, NULL);
  }
#endif
#endif

  litex_sim_init_cmdargs(argc, argv);
  if(RC_OK != (ret = litex_sim_initialize_all(&vsim, base)))
  {
    goto out;
  }

  if(RC_OK != (ret = litex_sim_sort_session()))
  {
    goto out;
  }

  tv.tv_sec = 0;
  tv.tv_usec = 0;
  ev = event_new(base, -1, EV_PERSIST, cb, vsim);
  event_add(ev, &tv);
  sim_start_time_s = litex_sim_wall_time_s();
  sim_started = 1;
  event_base_dispatch(base);
out:
  if(vsim != NULL)
  {
    litex_sim_finalize(vsim);
#if VM_COVERAGE
    litex_sim_coverage_dump();
#endif
  }
  if(sim_started)
  {
    litex_sim_print_summary();
  }
#ifndef _WIN32
  if(sigint_ev != NULL)
  {
    event_free(sigint_ev);
  }
#ifdef SIGTERM
  if(sigterm_ev != NULL)
  {
    event_free(sigterm_ev);
  }
#endif
#endif
  return ret;
}
