/**
 * LiteX Simulator (verilated simulation)
 *
 * Copyright (c) 2017 LambdaConcept
 * Copyright (c) 2021 Leon Schuermann <leon@is.currently.online>
 */

#include <string.h>
#include <errno.h>
#include <stdio.h>
#include <signal.h>
#ifndef _WIN32
#include <netinet/in.h>
# ifdef _XOPEN_SOURCE_EXTENDED
#  include <arpa/inet.h>
# endif
#include <sys/socket.h>
#endif
#include <stdlib.h>
#include "error.h"
#include "modules.h"
#include "pads.h"
#include "veril.h"

#include <event2/listener.h>
#include <event2/util.h>
#include <event2/event.h>

void litex_sim_init(void **out);
void litex_sim_dump();

struct session_list_s {
  void *session;
  char tickfirst;
  struct ext_module_s *module;
  struct session_list_s *next;
};

uint64_t timebase_ps = 1;
uint64_t sim_time_ps = 0;

// TODO: introduce parameter which enables the simulation to halt on start.
bool sim_halt = false;

struct session_list_s *sesslist=NULL;
struct event_base *base=NULL;

static int litex_sim_initialize_all(void **sim, void *base)
{
  struct module_s *ml=NULL;
  struct module_s *mli=NULL;
  struct ext_module_list_s *mlist=NULL;
  struct ext_module_list_s *pmlist=NULL;
  //struct ext_module_list_s *mlisti=NULL;
  struct pad_list_s *plist=NULL;
  struct pad_list_s *pplist=NULL;
  struct session_list_s *fslist=NULL;
  struct session_list_s *slist=NULL;
  void *vsim=NULL;
  int i;
  int ret = RC_OK;

  // Initialize the first entry of the session list early on, as we'd
  // like to give a pointer to that to the individual modules. This
  // pointer is going to be passed back by the modules for
  // inter-module communication.
  fslist = malloc(sizeof(struct session_list_s));
  if (NULL == fslist) {
      ret = RC_NOENMEM;
      goto out;
  }

  /* Load external modules */
  ret = litex_sim_load_ext_modules(&mlist);
  if(RC_OK != ret)
  {
    goto out;
  }
  for(pmlist = mlist; pmlist; pmlist=pmlist->next)
  {
    if(pmlist->module->start)
    {
      pmlist->module->start(base, fslist);
    }
  }

  /* Load configuration */
  ret = litex_sim_file_parse("sim_config.js", &ml, &timebase_ps);
  if(RC_OK != ret)
  {
    goto out;
  }
  /* Init generated */
  litex_sim_init(&vsim);

  /* Get pads from generated */
  ret = litex_sim_pads_get_list(&plist);
  if(RC_OK != ret)
  {
    goto out;
  }

  for(mli = ml; mli; mli=mli->next)
  {
    /* Find the module in the external module */
    pmlist = NULL;
    ret = litex_sim_find_ext_module(mlist, mli->name, &pmlist );
    if(RC_OK != ret)
    {
      goto out;
    }
    if(NULL == pmlist)
    {
      eprintf("Could not find module %s\n", mli->name);
      continue;
    }

    slist = malloc(sizeof(struct session_list_s));
    if (NULL == slist) {
        ret = RC_NOENMEM;
        goto out;
    }
    memset(slist, 0, sizeof(struct session_list_s));

    slist->tickfirst = mli->tickfirst;
    slist->module = pmlist->module;
    slist->next = sesslist;
    ret = pmlist->module->new_sess(&slist->session, mli->args);
    if(RC_OK != ret)
    {
      goto out;
    }
    sesslist = slist;

    /* For each interface */
    for(i = 0; i < mli->niface; i++)
    {
      /*Find the pads */
      pplist=NULL;
      ret = litex_sim_pads_find(plist, mli->iface[i].name, mli->iface[i].index, &pplist);
      if(RC_OK != ret)
      {
        goto out;
      }
      if(NULL == pplist)
      {
        eprintf("Could not find interface %s with index %d\n", mli->iface[i].name, mli->iface[i].index);
        continue;
      }
      if (pmlist->module->add_pads != NULL) {
      ret = pmlist->module->add_pads(slist->session, pplist);
      if(RC_OK != ret)
      {
        goto out;
      }}
    }
  }

  // Move the list head to the already allocated memory location
  memcpy(fslist, slist, sizeof(struct session_list_s));

  // Try to send a message to every module session, announcing every
  // other module session.
  struct session_list_s *slist_iter_a;
  struct session_list_s *slist_iter_b;
  for (slist_iter_a = fslist; slist_iter_a != NULL; slist_iter_a = slist_iter_a->next) {
    litex_sim_msid_t dst_session_id;
    dst_session_id.sptr = slist_iter_a->session;
    for (slist_iter_b = fslist; slist_iter_b != NULL; slist_iter_b = slist_iter_b->next) {
      if (slist_iter_a != slist_iter_b) {
          litex_sim_msid_t mod_session_id;
          mod_session_id.sptr = slist_iter_b->session;
          modmsg_newmodsession_payload_t data;
          data.mod_name = slist_iter_b->module->name;
          data.mod_session_id = mod_session_id;
          void* retdata;
          litex_sim_send_msg(fslist, dst_session_id, MODMSG_OP_NEWMODSESSION, &data, &retdata);
      }
    }
  }

  *sim = vsim;
out:
  return ret;
}

int litex_sim_sort_session()
{
  struct session_list_s *s;
  struct session_list_s *sprev=sesslist;

  if(!sesslist->next)
  {
    return RC_OK;
  }

  for(s = sesslist->next; s; s=s->next)
  {
    if(s->tickfirst)
    {
      sprev->next = s->next;
      s->next = sesslist;
      sesslist=s;
      s=sprev;
      continue;
    }
    sprev = s;
  }

  return RC_OK;
}

struct event *ev;

static void cb(int sock, short which, void *arg)
{
  struct session_list_s *s;
  void *vsim=arg;
  struct timeval tv;
  tv.tv_sec = 0;
  tv.tv_usec = 0;
  int i;

  
  for(i = 0; i < 1000; i++)
  {
    if (sim_halt) {
      break;
    }

    for(s = sesslist; s; s=s->next)
    {
      if(s->tickfirst)
        s->module->tick(s->session, sim_time_ps);
    }

    litex_sim_eval(vsim, sim_time_ps);
    litex_sim_dump();

    for(s = sesslist; s; s=s->next)
    {
      if(!s->tickfirst)
        s->module->tick(s->session, sim_time_ps);
    }

    sim_time_ps += timebase_ps;

    if (litex_sim_got_finish()) {
        event_base_loopbreak(base);
        break;
    }
  }

  if (!evtimer_pending(ev, NULL) && !sim_halt) {
    event_del(ev);
    evtimer_add(ev, &tv);
  }
}

/**
 * Send a message to a module session in the simulation.
 *
 * Prototype and behavior defined in `modules.h`.
 */
msg_return_t litex_sim_send_msg(
  void *sim_handle,
  litex_sim_msid_t mod_session_id,
  uint32_t msg_op,
  void* data,
  void** retdata
) {
  struct session_list_s *slist = sim_handle;

  // Find the matching session
  while (slist != NULL) {
      if (slist->session == mod_session_id.sptr) {
        break;
    }
    slist = slist->next;
  }

  // Check whether we finished the loop without finding a matching module
  if (slist == NULL) {
    return MSGRET_MODSESSION_NOT_FOUND;
  }

  // Check whether the module has defined a handler for messages
  if (slist->module->module_msg == NULL) {
    return MSGRET_INVALID_OP;
  }

  // Finally, pass the message to the module
  msg_return_t msg_ret = (slist->module->module_msg)(slist->session, msg_op, data, retdata);

  if (msg_ret == MSGRET_MODSESSION_NOT_FOUND) {
      fprintf(stderr, "[litex_sim]: module %s reported MSGRET_MODSESSION_NOT_FOUND, which is illegal. replacing with MSGRET_FAIL.\n", slist->module->name);
      msg_ret = MSGRET_FAIL;
  }

  return msg_ret;
};

uint64_t litex_sim_current_time_ps(void *sim_handle) {
    return sim_time_ps;
}

bool litex_sim_halted(void *sim_handle) {
    return sim_halt;
}

void litex_sim_halt(bool halt) {
    struct timeval tv;
    tv.tv_sec = 0;
    tv.tv_usec = 0;

    sim_halt = halt;

    if (!evtimer_pending(ev, NULL) && !sim_halt) {
      event_del(ev);
      evtimer_add(ev, &tv);
    }
}

int main(int argc, char *argv[])
{
  void *vsim=NULL;
  struct timeval tv;

  int ret;

#ifdef _WIN32
  WSADATA wsa_data;
  WSAStartup(0x0201, &wsa_data);
#endif


  base = event_base_new();
  if(!base)
  {
    eprintf("Can't allocate base\n");
    ret=RC_ERROR;
    goto out;
  }

  litex_sim_init_cmdargs(argc, argv);
  if(RC_OK != (ret = litex_sim_initialize_all(&vsim, base)))
  {
    goto out;
  }

  if(RC_OK != (ret = litex_sim_sort_session()))
  {
    goto out;
  }

  tv.tv_sec = 0;
  tv.tv_usec = 0;
  ev = event_new(base, -1, EV_PERSIST, cb, vsim);
  event_add(ev, &tv);
  event_base_dispatch(base);
#if VM_COVERAGE
  litex_sim_coverage_dump();
#endif
out:
  return ret;
}
