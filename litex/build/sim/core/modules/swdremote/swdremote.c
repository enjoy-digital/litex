/*
 * swdremote -- OpenOCD remote_bitbang server for the SWD wire protocol.
 *
 * Counterpart of the jtagremote module.
 * Character assignments below follow doc/manual/jtag/drivers/remote_bitbang.txt :
 *
 *   'O' / 'o'  SWDIO drive enable / disable (turnaround)
 *   'c'        sample SWDIO, reply '0' or '1'
 *   'd'..'g'   write {swclk, swdio} = bits 1/0 of (c - 'd')
 *   'Z' / 'z'  optional remote sleep (renamed from 'D'/'d', which now mean SWD writes)
 *
 * SWDIO is modelled as a single wire node with a pull-up: the DUT exposes it as three
 * signals (swdio_i, swdio_o, swdio_oe) because the black-box cluster has no true inout.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"
#include <unistd.h>
#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>

#include <json-c/json.h>
#include "modules.h"

struct session_s {
	char *swclk;
	char *swdio_i;
	char *swdio_o;
	char *swdio_oe;
	char *sys_clk;
	struct event *ev;
	char databuf[2048];
	int data_start;
	int datalen;
	int cntticks;
	int fd;
	int host_oe;    /* host is driving SWDIO */
	int host_swdio; /* value the host drives  */
	int started;
};

struct event_base *base;

int litex_sim_module_get_args( char *args, char *arg, char **val)
{
  int ret = RC_OK;
  json_object *jsobj = NULL;
  json_object *obj = NULL;
  char *value = NULL;
  int r;

  jsobj = json_tokener_parse(args);
  if(NULL==jsobj) {
    fprintf(stderr, "Error parsing json arg: %s \n", args);
    ret=RC_JSERROR;
    goto out;
  }
  if(!json_object_is_type(jsobj, json_type_object)) {
    fprintf(stderr, "Arg must be type object! : %s \n", args);
    ret=RC_JSERROR;
    goto out;
  }
  obj=NULL;
  r = json_object_object_get_ex(jsobj, arg, &obj);
  if(!r) {
    fprintf(stderr, "Could not find object: \"%s\" (%s)\n", arg, args);
    ret=RC_JSERROR;
    goto out;
  }
  value=strdup(json_object_get_string(obj));

out:
  *val = value;
  return ret;
}

static int litex_sim_module_pads_get( struct pad_s *pads, char *name, void **signal)
{
  int ret = RC_OK;
  void *sig = NULL;
  int i;

  if(!pads || !name || !signal) {
    ret = RC_INVARG;
    goto out;
  }

  i = 0;
  while(pads[i].name) {
    if(!strcmp(pads[i].name, name)) {
      sig = (void*)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal = sig;
  return ret;
}

static int swdremote_start(void *b)
{
  base = (struct event_base *)b;
  printf("[swdremote] loaded (%p)\n", base);
  return RC_OK;
}

void read_handler(int fd, short event, void *arg)
{
  struct session_s *s = (struct session_s*)arg;
  char buffer[1024];
  ssize_t read_len;

  int i;

  read_len = read(fd, buffer, 1024);
  for(i = 0; i < read_len; i++)
  {
    s->databuf[(s->data_start +  s->datalen ) % 2048] = buffer[i];
    s->datalen++;
  }
}

static void event_handler(int fd, short event, void *arg)
{
  if (event & EV_READ)
    read_handler(fd, event, arg);
}

static void accept_conn_cb(struct evconnlistener *listener, evutil_socket_t fd, struct sockaddr *address, int socklen,  void *ctx)
{
  struct session_s *s = (struct session_s*)ctx;
  struct timeval tv = {1, 0};

  s->fd = fd;
  s->ev = event_new(base, fd, EV_READ | EV_PERSIST , event_handler, s);
  event_add(s->ev, &tv);
}

static void
accept_error_cb(struct evconnlistener *listener, void *ctx)
{
  struct event_base *base = evconnlistener_get_base(listener);
  eprintf("ERRROR\n");

  event_base_loopexit(base, NULL);
}

static int swdremote_new(void **sess, char *args)
{
  int ret = RC_OK;
  struct session_s *s = NULL;
  char *cport = NULL;
  int port;
  struct evconnlistener *listener;
  struct sockaddr_in sin;

  if(!sess) {
    ret = RC_INVARG;
    goto out;
  }

  ret = litex_sim_module_get_args(args, "port", &cport);
  if(RC_OK != ret)
    goto out;

  printf("Found port %s\n", cport);
  sscanf(cport, "%d", &port);
  free(cport);
  if(!port) {
    ret = RC_ERROR;
    fprintf(stderr, "Invalid port selected!\n");
    goto out;
  }

  s=(struct session_s*)malloc(sizeof(struct session_s));
  if(!s) {
    ret = RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));

  memset(&sin, 0, sizeof(sin));
  sin.sin_family = AF_INET;
  sin.sin_addr.s_addr = htonl(0);
  sin.sin_port = htons(port);
  listener = evconnlistener_new_bind(base, accept_conn_cb, s,  LEV_OPT_CLOSE_ON_FREE|LEV_OPT_REUSEABLE, -1, (struct sockaddr*)&sin, sizeof(sin));
  if (!listener) {
    ret=RC_ERROR;
    eprintf("Can't bind port %d\n!\n", port);
    goto out;
  }
  evconnlistener_set_error_cb(listener, accept_error_cb);

out:
  *sess=(void*)s;
  return ret;
}

static int swdremote_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret=RC_OK;
  struct session_s *s=(struct session_s*)sess;
  struct pad_s *pads;
  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  printf("plist name: %s\n", plist->name);
  if(!strcmp(plist->name, "swd")) {
    litex_sim_module_pads_get(pads, "swclk",    (void**)&s->swclk);
    litex_sim_module_pads_get(pads, "swdio_i",  (void**)&s->swdio_i);
    litex_sim_module_pads_get(pads, "swdio_o",  (void**)&s->swdio_o);
    litex_sim_module_pads_get(pads, "swdio_oe", (void**)&s->swdio_oe);
  }

  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->sys_clk);

out:
  return ret;

}

/* Value seen by the DUT: the host's driven value, or the pull-up when the host has
 * released the line. */
static void swdremote_drive_dut(struct session_s *s)
{
  *s->swdio_i = s->host_oe ? (s->host_swdio & 1) : 1;
}

/* Value seen by the host: the target wins while it drives (turnaround has handed the bus
 * over), otherwise the host's own driven value, otherwise the pull-up. */
static char swdremote_sample(struct session_s *s)
{
  if(*s->swdio_oe)
    return (*s->swdio_o & 1) + '0';
  if(s->host_oe)
    return (s->host_swdio & 1) + '0';
  return '1';
}

static int swdremote_tick(void *sess, uint64_t time_ps)
{
  static clk_edge_state_t edge;
  char c, val;
  int ret = RC_OK;

  struct session_s *s = (struct session_s*)sess;
  if(!clk_pos_edge(&edge, *s->sys_clk)) {
    return RC_OK;
  }

  if(!s->started) {
    /* Idle line: SWCLK low, SWDIO released to the pull-up. */
    s->started = 1;
    *s->swclk  = 0;
    swdremote_drive_dut(s);
  }

  s->cntticks++;
  if(s->cntticks % 10)
	  return RC_OK;

  if(s->datalen)
  {
	  c = s->databuf[s->data_start];

	  switch(c) {
	  case 'O':
		/* Host drives SWDIO. */
		s->host_oe = 1;
		swdremote_drive_dut(s);
		break;
	  case 'o':
		/* Turnaround: host releases SWDIO. */
		s->host_oe = 0;
		swdremote_drive_dut(s);
		break;
	  case 'c':
		val = swdremote_sample(s);
		if(write(s->fd, &val, 1) == -1) {
			eprintf("Error writing on socket\n");
			ret = RC_ERROR;
			goto out;
		}
		break;
	  case 'd'...'g':
		/* swd_write: bit 1 = swclk, bit 0 = swdio. */
		*s->swclk    = ((c - 'd') >> 1) & 1;
		s->host_swdio = (c - 'd') & 1;
		swdremote_drive_dut(s);
		break;
	  case 'B':
	  case 'b':
		/* Blink -- no LED here. */
		break;
	  case 'Z':
	  case 'z':
		/* Remote sleep; the sim already paces at 1 char per 10 sys clocks. */
		break;
	  case 'Q':
		/* Quit: leave the line idle so a reconnect starts clean. */
		s->host_oe = 0;
		*s->swclk  = 0;
		swdremote_drive_dut(s);
		break;
	  default:
		/* JTAG-only requests ('0'-'7', 'r'-'u', 'R') are not valid on this transport. */
		break;
	  }

	  s->data_start = (s->data_start + 1) % 2048;
	  s->datalen--;
  }

out:
  return ret;
}

static struct ext_module_s ext_mod = {
  "swdremote",
  swdremote_start,
  swdremote_new,
  swdremote_add_pads,
  NULL,
  swdremote_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
