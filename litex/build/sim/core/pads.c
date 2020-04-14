/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include "error.h"
#include "pads.h"

static struct pad_list_s *padlist=NULL;

int litex_sim_register_pads(struct pad_s *pads, char *interface_name, int index)
{
  int ret = RC_OK;

  struct pad_list_s *pl=NULL;
  if(!pads || !interface_name)
  {
    ret = RC_INVARG;
    eprintf("Invalid argument\n");
    goto out;
  }

  pl = (struct pad_list_s *)malloc(sizeof(struct pad_list_s));
  if(NULL == pl)
  {
    ret = RC_NOENMEM;
    eprintf("Not enough mem\n");
    goto out;
  }

  memset(pl, 0, sizeof(struct pad_list_s));

  pl->index = index; /* Do we really need it ?*/
  pl->name = strdup(interface_name);
  pl->pads = pads;

  pl->next = padlist;
  padlist = pl;

out:
  return ret;
}

int litex_sim_pads_get_list(struct pad_list_s **plist)
{
  int ret=RC_OK;


  if(!plist)
  {
    ret = RC_INVARG;
    eprintf("Invalid argument\n");
    goto out;
  }

  *plist = padlist;
out:
  return ret;
}

int litex_sim_pads_find(struct pad_list_s *first, char *name, int index, struct pad_list_s **found)
{
  struct pad_list_s *list = NULL;
  int ret=RC_OK;
  if(!first || !name || !found)
  {
    ret = RC_INVARG;
    eprintf("Invalid arg\n");
    goto out;
  }

  for(list = first; list; list=list->next)
  {
    if(!strcmp(name, list->name) && (list->index == index))
      break;
  }
out:
  *found = list;
  return ret;
}
