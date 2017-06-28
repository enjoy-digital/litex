/* Copyright (C) 2017 LambdaConcept */

#ifndef __MODULE_H_
#define __MODULE_H_

#include "pads.h"

struct interface_s {
  char *name;
  int index;
};

struct module_s {
  char *name;
  struct interface_s *iface;
  size_t niface;
  char tickfirst;
  char *args;
  struct module_s *next;
};

struct ext_module_s {
  char *name;
  int (*start)(void *);
  int (*new_sess)(void **, char *);
  int (*add_pads)(void *, struct pad_list_s *);
  int (*close)(void*);
  int (*tick)(void*);
};

struct ext_module_list_s {
  struct ext_module_s *module;
  struct ext_module_list_s *next;
};

int litex_sim_file_to_module_list(char *filename, struct module_s **mod);
int litex_sim_load_ext_modules(struct ext_module_list_s **mlist);
int litex_sim_find_ext_module(struct ext_module_list_s *first, char *name , struct ext_module_list_s **found);

#endif
