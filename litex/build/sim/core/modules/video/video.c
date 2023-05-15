// Copyright (c) 2023 Victor Suarez Rovere <suarezvictor@gmail.com>
// Copyright (c) LiteX developers
// FIXME: add license

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"
#include <unistd.h>
#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>
#include <termios.h>

#include "modules.h"
#include "sim_fb.c" //from https://github.com/suarezvictor/CflexHDL/blob/main/src/sim_fb.c

struct session_s {
  char *hsync;
  char *vsync;
  char *de;
  char *valid;
  char *pix_clk;
  uint8_t *r;
  uint8_t *g;
  uint8_t *b;
  short hres, vres;
  short x, y;
  unsigned frame, stride;
  uint8_t *buf, *pbuf;
  fb_handle_t fb;
};

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
      sig = (void*)pads[i].signal;
      break;
    }
    i++;
  }

out:
  *signal = sig;
  return ret;
}

static int videosim_start(void *b)
{
  printf("[video] loaded (%p)\n", (struct event_base *)b);
  return RC_OK;
}

static int videosim_new(void **sess, char *args)
{
  int ret = RC_OK;
  struct session_s *s = NULL;

  if(!sess) {
    ret = RC_INVARG;
    goto out;
  }

  s = (struct session_s*) malloc(sizeof(struct session_s));
  if(!s) {
    ret=RC_NOENMEM;
    goto out;
  }
  memset(s, 0, sizeof(struct session_s));

out:
  *sess = (void*) s;
  return ret;
}

static int videosim_add_pads(void *sess, struct pad_list_s *plist)
{
  int ret = RC_OK;
  struct session_s *s = (struct session_s*) sess;
  struct pad_s *pads;

  if(!sess || !plist) {
    ret = RC_INVARG;
    goto out;
  }
  pads = plist->pads;
  if(!strcmp(plist->name, "vga")) {
    litex_sim_module_pads_get(pads, "hsync", (void**)&s->hsync);
    litex_sim_module_pads_get(pads, "vsync", (void**)&s->vsync);
    litex_sim_module_pads_get(pads, "de", (void**)&s->de);
    litex_sim_module_pads_get(pads, "r", (void**)&s->r);
    litex_sim_module_pads_get(pads, "g", (void**)&s->g);
    litex_sim_module_pads_get(pads, "b", (void**)&s->b);
	char *clk_pad = NULL;
    litex_sim_module_pads_get(pads, "clk", (void**) &clk_pad);
    if(clk_pad != NULL)
		s->pix_clk = clk_pad; //overrides sys_clk if previously set
  }

  if(!strcmp(plist->name, "sys_clk"))
  {
    if(!s->pix_clk) //not selected if vga clk was already used
      litex_sim_module_pads_get(pads, "sys_clk", (void**) &s->pix_clk);
  }
  
out:
  return ret;
}

static uint8_t *alloc_buf(unsigned short hres, unsigned short vres)
{
  return (uint8_t *) malloc(hres*vres*sizeof(uint32_t));
}

static int videosim_tick(void *sess, uint64_t time_ps) {
  static clk_edge_state_t edge;
  struct session_s *s = (struct session_s*)sess;

  if(!clk_pos_edge(&edge, *s->pix_clk)) {
    return RC_OK;
  }

  if(*s->vsync)
  {
    if(s->y != 0) //new frame
    {
      if(!s->vres)
      {
        s->vres = s->y;
        s->buf = alloc_buf(s->hres, s->vres);
        //printf("[video] start, resolution %dx%d\n", s->hres, s->vres);
        fb_init(s->hres, s->vres, false, &s->fb);
        s->stride = s->hres*sizeof(uint32_t);
      }
      s->y = 0;
      s->pbuf = s->buf;
      ++s->frame;
    }
  }

  if(*s->de)
  {
    if(s->pbuf)
    {
      *s->pbuf++ = *s->r;
      *s->pbuf++ = *s->g;
      *s->pbuf++ = *s->b;
      s->pbuf++;
    }
    s->x = s->x + 1;
  }
  else if(s->x != 0)
  {
    if(s->buf) //update each horizontal line
    {
      if(fb_should_quit())
      {
        fb_deinit(&s->fb);
        exit(1); //FIXME: end gracefully
      }
      fb_update(&s->fb, s->buf, s->stride);
      s->pbuf = s->buf + s->y*s->stride;
    }

    s->hres = s->x; //this is set many times until settled
    if(!s->hres) //avoid initial counting
      s->y = 0;
    s->y = s->y + 1;
    s->x = 0;
  }

  return RC_OK;
}

static struct ext_module_s ext_mod = {
  "video",
  videosim_start,
  videosim_new,
  videosim_add_pads,
  NULL,
  videosim_tick
};

int litex_sim_ext_module_init(int (*register_module) (struct ext_module_s *))
{
  int ret = RC_OK;
  ret = register_module(&ext_mod);
  return ret;
}
