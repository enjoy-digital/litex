#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"

#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>
#include <json-c/json.h>
#include "tapcfg.h"
#include "modules.h"

struct eth_packet_s {
  char data[2000];
  size_t len;
  struct eth_packet_s *next;
};

struct session_s {
  char *tx;
  char *tx_valid;
  char *tx_ready;
  char *rx;
  char *rx_valid;
  char *rx_ready;
  char *sys_clk;
  tapcfg_t *tapcfg;
  int fd;
  char databuf[2000];
  int datalen;
  char inbuf[2000];
  int inlen;
  int insent;
  struct eth_packet_s *ethpack;
  struct event *ev;
};

static struct event_base *base=NULL;

int litex_sim_module_get_args(char *args, char *arg, char **val)
{
  int ret = RC_OK;
  json_object *jsobj = NULL;
  json_object *obj = NULL;
  char *value = NULL;
  int r;

  jsobj = json_tokener_parse(args);
  if(NULL == jsobj) {
    fprintf(stderr, "Error parsing json arg: %s \n", args);
    ret = RC_JSERROR;
    goto out;
  }

  if(!json_object_is_type(jsobj, json_type_object)) {
    fprintf(stderr, "Arg must be type object! : %s \n", args);
    ret = RC_JSERROR;
    goto out;
  }

  obj=NULL;
  r = json_object_object_get_ex(jsobj, arg, &obj);
  if(!r) {
    fprintf(stderr, "Could not find object: \"%s\" (%s)\n", arg, args);
    ret = RC_JSERROR;
    goto out;
  }
  value = strdup(json_object_get_string(obj));

out:
  *val = value;
  return ret;
}

static int litex_sim_module_pads_get(struct pad_s *pads, char *name, void **signal)
{
  int ret = RC_OK;
  void *sig = NULL;
  int i;

  if(!pads || !name || !signal) {
    ret=RC_INVARG;
    goto out;
  }

  i = 0;
  while(pads[i].name) {
    if(!strcmp(pads[i].name, name)) {
      sig=(void*)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal=sig;
  return ret;
}

static int ethernet_start(void *b)
{
  base = (struct event_base *) b;
  printf("[ethernet] loaded (%p)\n", base);
  return RC_OK;
}

void event_handler(int fd, short event, void *arg)
{
  struct  session_s *s = (struct session_s*)arg;
  struct eth_packet_s *ep;
  struct eth_packet_s *tep;

  if (event & EV_READ) {
    ep = malloc(sizeof(struct eth_packet_s));
    memset(ep, 0, sizeof(struct eth_packet_s));
    ep->len = tapcfg_read(s->tapcfg, ep->data, 2000);
    if(ep->len < 60)
      ep->len = 60;

    if(!s->ethpack)
      s->ethpack = ep;
    else {
      for(tep=s->ethpack; tep->next; tep=tep->next);
      tep->next = ep;
    }
  }
}

static const char macadr[6] = {0xaa, 0xb6, 0x24, 0x69, 0x77, 0x21};

static int ethernet_new(void **sess, char *args)
{
  int ret = RC_OK;
  char *c_tap = NULL;
  char *c_tap_ip = NULL;
  struct session_s *s = NULL;
  struct timeval tv = {10, 0};
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

  ret = litex_sim_module_get_args(args, "interface", &c_tap);
  {
    if(RC_OK != ret)
      goto out;
  }
  ret = litex_sim_module_get_args(args, "ip", &c_tap_ip);
  {
    if(RC_OK != ret)
      goto out;
  }

  s->tapcfg = tapcfg_init();
  tapcfg_start(s->tapcfg, c_tap, 0);
  s->fd = tapcfg_get_fd(s->tapcfg);
  tapcfg_iface_set_hwaddr(s->tapcfg, macadr, 6);
  tapcfg_iface_set_ipv4(s->tapcfg, c_tap_ip, 24);
  tapcfg_iface_set_status(s->tapcfg, TAPCFG_STATUS_ALL_UP);
  free(c_tap);
  free(c_tap_ip);

  s->ev = event_new(base, s->fd, EV_READ | EV_PERSIST, event_handler, s);
  event_add(s->ev, &tv);

out:
  *sess=(void*)s;
  return ret;
}

static int ethernet_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*)sess;
  struct pad_s *pads;
  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  if(!strcmp(plist->name, "eth")) {
    litex_sim_module_pads_get(pads, "sink_data", (void**)&s->rx);
    litex_sim_module_pads_get(pads, "sink_valid", (void**)&s->rx_valid);
    litex_sim_module_pads_get(pads, "sink_ready", (void**)&s->rx_ready);
    litex_sim_module_pads_get(pads, "source_data", (void**)&s->tx);
    litex_sim_module_pads_get(pads, "source_valid", (void**)&s->tx_valid);
    litex_sim_module_pads_get(pads, "source_ready", (void**)&s->tx_ready);
  }
  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->sys_clk);

out:
  return ret;
}

static int ethernet_tick(void *sess, uint64_t time_ps)
{
  static clk_edge_state_t edge;
  char c;
  struct session_s *s = (struct session_s*)sess;
  struct eth_packet_s *pep;

  if(!clk_pos_edge(&edge, *s->sys_clk)) {
    return RC_OK;
  }

  *s->tx_ready = 1;
  if(*s->tx_valid == 1) {
    c = *s->tx;
    s->databuf[s->datalen++]=c;
  } else {
    if(s->datalen) {
      tapcfg_write(s->tapcfg, s->databuf, s->datalen);
      s->datalen=0;
    }
  }

  *s->rx_valid=0;
  if(s->inlen) {
    *s->rx_valid=1;
    *s->rx = s->inbuf[s->insent++];
    if(s->insent == s->inlen) {
      s->insent =0;
      s->inlen = 0;
    }
  } else {
    if(s->ethpack) {
      memcpy(s->inbuf, s->ethpack->data, s->ethpack->len);
      s->inlen = s->ethpack->len;
      pep=s->ethpack->next;
      free(s->ethpack);
      s->ethpack=pep;
    }
  }
  return RC_OK;
}

static struct ext_module_s ext_mod = {
  "ethernet",
  ethernet_start,
  ethernet_new,
  ethernet_add_pads,
  NULL,
  ethernet_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
