/* Copyright (C) 2017 LambdaConcept */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "tinydir.h"
#include "error.h"
#include "libdylib.h"
#include "modules.h"

#ifdef _MSC_VER
#define LIBEXT "dll"
#else
#define LIBEXT "so"
#endif

static struct ext_module_list_s *modlist=NULL;

int litex_sim_register_ext_module(struct ext_module_s *mod)
{
  int ret=RC_OK;
  struct ext_module_list_s *ml=NULL;

  if(!mod)
  {
    eprintf("Invalid arguments\n");
    ret=RC_INVARG;
    goto out;
  }
  ml=( struct ext_module_list_s *)malloc(sizeof( struct ext_module_list_s));
  if(NULL == ml)
  {
    ret = RC_NOENMEM;
    eprintf("Not enough memory\n");
    goto out;
  }
  memset(ml, 0, sizeof( struct ext_module_list_s));
  ml->module = mod;
  ml->next = modlist;
  modlist = ml;

out:
  return ret;
}

int litex_sim_load_ext_modules(struct ext_module_list_s **mlist)
{
  int ret = RC_OK;
  tinydir_dir dir;
  tinydir_file file;
  dylib_ref lib;
  int (*litex_sim_ext_module_init)(int (*reg)(struct ext_module_s *));
  char name[300];
  if (tinydir_open(&dir, "./modules/") == -1)
  {
    ret = RC_ERROR;
    eprintf("Error opening file");
    goto out;
  }
  if(modlist)
  {
    ret=RC_ERROR;
    eprintf("modules already loaded !\n");
    goto out;
  }
  while(dir.has_next)
  {
    if(-1 == tinydir_readfile(&dir, &file))
    {
      ret = RC_ERROR;
      eprintf("Can't get file \n");
    }

    if(!strcmp(file.extension, LIBEXT))
    {
      sprintf(name, "./modules/%s", file.name);
      lib = libdylib_open(name);
      if(!lib)
      {
	ret = RC_ERROR;
	eprintf("Can't load library %s\n", libdylib_last_error());
	goto out;
      }

      if(!libdylib_find(lib, "litex_sim_ext_module_init"))
      {
	ret = RC_ERROR;
	eprintf("Module has no litex_sim_ext_module_init function\n");
	goto out;
      }
      LIBDYLIB_BINDNAME(lib, litex_sim_ext_module_init);
      if(!litex_sim_ext_module_init)
      {
	ret = RC_ERROR;
	eprintf("Can't bind %s\n", libdylib_last_error());
	goto out;
      }
      ret = litex_sim_ext_module_init(litex_sim_register_ext_module);
      if(RC_OK != ret)
      {
	goto out;
      }
    }
    if(-1 == tinydir_next(&dir))
    {
      eprintf("Error getting next file\n");
      ret = RC_ERROR;
      goto out;
    }
  }
  *mlist = modlist;
out:
  tinydir_close(&dir);
  return ret;
}

int litex_sim_find_ext_module(struct ext_module_list_s *first, char *name , struct ext_module_list_s **found)
{
  struct ext_module_list_s *list = NULL;
  int ret=RC_OK;

  if(!first || !name || !found)
  {
    ret = RC_INVARG;
    eprintf("Invalid first:%s arg:%s found:%p\n", first->module->name, name, found);
    goto out;
  }

  for(list = first; list; list=list->next)
  {
    if(!strcmp(name, list->module->name))
      break;
  }
out:
  *found = list;
  return ret;
}

int litex_sim_find_module(struct module_s *first, char *name , struct module_s **found)
{
  struct module_s *list = NULL;
  int ret=RC_OK;

  if(!first || !name || !found)
  {
    ret = RC_INVARG;
    eprintf("Invalid first:%s arg:%s found:%p\n", first->name, name, found);
    goto out;
  }

  for(list = first; list; list=list->next)
  {
    if(!strcmp(name, list->name))
      break;
  }
out:
  *found = list;
  return ret;
}
