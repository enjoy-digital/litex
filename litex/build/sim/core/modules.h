/* Copyright (C) 2017 LambdaConcept */

#ifndef __MODULE_H_
#define __MODULE_H_

#include <stdint.h>
#include <stdbool.h>
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
  int (*tick)(void*, uint64_t);
};

struct ext_module_list_s {
  struct ext_module_s *module;
  struct ext_module_list_s *next;
};

struct clk_edge_t {
  int last_clk;
};

int litex_sim_file_parse(char *filename, struct module_s **mod, uint64_t *timebase);
int litex_sim_load_ext_modules(struct ext_module_list_s **mlist);
int litex_sim_find_ext_module(struct ext_module_list_s *first, char *name , struct ext_module_list_s **found);

inline bool clk_pos_edge(struct clk_edge_t *edge, int new_clk) {
  bool is_edge = edge->last_clk == 0 && new_clk == 1;
  edge->last_clk = new_clk;
  return is_edge;
}

inline bool clk_neg_edge(struct clk_edge_t *edge, int new_clk) {
  bool is_edge = edge->last_clk == 1 && new_clk == 0;
  edge->last_clk = new_clk;
  return is_edge;
}

#endif
