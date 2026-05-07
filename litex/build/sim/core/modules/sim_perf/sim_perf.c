#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <json-c/json.h>

#include "error.h"
#include "modules.h"

struct session_s {
  char *clk;
  char *name;
  uint64_t freq_hz;
  double interval_s;
  double last_report_time_s;
  uint64_t total_cycles;
  uint64_t last_report_cycles;
  clk_edge_state_t clk_edge;
};

static double wall_time_s(void)
{
  struct timeval tv;
  gettimeofday(&tv, NULL);
  return (double)tv.tv_sec + (double)tv.tv_usec / 1000000.0;
}

static int litex_sim_module_pads_get(struct pad_s *pads, char *name, void **signal)
{
  int ret = RC_OK;
  void *sig = NULL;
  int i;

  if (!pads || !name || !signal) {
    ret = RC_INVARG;
    goto out;
  }

  i = 0;
  while (pads[i].name) {
    if (!strcmp(pads[i].name, name)) {
      sig = (void *)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal = sig;
  return ret;
}

static int sim_perf_parse_args(struct session_s *s, const char *args)
{
  int ret = RC_OK;
  json_object *args_json = NULL;
  json_object *freq_json = NULL;
  json_object *interval_json = NULL;

  s->freq_hz = 0;
  s->interval_s = 5.0;

  if (!args) {
    goto out;
  }

  args_json = json_tokener_parse(args);
  if (!args_json) {
    ret = RC_JSERROR;
    fprintf(stderr, "[sim_perf] Could not parse args: %s\n", args);
    goto out;
  }

  if (json_object_object_get_ex(args_json, "freq_hz", &freq_json)) {
    s->freq_hz = json_object_get_int64(freq_json);
  }

  if (json_object_object_get_ex(args_json, "interval_s", &interval_json)) {
    s->interval_s = json_object_get_double(interval_json);
  }

  if (s->interval_s <= 0.0) {
    ret = RC_JSERROR;
    fprintf(stderr, "[sim_perf] \"interval_s\" must be greater than 0\n");
    goto out;
  }

out:
  if (args_json) {
    json_object_put(args_json);
  }
  return ret;
}

static int sim_perf_start(void *b)
{
  (void)b;
  return RC_OK;
}

static int sim_perf_new(void **sess, char *args)
{
  int ret = RC_OK;
  struct session_s *s = NULL;

  if (!sess) {
    return RC_INVARG;
  }
  *sess = NULL;

  s = (struct session_s *)malloc(sizeof(struct session_s));
  if (!s) {
    ret = RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));

  ret = sim_perf_parse_args(s, args);
  if (ret != RC_OK) {
    free(s);
    s = NULL;
    goto out;
  }

  s->last_report_time_s = wall_time_s();

out:
  *sess = (void *)s;
  return ret;
}

static int sim_perf_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s *)sess;
  struct pad_s *pads;

  if (!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }

  pads = plist->pads;
  ret = litex_sim_module_pads_get(pads, plist->name, (void **)&s->clk);
  if (ret != RC_OK) {
    goto out;
  }

  s->name = plist->name;
  printf("[sim_perf] %s: interval=%.2fs", s->name, s->interval_s);
  if (s->freq_hz != 0) {
    printf(", reference=%" PRIu64 "Hz", s->freq_hz);
  }
  printf("\n");

out:
  return ret;
}

static int sim_perf_tick(void *sess, uint64_t time_ps)
{
  struct session_s *s = (struct session_s *)sess;
  uint64_t interval_cycles;
  double now_s;
  double elapsed_s;
  double effective_hz;
  double sim_time_s;

  if (!s || !s->clk) {
    return RC_OK;
  }

  if (!clk_pos_edge(&s->clk_edge, *s->clk)) {
    return RC_OK;
  }

  s->total_cycles++;
  now_s = wall_time_s();
  elapsed_s = now_s - s->last_report_time_s;
  if (elapsed_s < s->interval_s) {
    return RC_OK;
  }

  interval_cycles = s->total_cycles - s->last_report_cycles;
  effective_hz = (double)interval_cycles / elapsed_s;
  sim_time_s = (double)time_ps / 1000000000000.0;

  printf("[sim_perf] %s: %.2fMHz effective", s->name, effective_hz / 1e6);
  if (s->freq_hz != 0) {
    printf(", %.2fx realtime", effective_hz / (double)s->freq_hz);
  }
  printf(", sim_time=%.6fs, cycles=%" PRIu64 "\n", sim_time_s, s->total_cycles);
  fflush(stdout);

  s->last_report_time_s = now_s;
  s->last_report_cycles = s->total_cycles;

  return RC_OK;
}

static int sim_perf_close(void *sess)
{
  free(sess);
  return RC_OK;
}

static struct ext_module_s ext_mod = {
  "sim_perf",
  sim_perf_start,
  sim_perf_new,
  sim_perf_add_pads,
  sim_perf_close,
  sim_perf_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
