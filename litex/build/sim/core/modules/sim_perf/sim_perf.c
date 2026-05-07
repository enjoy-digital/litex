#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/time.h>
#include <unistd.h>
#include <json-c/json.h>

#include "error.h"
#include "modules.h"

struct session_s {
  char *clk;
  char *tx;
  char *tx_valid;
  char *clock_name;
  uint64_t freq_hz;
  double interval_s;
  double last_report_time_s;
  double last_uart_time_s;
  uint64_t total_cycles;
  uint64_t last_report_cycles;
  clk_edge_state_t clk_edge;
  int console;
  int interactive;
  int status_active;
  int uart_line_open;
  int printed_header;
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
  json_object *console_json = NULL;

  s->freq_hz = 0;
  s->interval_s = 5.0;
  s->console = 0;

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

  if (json_object_object_get_ex(args_json, "console", &console_json)) {
    s->console = json_object_get_boolean(console_json);
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
  s->last_uart_time_s = s->last_report_time_s;
  s->interactive = s->console && isatty(fileno(stdout));

out:
  *sess = (void *)s;
  return ret;
}

static void sim_perf_print_header(struct session_s *s)
{
  if (s->printed_header || s->interactive || !s->clock_name) {
    return;
  }

  printf("[sim_perf] %s: interval=%.2fs", s->clock_name, s->interval_s);
  if (s->freq_hz != 0) {
    printf(", reference=%" PRIu64 "Hz", s->freq_hz);
  }
  printf("\n");
  s->printed_header = 1;
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

  if (!strcmp(plist->name, "sys_clk")) {
    ret = litex_sim_module_pads_get(pads, "sys_clk", (void **)&s->clk);
    if (ret != RC_OK) {
      goto out;
    }
    s->clock_name = plist->name;
    sim_perf_print_header(s);
  }

  if (!strcmp(plist->name, "serial")) {
    litex_sim_module_pads_get(pads, "source_data",  (void **)&s->tx);
    litex_sim_module_pads_get(pads, "source_valid", (void **)&s->tx_valid);
  }

out:
  return ret;
}

static void sim_perf_clear_status(struct session_s *s)
{
  if (!s->interactive || !s->status_active) {
    return;
  }

  printf("\r\033[2K");
  fflush(stdout);
  s->status_active = 0;
}

static void sim_perf_track_uart(struct session_s *s, double now_s)
{
  char tx;

  if (!s->tx_valid || !*s->tx_valid) {
    return;
  }

  sim_perf_clear_status(s);
  s->last_uart_time_s = now_s;

  if (!s->tx) {
    return;
  }

  tx = *s->tx;
  if (tx == '\n' || tx == '\r') {
    s->uart_line_open = 0;
  } else {
    s->uart_line_open = 1;
  }
}

static void sim_perf_format_status(
  char *buf,
  size_t buf_size,
  struct session_s *s,
  double effective_hz,
  double sim_time_s)
{
  if (s->freq_hz != 0) {
    snprintf(buf, buf_size,
      "[sim_perf] %s: %.2fMHz effective, %.2fx realtime, sim_time=%.6fs, cycles=%" PRIu64,
      s->clock_name, effective_hz / 1e6, effective_hz / (double)s->freq_hz, sim_time_s, s->total_cycles);
  } else {
    snprintf(buf, buf_size,
      "[sim_perf] %s: %.2fMHz effective, sim_time=%.6fs, cycles=%" PRIu64,
      s->clock_name, effective_hz / 1e6, sim_time_s, s->total_cycles);
  }
}

static int sim_perf_tick(void *sess, uint64_t time_ps)
{
  struct session_s *s = (struct session_s *)sess;
  uint64_t interval_cycles;
  char status[160];
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
  if (s->interactive) {
    sim_perf_track_uart(s, now_s);
  }

  elapsed_s = now_s - s->last_report_time_s;
  if (elapsed_s < s->interval_s) {
    return RC_OK;
  }

  interval_cycles = s->total_cycles - s->last_report_cycles;
  effective_hz = (double)interval_cycles / elapsed_s;
  sim_time_s = (double)time_ps / 1000000000000.0;
  sim_perf_format_status(status, sizeof(status), s, effective_hz, sim_time_s);

  if (s->interactive) {
    if (!s->uart_line_open && (now_s - s->last_uart_time_s) >= s->interval_s) {
      printf("\r\033[2K%s", status);
      fflush(stdout);
      s->status_active = 1;
    }
  } else {
    printf("%s\n", status);
    fflush(stdout);
  }

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
