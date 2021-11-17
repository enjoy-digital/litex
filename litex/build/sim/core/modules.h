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

/**
 * Inter-module messaging.
 *
 * The LiteX simulator provides a way for modules to exchange messages. This can
 * be used for a variety of things, such as emulating hardware which is
 * connected two two independent bus subsystems, controlling the simulation,
 * etc. The messaging system does not define the content and types of messages
 * transmitted.
 *
 * While modules are free to implement their own message handlers, opcodes < 256
 * are reserved and must be defined in this file below. This is to enable
 * implementation of global, non module-specific behavior.
 *
 * An example of this is the simctrl interface. It is a generic component which
 * can be used to allow external programs to interface with the simulation and
 * is a bridge for messages to specific modules in the simulation. Thus it's
 * interface and it's opcodes are specified here.
 *
 * To discover other modules in the simulation, each module with a registered
 * module handler will retrieve a message of opcode MODMSG_OP_NEWMODSESSION with
 * a `data` value of type `modmsg_newmodsession_payload_t` for each module
 * session in the simulation. The returned `*retdata` must be NULL.
 */

// Global inter-module messaging opcodes
#define MODMSG_OP_NEWMODSESSION 0
#define MODMSG_OP_SIMCTRL_REQ 1
#define MODMSG_OP_SIMCTRL_RETFREE 2

/**
 * Error codes for inter-module messaging.
 *
 * Modules must never return MSGRET_MODSESSION_NOT_FOUND.
 */
typedef enum {
  MSGRET_SUCCESS = 0,
  MSGRET_FAIL = -1,
  MSGRET_MODSESSION_NOT_FOUND = -2,
  MSGRET_INVALID_OP = -3,
} msg_return_t;

/**
 * Convert a msg_return_t to a string representation.
 *
 * This performs no allocations.
 */
const char* msg_return_strerror(msg_return_t err);


/**
 * A simctrl message targeted towards a specific module.
 *
 * The MODMSG_OP_SIMCTRL_REQ and MODMSG_OP_SIMCTRL_RETFREE messages use this
 * data type as their `data` parameter. The MODMSG_OP_SIMCTRL_REQ messages
 * accept an optional `retdata` pointer to point towards a valid instance of
 * this data type.
 *
 * The simctrl_msg_t pointer passed into `data` on a MODMSG_OP_SIMCTRL_REQ,
 * along with the contained `data` field, is allocated by the caller and only
 * valid for the duration of the method invocation.
 *
 * On a MODMSG_OP_SIMCTRL_REQ the receiving module may wish to return a response
 * to the caller. It can allocate a `simctrl_msg_t` and make `retdata` point to
 * this allocated struct, which will be recognized as a response by the message
 * sender. If `retdata` is non-NULL, to allow freeing the allocated memory, the
 * sender must subsequently send a MODMSG_OP_SIMCTRL_RETFREE message, with the
 * `data` pointer set to the value written to `retdata`. This can be used by the
 * receiving module to free the previously allocated module. To keep additional
 * state between sending the response and freeing the response memory, the
 * receiver is free to use the `retdata_private` field.
 *
 * Upon a MODMSG_OP_SIMCTRL_RETFREE, the `retdata` field MUST be set to NULL. No
 * additional response may be returned.
 *
 * Visually, the message flow looks like the following:
 *
 * /----------------\                                   /--------------\
 * | simctrl        |  MODMSG_OP_SIMCTRL_REQ            | other module |
 * | implementation |  -> `data` stack allocated        |              |
 * |                |---------------------------------->|              |
 * |                |     `*retdata` heap allocated <-  |              |
 * |                |                       or NULL     |              |
 * |                |                                   |              |
 * -- if `*retdata` is not NULL ----------------------------------------
 * |                |                                   |              |
 * |                |  MODMSG_OP_SIMCTRL_RETFREE        |              |
 * |                |  -> `data` = previous `*retdata`  |              |
 * |                |---------------------------------->|              |
 * |                |       `*retdata` MUST be NULL <-  |              |
 * \----------------/                                   \--------------/
 */
typedef struct {
  size_t len;
  void* data;
  void* retdata_private;
} simctrl_msg_t;

/**
 * Identifier of a specific module session.
 *
 * Modules must not rely on or access the contents of this struct.
 */
typedef struct {
  void *sptr;
} litex_sim_msid_t;

/**
 * Payload of the MODMSG_OP_NEWMODSESSION message.
 *
 * Indicates that a specific module session has been registered with the
 * simulation. `mod_name` will contain the name of the registered
 * module. `mod_session_id` can be used with `litex_sim_send_msg` to send
 * messages to the respective module session.
 */
typedef struct {
  char *mod_name;
  litex_sim_msid_t mod_session_id;
} modmsg_newmodsession_payload_t;

/**
 * Send an inter-module message.
 *
 * Callers must pass in a valid sim_handle, typically announced to them using a
 * parameter on the `start` method of the `ext_module_s` interface.
 *
 * `mod_session_id` determines to which module session this message will be
 * routed. This value must have been provided to the caller through the
 * MODMSG_OP_NEWMODSESSION message.
 *
 * `msg_op`, `data` and `retdata` are forwarded to the call to `module_msg` on
 * the `ext_module_s` interface.
 *
 * In case the module session could not be found, this method will return
 * MSGRET_MODSESSION_NOT_FOUND. In case the module has no message handler
 * defined, this method will return MSGRET_INVALID_OP. If the module itself
 * returns MSGRET_MODSESSION_NOT_FOUND, this will be converted into a
 * MSGRET_FAIL.
 */
msg_return_t litex_sim_send_msg(
  void *sim_handle,
  litex_sim_msid_t mod_session_id,
  uint32_t msg_op,
  void* data,
  void** retdata
);

/**
 * Retrieve the current simulation time in picoseconds.
 */
uint64_t litex_sim_current_time_ps(void *sim_handle);

/**
 * Query the current state of the simulation.
 *
 * Returns:
 * - `true` if the simulation is currently halted.
 * - `false` if the simulation is currently running.
 */
bool litex_sim_halted(void *sim_handle);

/**
 * Request the simulation to halt or resume.
 *
 * Parameters:
 * `halt`: - if `true`, halt the simulation
 *         - if `false`, resume the simulation
 *
 * If the simulation is already in the requested state, this does nothing.
 *
 * Beware that halting the simulation will eventually cause calls to `tick`
 * methods on `ext_module_s` interfaces to cease. The module should have a way
 * to resume the simulation at some point, possibly through a scheduled event on
 * the libevent base.
 */
void litex_sim_halt(bool halt);

struct ext_module_s {
  char *name;
  int (*start)(void *, void *sim_handle);
  int (*new_sess)(void **, char *);
  int (*add_pads)(void *, struct pad_list_s *);
  int (*close)(void*);
  int (*tick)(void*, uint64_t);

  /** Generic interface for inter-module communication
   *
   * This method is invoked whenever a message for a module with a matching name
   * is received.
   *
   * It is legal for a module to not implement this function. If this function
   * pointer is set to NULL, every received message will automatically return an
   * MSGRET_INVALID_OP.
   *
   * The return code must indicate whether the message received and processed
   * successfully. Implementations must never return
   * MSGRET_MODSESSION_NOT_FOUND.
   *
   * `msg_op` hints at the type of a message. The API contract per `msg_op` is
   * defined by the module itself. Thus `msg_op` must be unique within a given
   * module only.
   *
   * Any message payload will be passed as `data`. If no payload is provided,
   * this pointer can be NULL.
   *
   * A pointer to a return payload, if any, can be placed in `retdata`. How
   * allocated memory for return payload is freed is not specified in this
   * interface. One possible implementation is to define an additional `msg_op`
   * per `msg_op`, invoked with the pointer to `retdata` passed in such that the
   * module implementation can decide whether memory needs to be freed.
   */
  msg_return_t (*module_msg)(void* state, uint32_t msg_op, void *data, void **retdata);
};

struct ext_module_list_s {
  struct ext_module_s *module;
  struct ext_module_list_s *next;
};

int litex_sim_file_parse(char *filename, struct module_s **mod, uint64_t *timebase);
int litex_sim_load_ext_modules(struct ext_module_list_s **mlist);
int litex_sim_find_ext_module(struct ext_module_list_s *first, char *name , struct ext_module_list_s **found);

typedef enum clk_edge {
    CLK_EDGE_NONE,
    CLK_EDGE_RISING,
    CLK_EDGE_FALLING,
} clk_edge_t;

typedef struct clk_edge_state {
  int last_clk;
} clk_edge_state_t;

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
