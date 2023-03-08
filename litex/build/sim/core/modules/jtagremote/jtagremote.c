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
	char *tdi;
	char *tdo;
	char *tck;
	char *tms;
	char *sys_clk;
	struct event *ev;
	char databuf[2048];
	int data_start;
	int datalen;
	int cntticks;
	int fd;
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

static int jtagremote_start(void *b)
{
  base = (struct event_base *)b;
  printf("[jtagremote] loaded (%p)\n", base);
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

static int jtagremote_new(void **sess, char *args)
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

static int jtagremote_add_pads(void *sess, struct pad_list_s *plist)
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
  if(!strcmp(plist->name, "jtag")) {
    litex_sim_module_pads_get(pads, "tck", (void**)&s->tck);
    litex_sim_module_pads_get(pads, "tdi", (void**)&s->tdi);
    litex_sim_module_pads_get(pads, "tdo", (void**)&s->tdo);
    litex_sim_module_pads_get(pads, "tms", (void**)&s->tms);
  }

  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->sys_clk);

out:
  return ret;

}
static int jtagremote_tick(void *sess, uint64_t time_ps)
{
  static clk_edge_state_t edge;
	char c, val;
	int ret = RC_OK;

  struct session_s *s = (struct session_s*)sess;
  if(!clk_pos_edge(&edge, *s->sys_clk)) {
    return RC_OK;
  }

  s->cntticks++;
  if(s->cntticks % 10)
	  return RC_OK;

  if(s->datalen)
  {
	  c = s->databuf[s->data_start];

	  if((c >= '0') && (c <= '7')){
		  *s->tck = ((c - '0') >> 2) & 1;
		  *s->tms = ((c - '0') >> 1) & 1;
		  *s->tdi = (c - '0')  & 1;
	  }
	  if(c == 'R'){
		  val = *s->tdo + '0';
		  if(-1 == write(s->fd, &val, 1)) {
			  eprintf("Error writing on socket\n");
			  ret = RC_ERROR;
			  goto out;
		  }
	  }
	  s->data_start = (s->data_start + 1) % 2048;
	  s->datalen--;
  }

out:
  return ret;
}

static struct ext_module_s ext_mod = {
  "jtagremote",
  jtagremote_start,
  jtagremote_new,
  jtagremote_add_pads,
  NULL,
  jtagremote_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
