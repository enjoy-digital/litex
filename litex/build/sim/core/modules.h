/* Copyright (C) 2017 LambdaConcept */

#ifndef __MODULE_H_
#define __MODULE_H_

#include <stdint.h>
#include <stdbool.h>
#include "pads.h"

typedef enum clk_edge {
    CLK_EDGE_NONE,
    CLK_EDGE_RISING,
    CLK_EDGE_FALLING,
} clk_edge_t;

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

typedef struct clk_edge_state {
  int last_clk;
} clk_edge_state_t;

int litex_sim_file_parse(char *filename, struct module_s **mod, uint64_t *timebase);
int litex_sim_load_ext_modules(struct ext_module_list_s **mlist);
int litex_sim_find_ext_module(struct ext_module_list_s *first, char *name , struct ext_module_list_s **found);

inline bool clk_pos_edge(clk_edge_state_t *edge_state, int new_clk) {
  bool is_edge = edge_state->last_clk == 0 && new_clk == 1;
  edge_state->last_clk = new_clk;
  return is_edge;
}

inline bool clk_neg_edge(clk_edge_state_t *edge_state, int new_clk) {
  bool is_edge = edge_state->last_clk == 1 && new_clk == 0;
  edge_state->last_clk = new_clk;
  return is_edge;
}

inline clk_edge_t clk_edge(clk_edge_state_t *edge_state, int new_clk) {
  clk_edge_t edge = CLK_EDGE_NONE;
  if (edge_state->last_clk == 0 && new_clk == 1) {
      edge = CLK_EDGE_RISING;
  } else if (edge_state->last_clk == 1 && new_clk == 0) {
      edge = CLK_EDGE_FALLING;
  }
  edge_state->last_clk = new_clk;
  return edge;
}

#endif
