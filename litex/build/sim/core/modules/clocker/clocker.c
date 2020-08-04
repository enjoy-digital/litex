#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <json-c/json.h>
#include "error.h"
#include "modules.h"

struct session_s {
  char *clk;
  char *name;
  uint32_t freq_hz;
  uint16_t phase_deg;
};

static int litex_sim_module_pads_get( struct pad_s *pads, char *name, void **signal)
{
  int ret = RC_OK;
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

static int clocker_parse_args(struct session_s *s, const char *args)
{
  int ret = RC_OK;
  json_object *args_json = NULL;
  json_object *freq_json = NULL;
  json_object *phase_json = NULL;

  args_json = json_tokener_parse(args);
  if (!args_json) {
    ret = RC_JSERROR;
    fprintf(stderr, "[clocker] Could not parse args: %s\n", args);
    goto out;
  }

  if(!json_object_object_get_ex(args_json, "freq_hz", &freq_json))
  {
    ret = RC_JSERROR;
    fprintf(stderr, "[clocker] \"freq_hz\" not found in args: %s\n", json_object_to_json_string(args_json));
    goto out;
  }

  if(!json_object_object_get_ex(args_json, "phase_deg", &phase_json))
  {
    ret = RC_JSERROR;
    fprintf(stderr, "[clocker] \"phase_deg\" not found in args: %s\n", json_object_to_json_string(args_json));
    goto out;
  }

  s->freq_hz = json_object_get_int64(freq_json);
  s->phase_deg = json_object_get_int64(phase_json);

  if (s->freq_hz == 0) {
    ret = RC_JSERROR;
    fprintf(stderr, "[clocker] \"freq_hz\" must be different than 0\n");
    goto out;
  }

  if (s->phase_deg >= 360) {
    ret = RC_JSERROR;
    fprintf(stderr, "[clocker] \"phase_deg\" must be in range [0, 360)\n");
    goto out;
  }
out:
  if(args_json) json_object_put(args_json);
  return ret;
}

static int clocker_start()
{
  printf("[clocker] loaded\n");
  return RC_OK;
}

static int clocker_new(void **sess, char *args)
{
  int ret = RC_OK;

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

  clocker_parse_args(s, args);
out:
  *sess=(void*)s;
  return ret;
}

static int clocker_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*)sess;
  struct pad_s *pads;

  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;

  ret = litex_sim_module_pads_get(pads, plist->name, (void**)&s->clk);
  if (ret != RC_OK) {
    goto out;
  }

  s->name = plist->name;
  *s->clk=0;
  printf("[clocker] %s: freq_hz=%u, phase_deg=%u\n", s->name, s->freq_hz, s->phase_deg);
out:
  return ret;
}

static int clocker_tick(void *sess, uint64_t time_ps)
{
  static const uint64_t ps_in_sec = 1000000000000ull;
  struct session_s *s = (struct session_s*) sess;

  uint64_t period_ps = ps_in_sec / s->freq_hz;
  uint64_t phase_shift_ps = period_ps * s->phase_deg / 360;

  // phase-shifted time relative to start of current period
  uint64_t rel_time_ps = (time_ps - phase_shift_ps) % period_ps;
  if (rel_time_ps < (period_ps/2)) {
    *s->clk = 1;
  } else {
    *s->clk = 0;
  }

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
