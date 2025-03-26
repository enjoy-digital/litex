/**
 * simctrl module for interacting with the simulation through a
 * ZeroMQ/JSON-based protocol.
 *
 * This module provides a ZeroMQ/JSON-based protocol for basic interaction with
 * the LiteX simulation, as well as interacting with other modules through the
 * simctrl interface.
 *
 * Copyright (c) 2021 Leon Schuermann <leon@is.currently.online>
 *
 * All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions are met:
 *
 * 1. Redistributions of source code must retain the above copyright notice,
 *    this list of conditions and the following disclaimer.
 *
 * 2. Redistributions in binary form must reproduce the above copyright notice,
 *    this list of conditions and the following disclaimer in the documentation
 *    and/or other materials provided with the distribution.
 *
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
 * AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
 * LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 *
 * Copyright (c) 2021 Leon Schuermann <leon@is.currently.online>
 */

#include <stdio.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

#include <event2/event.h>
#include <json-c/json.h>
#include <zmq.h>

#include "error.h"
#include "modules.h"

#define SIMCTRL_ZMQ_RECV_ENVELOPE_BUF_LEN 1024
#define SIMCTRL_ZMQ_RECV_PAYLOAD_BUF_LEN  64 * 1024
#define SIMCTRL_ZMQ_SEND_ENVELOPE_BUF_LEN 1024
#define SIMCTRL_ZMQ_SEND_PAYLOAD_BUF_LEN  64 * 1024

typedef struct simctrl_modsession_list {
    char *mod_name;
    litex_sim_msid_t mod_session_id;
    size_t zmq_mod_session_id;
    time_t registered_at;
    struct simctrl_modsession_list *next;
} simctrl_modsession_list_t;

typedef struct {
    // Instantiated module sessions of the current simulation,
    // collected through incoming messages
    simctrl_modsession_list_t *modsession_list;
    // Counter used to assign IDs to the modsession list
    // elements. These values are exposed via ZeroMQ, we don't really
    // want to encode and expose the internal litex_sim_msid_t type to
    // ZeroMQ clients.
    size_t modsession_count;

    // ZeroMQ communication socket and libevent events
    void *zmq_context;
    void *zmq_socket_handle;
    void *zmq_fd_event;

    // Incoming ZeroMQ message buffer
    char zmq_recv_envelope_buffer[SIMCTRL_ZMQ_RECV_ENVELOPE_BUF_LEN];
    size_t zmq_recv_envelope_len;
    char zmq_recv_payload_buffer[SIMCTRL_ZMQ_RECV_PAYLOAD_BUF_LEN];
    size_t zmq_recv_payload_len;
} simctrl_state_t;

static struct event_base *base = NULL;
static void *sim_handle = NULL;

// Instance counter to make sure we don't violate the singleton pattern
static size_t ninstances = 0;

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

static void simctrl_zmq_report_error(simctrl_state_t *s,
                                     const char *err,
                                     json_object *additional_information) {
    int res;

    // Top-level response object
    json_object *response_obj = json_object_new_object();

    // Top-level response-type field
    json_object *response_type = json_object_new_string("error");
    json_object_object_add(response_obj, "_type", response_type);

    // Error code to report to the client
    json_object *response_error = json_object_new_string(err);
    json_object_object_add(response_obj, "error", response_error);

    // If we have additional information, also add that to the error
    // response
    if (additional_information != NULL) {
        // Increase the reference count for the passed in additional
        // information such that it is not freed through our call
        // below.
        json_object_get(additional_information);
        json_object_object_add(response_obj, "additional_information",
                               additional_information);
    }

    // Send the response via ZeroMQ. Don't need to free the encoded
    // string manually, it is stored within the json_object
    const char *encoded = json_object_to_json_string(response_obj);
    res = zmq_send(s->zmq_socket_handle, encoded, strlen(encoded), ZMQ_DONTWAIT);
    if (res < 0) {
        fprintf(stderr, "[simctrl]: responding to ZeroMQ request with error "
                "failed: %s\n", strerror(errno));
    }

    // Free all allocated memory. This will not free the passed in
    // additional_information.
    json_object_put(response_obj);
}

static void simctrl_zmq_process_message(simctrl_state_t *s) {
    int res;
    msg_return_t msg_res;

    // When we reach this function, we know that we have at least
    // received some envelope and maybe some payload via
    // ZeroMQ. However, we may have received zero bytes of data or
    // truncated data (the length being larger than the buffer
    // capacity). While the payload will potentially be passed
    // unmodified to a different subsystem, validate and
    // NULL-terminate the envelope so we can parse it as a JSON
    // string.
    if (s->zmq_recv_envelope_len > sizeof(s->zmq_recv_envelope_buffer)) {
        json_object *addinfo = json_object_new_object();
        json_object_object_add(addinfo, "actual",
                               json_object_new_int64(s->zmq_recv_envelope_len));
        json_object_object_add(addinfo, "maximum",
                               json_object_new_int64(
                                   sizeof(s->zmq_recv_envelope_buffer)));
        simctrl_zmq_report_error(s, "envelope_too_large", addinfo);
        json_object_put(addinfo);
        goto out;
    }

    if (s->zmq_recv_payload_len > sizeof(s->zmq_recv_payload_buffer)) {
        json_object *addinfo = json_object_new_object();
        json_object_object_add(addinfo, "actual",
                               json_object_new_int64(s->zmq_recv_envelope_len));
        json_object_object_add(addinfo, "maximum",
                               json_object_new_int64(
                                   sizeof(s->zmq_recv_envelope_buffer)));
        simctrl_zmq_report_error(s, "payload_too_large", addinfo);
        json_object_put(addinfo);
        goto out;
    }

    // Use the _ex parse method with a tokener to be able to limit the
    // string length. If the JSON is incomplete we treat it as invalid
    // json.
    json_tokener *tokener = json_tokener_new();
    // It appears we must still null-terminate the received string,
    // even though we pass a length to json_tokener_parse_ex.
    s->zmq_recv_envelope_buffer[s->zmq_recv_envelope_len] = '\0';
    json_object *request_envelope =
        json_tokener_parse_ex(tokener, s->zmq_recv_envelope_buffer,
                              s->zmq_recv_envelope_len);
    if (request_envelope == NULL) {
        enum json_tokener_error err = json_tokener_get_error(tokener);
        const char* errdesc = json_tokener_error_desc(err);
        json_object *addinfo = json_object_new_object();
        json_object_object_add(addinfo, "description",
                               json_object_new_string(errdesc));
        simctrl_zmq_report_error(s, "envelope_parse_error", addinfo);
        json_object_put(addinfo);
        goto free_tokener;
    }

    // Okay, parsing worked, let's see whether we know the type
    json_object *request_type;
    json_bool type_present = json_object_object_get_ex(request_envelope,
                                                       "_type", &request_type);
    if (!type_present) {
        simctrl_zmq_report_error(s, "envelope_missing_type", NULL);
        goto free_parsed;
    }
    if (!json_object_is_type(request_type, json_type_string)) {
        simctrl_zmq_report_error(s, "envelope_type_not_a_string", NULL);
        goto free_parsed;
    }

    const char* request_type_str = json_object_get_string(request_type);

    if (strcmp(request_type_str, "sim_info") == 0) {
        // Encode the current date and time into the object
        time_t timep = time(NULL);
        if (timep == -1) {
            simctrl_zmq_report_error(s, "get_time_failed", NULL);
            goto free_parsed;
        }

        // Store values in a JSON object
        json_object *sim_info = json_object_new_object();
        json_object_object_add(sim_info, "_type",
                               json_object_new_string("sim_info"));
        char *timestr = ctime(&timep);
        timestr[24] = '\0'; // Hack, to strip off the trailing newline
        json_object_object_add(sim_info, "system_time",
                               json_object_new_string(timestr));
        bool sim_halted = litex_sim_halted(sim_handle);
        json_object_object_add(sim_info, "sim_halted",
                               json_object_new_boolean(sim_halted));

        // Send the response via ZeroMQ
        const char *encoded = json_object_to_json_string(sim_info);
        res = zmq_send(s->zmq_socket_handle, encoded, strlen(encoded),
                       ZMQ_DONTWAIT);
        if (res < 0) {
            fprintf(stderr, "[simctrl]: responding to ZeroMQ request failed: "
                    "%s\n", strerror(errno));
        }

        // Free the allocated object
        json_object_put(sim_info);
    } else if (strcmp(request_type_str, "sim_time") == 0) {
        // Encode the current simulation time into the response
        json_object *sim_time = json_object_new_object();
        json_object_object_add(sim_time, "_type",
                               json_object_new_string("sim_time"));
        // TODO: handle overflows properly
        int64_t sim_time_ps = (int64_t) litex_sim_current_time_ps(sim_handle);
        json_object_object_add(sim_time, "sim_time",
                               json_object_new_int64(sim_time_ps));
        bool sim_halted = litex_sim_halted(sim_handle);
        json_object_object_add(sim_time, "sim_halted",
                               json_object_new_boolean(sim_halted));

        // Send the response via ZeroMQ
        const char *encoded = json_object_to_json_string(sim_time);
        res = zmq_send(s->zmq_socket_handle, encoded, strlen(encoded),
                       ZMQ_DONTWAIT);
        if (res < 0) {
            fprintf(stderr, "[simctrl]: responding to ZeroMQ request failed: "
                    "%s\n", strerror(errno));
        }

        // Free the allocated object
        json_object_put(sim_time);
    } else if (strcmp(request_type_str, "halt") == 0) {
        // For a module message, assert that we know of an instance
        // with the given session_id.
        json_object *halt_val;
        json_bool halt_present = json_object_object_get_ex(request_envelope,
                                                           "halt", &halt_val);
        if (!halt_present) {
            simctrl_zmq_report_error(s, "missing_halt", NULL);
            goto free_parsed;
        }

        json_type halt_type = json_object_get_type(halt_val);
        if (halt_type != json_type_boolean) {
            simctrl_zmq_report_error(s, "invalid_halt_type", NULL);
            json_object_put(halt_val);
            goto free_parsed;
        }

        json_bool halt = json_object_get_boolean(halt_val);
        //json_object_put(halt_val);

        litex_sim_halt(halt);

        // Encode the current simulation time into the response
        json_object *sim_halt = json_object_new_object();
        json_object_object_add(sim_halt, "_type",
                               json_object_new_string("halt"));
        // TODO: handle overflows properly
        int64_t sim_time_ps = (int64_t) litex_sim_current_time_ps(sim_handle);
        json_object_object_add(sim_halt, "sim_time",
                               json_object_new_int64(sim_time_ps));
        bool sim_halted = litex_sim_halted(sim_handle);
        json_object_object_add(sim_halt, "sim_halted",
                               json_object_new_boolean(sim_halted));

        // Send the response via ZeroMQ
        const char *encoded = json_object_to_json_string(sim_halt);
        res = zmq_send(s->zmq_socket_handle, encoded, strlen(encoded),
                       ZMQ_DONTWAIT);
        if (res < 0) {
            fprintf(stderr, "[simctrl]: responding to ZeroMQ request failed: "
                    "%s\n", strerror(errno));
        }

        // Free the allocated object
        json_object_put(sim_halt);
    } else if (strcmp(request_type_str, "module_session_list") == 0) {
        // Top-level object containing type info
        json_object *module_sessions_obj = json_object_new_object();
        json_object_object_add(module_sessions_obj, "_type",
                               json_object_new_string("module_session_list"));

        // List of individual module sessions
        json_object *module_sessions_arr = json_object_new_array();
        for (simctrl_modsession_list_t *ms = s->modsession_list;
             ms != NULL; ms = ms->next) {
            json_object *module_session = json_object_new_object();
            json_object_object_add(module_session, "module_name",
                                   json_object_new_string(ms->mod_name));
            json_object_object_add(module_session, "session_id",
                                   json_object_new_int64(
                                       ms->zmq_mod_session_id));
            char *timestr = ctime(&ms->registered_at);
            timestr[24] = '\0'; // Hack, to strip off the trailing newline
            json_object_object_add(module_session, "registered_at",
                                   json_object_new_string(timestr));
            json_object_array_add(module_sessions_arr, module_session);
        }
        json_object_object_add(module_sessions_obj, "module_sessions",
                               module_sessions_arr);

        // Send the response via ZeroMQ
        const char *encoded = json_object_to_json_string(module_sessions_obj);
        res = zmq_send(s->zmq_socket_handle, encoded, strlen(encoded),
                       ZMQ_DONTWAIT);
        if (res < 0) {
            fprintf(stderr, "[simctrl]: responding to ZeroMQ request failed: "
                    "%s\n", strerror(errno));
        }

        // Free the allocated object
        json_object_put(module_sessions_obj);
    } else if (strcmp(request_type_str, "module_msg") == 0) {
        // For a module message, assert that we know of an instance
        // with the given session_id.
        json_object *session_id;
        json_bool session_id_present =
            json_object_object_get_ex(request_envelope, "session_id",
                                      &session_id);
        if (!session_id_present) {
            simctrl_zmq_report_error(s, "missing_session_id", NULL);
            goto free_parsed;
        }
        if (!json_object_is_type(session_id, json_type_int)) {
            simctrl_zmq_report_error(s, "session_id_not_an_integer", NULL);
            goto free_parsed;
        }
        long zmq_session_id = json_object_get_int64(session_id);

        // Search for the session ID in the mod session list
        simctrl_modsession_list_t *ms = s->modsession_list;
        for (; ms != NULL; ms = ms->next) {
            if (ms->zmq_mod_session_id == zmq_session_id) {
                break;
            }
        }

        // Check whether we've reached the end of the list without finding the
        // module session
        if (ms == NULL) {
            simctrl_zmq_report_error(s, "session_not_found", NULL);
            goto free_parsed;
        }

        // Okay, we've found the session in question. Deliver the message.
        simctrl_msg_t data;
        data.len = s->zmq_recv_payload_len;
        data.data = s->zmq_recv_payload_buffer;
        simctrl_msg_t *retdata = NULL;
        msg_res = litex_sim_send_msg(sim_handle, ms->mod_session_id,
                                     MODMSG_OP_SIMCTRL_REQ, &data,
                                     (void*) &retdata);

        if (msg_res == MSGRET_MODSESSION_NOT_FOUND) {
            // Don't need to free retdata, module was not invoked
            fprintf(stderr, "[simctrl]: internal inconsistency in modsessions\n");
            simctrl_zmq_report_error(s, "internal_error", NULL);
        } else if (msg_res == MSGRET_INVALID_OP) {
            // Don't need to free retdata, module reported that the op does not
            // exist and thus it shouldn't have written to retdata
            simctrl_zmq_report_error(s, "module_does_not_support_simctrl", NULL);
        } else {
            // Either success or fail, in both cases report to the client

            // Top-level object containing type info
            json_object *module_sessions_obj = json_object_new_object();
            json_object_object_add(module_sessions_obj, "_type",
                                   json_object_new_string("module_msg"));

            // Encode the module return code as a string
            json_object_object_add(module_sessions_obj, "module_return_code",
                                   json_object_new_string(
                                       msg_return_strerror(msg_res)));

            // Send the envelope response via ZeroMQ
            const char *encoded =
                json_object_to_json_string(module_sessions_obj);
            res = zmq_send(s->zmq_socket_handle, encoded, strlen(encoded),
                           ZMQ_DONTWAIT
                           | ((retdata != NULL) ? ZMQ_SNDMORE : 0));
            if (res < 0) {
                fprintf(stderr, "[simctrl]: responding to ZeroMQ request "
                        "failed: %s\n", strerror(errno));
                goto free_parsed;
            }

            // When there is data returned by the module
            if (retdata != NULL) {
                res = zmq_send(s->zmq_socket_handle, retdata->data,
                               retdata->len, ZMQ_DONTWAIT);
                if (res < 0) {
                    fprintf(stderr, "[simctrl]: sending retdata via ZeroMQ "
                            "failed: %s\n", strerror(errno));
                }

                // Regardless of whether the transmission succeeded, we must
                // pass the retdata back to the module such that it can be
                // freed.
                void* dummy_retdata_free = NULL;
                msg_res = litex_sim_send_msg(sim_handle, ms->mod_session_id,
                                             MODMSG_OP_SIMCTRL_RETFREE,
                                             retdata, &dummy_retdata_free);
                if (msg_res != MSGRET_SUCCESS) {
                    fprintf(stderr, "[simctrl]: module %s passed back some "
                            "retdata, but does not accept the RETFREE call: "
                            "%d\n", ms->mod_name, msg_res);
                }
            }
        }
    } else {
        simctrl_zmq_report_error(s, "envelope_unknown_type", NULL);
    }

free_parsed:
    json_object_put(request_envelope);

free_tokener:
    json_tokener_free(tokener);

out:
    return;
}

static bool simctrl_zmq_recv_nonblock(simctrl_state_t *s) {
    int received_len;
    int rcvmore;
    size_t rcvmore_len = sizeof(rcvmore);

    // Try to receive the envelope first
    received_len = zmq_recv(
        s->zmq_socket_handle,
        s->zmq_recv_envelope_buffer,
        sizeof(s->zmq_recv_envelope_buffer),
        ZMQ_DONTWAIT
    );
    if (received_len >= 0) {
        s->zmq_recv_envelope_len = received_len;

        // Also, reset the payload length so if we don't receive any,
        // we won't use the previous buffer contents
        s->zmq_recv_payload_len = 0;

        // Now, check whether there is an additional payload
        // available. All parts of a message must arrive atomically,
        // thus it's fine to check this immediately here as well.
        zmq_getsockopt(s->zmq_socket_handle, ZMQ_RCVMORE, &rcvmore,
                       &rcvmore_len);
        if (rcvmore) {
            // There is an additional payload, try to receive it.
            received_len = zmq_recv(
                s->zmq_socket_handle,
                s->zmq_recv_payload_buffer,
                sizeof(s->zmq_recv_payload_buffer),
                ZMQ_DONTWAIT
            );
            if (received_len >= 0) {
                // There was a payload, set the length accordingly
                s->zmq_recv_payload_len = received_len;
            }
        }

        // There might be even more message parts, which we don't want
        // to handle. To avoid receiving them in the next invocation
        // of this function, process them here in a loop.
        do {
            zmq_getsockopt(s->zmq_socket_handle, ZMQ_RCVMORE, &rcvmore,
                           &rcvmore_len);
            if (rcvmore) {
                fprintf(stderr, "[simctrl]: received additional unexpected "
                        "ZeroMQ message parts\n");
                zmq_recv(s->zmq_socket_handle, NULL, 0, ZMQ_DONTWAIT);
            }
        } while (rcvmore);

        // In any case we've now got a valid envelope (and maybe also
        // payload) which we must process and respond to.
        simctrl_zmq_process_message(s);

        return true;
    } else {
        return false;
    }
}

static void simctrl_zmq_event_cb(int fd, short event, void *arg) {
    simctrl_state_t *s = arg;

    uint32_t events = 0;
    size_t events_len = sizeof(events);
    if (zmq_getsockopt(s->zmq_socket_handle, ZMQ_EVENTS, &events, &events_len)
        != 0) {
        fprintf(stderr, "[simctrl]: error retrieving information ZeroMQ socket "
                "event state: %s\n", strerror(errno));
        return;
    }

    if (events & ZMQ_POLLIN) {
        while (simctrl_zmq_recv_nonblock(s)) {
            // Receive pending messages
        }
    }
}

static int simctrl_start(void *b, void* sh) {
    base = (struct event_base *) b;
    sim_handle = sh;
    fprintf(stderr, "[simctrl] loaded (libevent base: %p, sim_handle: %p)\n",
            base, sim_handle);
    return RC_OK;
}

static int simctrl_new(void **state, char *args) {
    int res = RC_OK;
    //char *listen_port = NULL;
    simctrl_state_t *s = NULL;

    if (!state) {
        res = RC_INVARG;
        goto out;
    }

    // There should only ever be a single simctrl instance in a
    // simulation. It doesn't make sense to have two.
    if (ninstances > 0) {
        fprintf(stderr, "[simctrl]: refusing to create instance %ld\n",
                ninstances + 1);
        res = RC_ERROR;
        goto out;
    }

    /* ret = litex_sim_module_get_args(args, "listen_port", &listen_port); */
    /* if (ret != RC_OK) { */
    /*     return ret; */
    /* } */

    s = malloc(sizeof(simctrl_state_t));
    if (!s) {
        res = RC_NOENMEM;
        goto out;
    }

    // Set the ZMQ receive buffer lengths
    s->zmq_recv_envelope_len = 0;
    s->zmq_recv_payload_len = 0;

    // Create a new ZeroMQ context, create and bind a socket so that
    // clients can connect
    s->zmq_context = zmq_ctx_new();
    if (s->zmq_context == NULL) {
        fprintf(stderr, "[simctrl]: failed to create ZeroMQ context: %s\n",
                strerror(errno));
        res = RC_ERROR;
        goto free_simctrl_state;
    }

    s->zmq_socket_handle = zmq_socket(s->zmq_context, ZMQ_REP);
    if (s->zmq_socket_handle == NULL) {
        fprintf(stderr, "[simctrl]: failed to create ZeroMQ socket: %s\n",
                strerror(errno));
        res = RC_ERROR;
        goto free_zmq_ctx;
    }

    res = zmq_bind(s->zmq_socket_handle, "tcp://*:7173");
    if (res != 0) {
        fprintf(stderr, "[simctrl]: failed to bind ZeroMQ socket: %s\n",
                strerror(errno));
        res = RC_ERROR;
        goto free_zmq_ctx;
    }
    res = RC_OK;

    // Add ZMQ socket pull to event dispatcher
    int zmq_socket_fd;
    size_t zmq_socket_fd_len = sizeof(zmq_socket_fd);
    if (zmq_getsockopt(s->zmq_socket_handle, ZMQ_FD, &zmq_socket_fd,
                       &zmq_socket_fd_len) != 0) {
        fprintf(stderr, "[simctrl]: failed to determine the ZeroMQ socket file "
                "descriptor: %s\n", strerror(errno));
        res = RC_ERROR;
        goto free_zmq_ctx;
    }
    s->zmq_fd_event = event_new(base, zmq_socket_fd, EV_READ | EV_PERSIST,
                                simctrl_zmq_event_cb, s);
    struct timeval tv = {10, 0};
    event_add(s->zmq_fd_event, &tv);

    // Initialize all fields of the simctrl_state
    s->modsession_list = NULL;
    s->modsession_count = 0;

    // Register our session state and mark that we have created one
    // instance
    *state = (void*) s;
    ninstances += 1;

    // Everything worked, keep all allocated structures
    goto out;

free_zmq_ctx:
    zmq_ctx_destroy(s->zmq_context);

free_simctrl_state:
    free(s);

out:
    return res;
}

static int simctrl_add_pads(void *state, struct pad_list_s *plist) {
    return RC_OK;
}

static int simctrl_tick(void *state, uint64_t time_ps) {
    return RC_OK;
}

static msg_return_t simctrl_msg(void *state, uint32_t msg_op, void *data,
                                void **retdata) {
    simctrl_state_t *s = state;

    time_t timep = time(NULL);
    if (timep == -1) {
        fprintf(stderr, "[simctrl]: getting current time failed\n");
        return MSGRET_FAIL;
    }


    if (msg_op == MODMSG_OP_NEWMODSESSION) {
        // A new module session is being announced. Add it to the
        // internal list of module sessions.
        modmsg_newmodsession_payload_t *msg_payload = data;

        // New list element to append
        simctrl_modsession_list_t *modsession =
            malloc(sizeof(simctrl_modsession_list_t));
        modsession->mod_name = strdup(msg_payload->mod_name);
        modsession->mod_session_id = msg_payload->mod_session_id;
        modsession->zmq_mod_session_id = s->modsession_count++;
        modsession->registered_at = timep;

        // Append it to the front of the state list (keeping the
        // ordering does not matter).
        // TODO: possibly lock this beforehand
        modsession->next = s->modsession_list;
        s->modsession_list = modsession;
    }

    return MSGRET_SUCCESS;

}

static struct ext_module_s ext_mod = {
    "simctrl",
    simctrl_start,
    simctrl_new,
    simctrl_add_pads,
    NULL,
    simctrl_tick,
    simctrl_msg,
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *)) {
    int ret = RC_OK;
    ret = register_module(&ext_mod);
    return ret;
}
