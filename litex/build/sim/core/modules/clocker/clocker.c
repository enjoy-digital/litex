#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"
#include "modules.h"

struct session_s {
  char *sys_clk;
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
  struct pad_s *pads;

  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  
  if(!strcmp(plist->name, "sys_clk")) {
    litex_sim_module_pads_get(pads, "sys_clk", (void**)&s->sys_clk);
  }

  *s->sys_clk=0;

out:
  return ret;
}

static int clocker_tick(void *sess)
{
  struct session_s *s=(struct session_s*)sess;
  *s->sys_clk = ~(*s->sys_clk);
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
