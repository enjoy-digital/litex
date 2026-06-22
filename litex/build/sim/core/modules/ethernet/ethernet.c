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

enum ethernet_tx_mode {
  TX_MODE_AUTO = 0,
  TX_MODE_BARE,
  TX_MODE_GMII,
};

struct session_s {
  char *tx;
  char *tx_valid;
  char *tx_ready;
  char *rx;
  char *rx_valid;
  char *rx_ready;
  char *sys_clk;
  clk_edge_state_t sys_clk_edge;
  tapcfg_t *tapcfg;
  int fd;
  char databuf[2000];
  int datalen;
  enum ethernet_tx_mode tx_mode;
  enum ethernet_tx_mode tx_frame_mode;
  int tx_preamble_len;
  char inbuf[2000];
  int inlen;
  int insent;
  struct eth_packet_s *ethpack;
  struct event *ev;
};

static struct event_base *base=NULL;

static int litex_sim_module_get_args_common(char *args, char *arg, char **val, int required)
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
    if(required) {
      fprintf(stderr, "Could not find object: \"%s\" (%s)\n", arg, args);
      ret = RC_JSERROR;
    }
    goto out;
  }
  value = strdup(json_object_get_string(obj));

out:
  *val = value;
  return ret;
}

int litex_sim_module_get_args(char *args, char *arg, char **val)
{
  return litex_sim_module_get_args_common(args, arg, val, 1);
}

static int litex_sim_module_get_args_optional(char *args, char *arg, char **val)
{
  return litex_sim_module_get_args_common(args, arg, val, 0);
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

static void ethernet_tx_reset(struct session_s *s)
{
  s->tx_frame_mode   = (s->tx_mode == TX_MODE_GMII) ? TX_MODE_AUTO : s->tx_mode;
  s->tx_preamble_len = 0;
}

static void ethernet_tx_append(struct session_s *s, unsigned char c)
{
  if(s->datalen < (int)sizeof(s->databuf))
    s->databuf[s->datalen++] = c;
}

static void ethernet_tx_append_pending_preamble(struct session_s *s)
{
  while(s->tx_preamble_len) {
    ethernet_tx_append(s, 0x55);
    s->tx_preamble_len--;
  }
}

static void ethernet_tx_byte(struct session_s *s, unsigned char c)
{
  switch(s->tx_frame_mode) {
  case TX_MODE_GMII:
  case TX_MODE_BARE:
    ethernet_tx_append(s, c);
    break;
  case TX_MODE_AUTO:
    if(s->tx_mode == TX_MODE_GMII) {
      if(s->tx_preamble_len < 7) {
        s->tx_preamble_len++;
      } else {
        s->tx_preamble_len = 0;
        s->tx_frame_mode   = TX_MODE_GMII;
      }
      break;
    }
    if(s->tx_preamble_len < 7) {
      if(c == 0x55) {
        s->tx_preamble_len++;
      } else {
        ethernet_tx_append_pending_preamble(s);
        ethernet_tx_append(s, c);
        s->tx_frame_mode = TX_MODE_BARE;
      }
    } else {
      if(c == 0xd5) {
        s->tx_preamble_len = 0;
        s->tx_frame_mode   = TX_MODE_GMII;
      } else {
        ethernet_tx_append_pending_preamble(s);
        ethernet_tx_append(s, c);
        s->tx_frame_mode = TX_MODE_BARE;
      }
    }
    break;
  }
}

static void ethernet_tx_flush(struct session_s *s)
{
  if(s->tx_frame_mode == TX_MODE_AUTO && s->tx_mode != TX_MODE_GMII)
    ethernet_tx_append_pending_preamble(s);

  if(s->datalen) {
    int len = s->datalen;
    if(s->tx_frame_mode == TX_MODE_GMII)
      len = (s->datalen > 4) ? s->datalen - 4 : 0;
    if(len)
      tapcfg_write(s->tapcfg, s->databuf, len);
    s->datalen = 0;
  }

  ethernet_tx_reset(s);
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
  char *c_tx_mode = NULL;
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
  ret = litex_sim_module_get_args_optional(args, "tx_mode", &c_tx_mode);
  {
    if(RC_OK != ret)
      goto out;
  }

  if(c_tx_mode) {
    if(!strcmp(c_tx_mode, "auto"))
      s->tx_mode = TX_MODE_AUTO;
    else if(!strcmp(c_tx_mode, "bare") || !strcmp(c_tx_mode, "raw"))
      s->tx_mode = TX_MODE_BARE;
    else if(!strcmp(c_tx_mode, "gmii") || !strcmp(c_tx_mode, "preamble_crc"))
      s->tx_mode = TX_MODE_GMII;
    else {
      fprintf(stderr, "Unknown Ethernet TX mode: \"%s\"\n", c_tx_mode);
      ret = RC_INVARG;
      free(c_tx_mode);
      goto out;
    }
  }
  ethernet_tx_reset(s);

  s->tapcfg = tapcfg_init();
  tapcfg_start(s->tapcfg, c_tap, 0);
  s->fd = tapcfg_get_fd(s->tapcfg);
  tapcfg_iface_set_hwaddr(s->tapcfg, macadr, 6);
  tapcfg_iface_set_ipv4(s->tapcfg, c_tap_ip, 24);
  tapcfg_iface_set_status(s->tapcfg, TAPCFG_STATUS_ALL_UP);
  free(c_tap);
  free(c_tap_ip);
  free(c_tx_mode);

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
  struct session_s *s = (struct session_s*)sess;
  struct eth_packet_s *pep;

  if(!clk_pos_edge(&s->sys_clk_edge, *s->sys_clk)) {
    return RC_OK;
  }

  *s->tx_ready = 1;
  if(*s->tx_valid == 1) {
    ethernet_tx_byte(s, (unsigned char)*s->tx);
  } else {
    ethernet_tx_flush(s);
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
