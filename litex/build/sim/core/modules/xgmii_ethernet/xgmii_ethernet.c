#include <assert.h>
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

#define ETH_LEN 9000
struct eth_packet_s {
  char data[ETH_LEN];
  size_t len;
  struct eth_packet_s *next;
};

#define DW_64
struct session_s {
  #ifdef DW_64
  unsigned long int tx;
  unsigned long int rx;
  #else
  unsigned int tx;
  unsigned int rx;
  #endif
  char tx_valid;
  char rx_valid;
  char rx_ready;

  #ifdef DW_64
  unsigned long int *tx_data;
  unsigned long int *rx_data;
  #else
  unsigned int *tx_data;
  unsigned int *rx_data;
  #endif

  char *tx_ctl;
  char terminate;
  char preamble;
  char *rx_ctl;
  char *sys_clk;

  tapcfg_t *tapcfg;
  int fd;
  char databuf[ETH_LEN];
  char rx_state;
  int datalen;
  char inbuf[ETH_LEN];
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
  int ret;
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

static int xgmii_ethernet_start(void *b)
{
  base = (struct event_base *) b;
  printf("[xgmii_ethernet] loaded (%p)\n", base);
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
    ep->len = tapcfg_read(s->tapcfg, ep->data, ETH_LEN);
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

static int xgmii_ethernet_new(void **sess, char *args)
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

static int xgmii_ethernet_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret=RC_OK;
  struct session_s *s = (struct session_s*)sess;
  struct pad_s *pads;
  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  if(!strcmp(plist->name, "eth")) {
    litex_sim_module_pads_get(pads, "rx_data", (void**)&s->rx_data);
    litex_sim_module_pads_get(pads, "rx_ctl", (void**)&s->rx_ctl);
    litex_sim_module_pads_get(pads, "tx_data", (void**)&s->tx_data);
    litex_sim_module_pads_get(pads, "tx_ctl", (void**)&s->tx_ctl);
  }

  if(!strcmp(plist->name, "sys_clk"))
    litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->sys_clk);

out:
  return ret;
}

#ifdef DW_64
char g_preamble = 0;
char g_dw = 64;
unsigned long int g_mask = 0xff;
unsigned long int g_idle = 0x0707070707070707;
#else
char g_preamble = 0;
char g_dw = 32;
unsigned int g_mask = 0xff;
unsigned int g_idle = 0x07070707;
#endif

static int xgmii_ethernet_tick(void *sess)
{
  struct session_s *s = (struct session_s*)sess;
  struct eth_packet_s *pep;

  if(*s->sys_clk == 0) {
    s->preamble=0;
    return RC_OK;
  }

  #ifdef DW_64
  unsigned long int u;
  #else
  unsigned int u;
  #endif
  // XGMII stuff
  u = *s->tx_data;
  s->tx = u;
  // printf("%16lx\t\t%x\n", u, *s->tx_ctl & g_mask);
  if (u != g_idle) {
    // printf("%16lx\t\t%x\n", u, *s->tx_ctl & g_mask);
    // printf("preamble: %02x\n", g_preamble);
  }

  if ((g_preamble == 0) && (*s->tx_ctl & g_mask) == 0x1) {
    g_preamble = (g_dw == 64)? 2: 1;
  } else if (g_preamble == 1) {
    g_preamble = 2;
  } else if (g_preamble == 2) {
    if ((*s->tx_ctl & g_mask) != 0) {
      // Intentionally ignoring errors for now (since we don't really have retransmission)
      // So this means last word
      // TODO: Check for end of frame mid word
      for (int m = 0; m < (g_dw >> 3); m++) {
        char mask = 1 << m;
        if ((*s->tx_ctl & mask) == 0)
	  s->databuf[s->datalen++] = (char) ((u & (g_mask << (8*m))) >> (8*m));
      }

      // Enable for debugging
      printf("Sending: \n");
      for(int i=0; i < s->datalen; printf("%02x ", s->databuf[i++] & 0xff));
      printf("\n%u\n", s->datalen);
      printf("Sent %u\n", s->datalen);
      tapcfg_write(s->tapcfg, s->databuf, s->datalen);
      s->datalen=0;
      g_preamble=0;
    } else {
      for (int i = 0; i < (g_dw >> 3); i++) {
	assert(s->datalen <= ETH_LEN);
	s->databuf[s->datalen++]= (char) ((u & (g_mask << (8 * i))) >> (8*i));
      }
    }
  }

  #ifdef DW_64
  unsigned long int local_data = 0x0707070707070707;
  unsigned long int temp_data = 0;  // This is here just to avoid an ugly cast later
  #else
  unsigned int local_data = 0x07070707;
  unsigned int temp_data = 0;
  #endif
  char temp_ctl = 0;
  char local_ctl = 0;
  if(s->inlen) {
    // printf("%x    ", s->rx_state);
    if (s->rx_state == 0) {
      *s->rx_data = 0xd5555555555555fb;
      *s->rx_ctl = 1;
      s->rx_state = 1;
    } else if ((s->rx_state == 1) && (s->insent + (g_dw >> 3) < s->inlen)) {
      *s->rx_ctl = 0;
      local_data = 0;
      for (unsigned int i = 0; i < (g_dw >> 3); i++) {
	temp_data = (unsigned char) s->inbuf[s->insent++];
	local_data |=  (temp_data << (i << 3));
      }
      *s->rx_data = local_data;
    } else if ((s->rx_state == 1) && (s->insent + (g_dw >> 3) >= s->inlen)) {
      // printf("%d, %d\n", s->insent, s->inlen);
      local_data = 0;
      for (unsigned int i = 0; i < (g_dw >> 3); i++) {
	if (s->insent < s->inlen) {
	  temp_data = (unsigned char) s->inbuf[s->insent++];
	} else if (s->insent == s->inlen) {
	  temp_data = (unsigned char) 0xfd;
	  temp_ctl = 1;
	  s->insent++;
	} else {
	  temp_data = (unsigned char) 0x07;
	  temp_ctl = 1;
	  s->insent++;
	}
	local_data |= (temp_data << (i << 3));
	local_ctl |= (temp_ctl  << i);
	//printf("%16lx %02x\n", local_data, local_ctl);
      }
      *s->rx_data = local_data;
      *s->rx_ctl = local_ctl;
      if (s->insent == s->inlen)
	s->rx_state = 2;
      else {
	s->insent = 0;
	s->inlen = 0;
	s->rx_state = 0;
      }
    } else if (s->rx_state == 2) {
      *s->rx_ctl = 0xff;
      *s->rx_data = 0x07070707070707fd;
      s->insent =0;
      s->inlen = 0;
      s->rx_state = 0;
    } else {
      *s->rx_ctl = 0xff;
      *s->rx_data = local_data;
    }
    // printf("%x, %16lx, %x\n", s->rx_state, *s->rx_data, *s->rx_ctl);
  } else {
    *s->rx_ctl = 0xff;
    *s->rx_data = local_data;
    if(s->ethpack) {
      memcpy(s->inbuf, s->ethpack->data, s->ethpack->len);
      printf("Received: %ld\n", s->ethpack->len );
      for(int i=0; i< s->ethpack->len;) {
	printf("%02x ", s->inbuf[i++] & 0xff);
	if (i%8 == 0 && i > 0);
      }
      printf("\n");
      s->inlen = s->ethpack->len;
      pep=s->ethpack->next;
      free(s->ethpack);
      s->ethpack=pep;
    }
  }
  return RC_OK;
}

static struct ext_module_s ext_mod = {
  "xgmii_ethernet",
  xgmii_ethernet_start,
  xgmii_ethernet_new,
  xgmii_ethernet_add_pads,
  NULL,
  xgmii_ethernet_tick
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
