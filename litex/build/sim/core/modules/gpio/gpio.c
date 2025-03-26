/**
 * GPIO module for interfacing with external applications through generic I/O
 * signals.
 *
 * This module does little on its own, but can be controlled through the
 * simctrl-style interface. This interface allows to drive pins and query their
 * configuration (input/output) as well as output value.
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


#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "error.h"

#include <json-c/json.h>
#include "modules.h"

typedef struct {
    // Simulation signals and signal attributes
    uint64_t *sim_gpio_oe;
    uint64_t *sim_gpio_o;
    uint64_t *sim_gpio_i;
    size_t sim_gpio_length;
    uint8_t *sim_sys_clk;
} gpio_state_t;

static struct event_base *base = NULL;
static void *sim_handle = NULL;

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

static int gpio_start(void *b, void* sh) {
    base = (struct event_base *) b;
    fprintf(stderr, "[gpio] loaded (libevent base: %p, sim_handle: %p)\n",
            base, sim_handle);
    return RC_OK;
}

static int gpio_new(void **state, char *args) {
    int res = RC_OK;
    gpio_state_t *s = NULL;

    if (!state) {
        res = RC_INVARG;
        goto out;
    }

    s = malloc(sizeof(gpio_state_t));
    if (!s) {
        res = RC_NOENMEM;
        goto out;
    }

    // Initialize all fields of the gpio_state

    // Register this session
    *state = (void*) s;

    // Everything worked, keep all allocated structures
    goto out;

//free_gpio_state:
    free(s);

out:
    return res;
}

static int gpio_add_pads(void *state, struct pad_list_s *plist) {
    int ret = RC_OK;
    gpio_state_t *s = state;
    bool length_set = false;

    if(!state || !plist) {
        ret = RC_INVARG;
        goto out;
    }

    if(!strcmp(plist->name, "gpio")) {
        for (int i = 0; plist->pads[i].name; i++) {
            if (strcmp(plist->pads[i].name, "oe") == 0) {
                s->sim_gpio_oe = plist->pads[i].signal;
            } else if (strcmp(plist->pads[i].name, "o") == 0) {
                s->sim_gpio_o = plist->pads[i].signal;
            } else if (strcmp(plist->pads[i].name, "i") == 0) {
                s->sim_gpio_i = plist->pads[i].signal;
            } else {
                // If we match neither, don't execute the code below
                continue;
            }

            if (length_set) {
                // Alright, we've set the length in the state
                // once. Assert that all other signals have the same
                // length, otherwise print an error.
                if (plist->pads[i].len != s->sim_gpio_length) {
                    fprintf(stderr, "[gpio]: GPIO signals have different "
                            "lengths: %ld vs %ld. Can't reasonably handle "
                            "this, expect weird behavior!\n",
                            plist->pads[i].len, s->sim_gpio_length);
                }
            } else {
                // The GPIO signal length has not been set. Check that
                // it's below 64 (otherwise cap it and print an error)
                // and set it.
                if (plist->pads[i].len > 64) {
                    fprintf(stderr, "[gpio]: can't handle GPIO wider than 64 "
                            "bits. capping at 64 controllable IOs.\n");
                    s->sim_gpio_length = 64;
                } else {
                    s->sim_gpio_length = plist->pads[i].len;
                }
            }
        }
    }

    if (!strcmp(plist->name, "sys_clk")) {
        for (int i = 0; plist->pads[i].name; i++) {
            if (strcmp(plist->pads[i].name, "sys_clk") == 0) {
                s->sim_sys_clk = (uint8_t*) plist->pads[i].signal;
            }
        }
    }

 out:
    return ret;
}

static int gpio_tick(void *state, uint64_t time_ps) {
    return RC_OK;
}

static void gpio_simctrl_report_error(json_object *response_obj,
                                      const char *err,
                                      json_object *additional_information) {
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
        // information such that it will survive the round trip
        // through simctrl and can be freed on the
        // MODMSG_SIMCTRL_RETFREE.
        json_object_get(additional_information);
        json_object_object_add(response_obj, "additional_information",
                               additional_information);
    }
}

static msg_return_t gpio_msg(void *state, uint32_t msg_op, void *data,
                             void **retdata) {
    msg_return_t msg_ret = MSGRET_SUCCESS;
    gpio_state_t *s = state;

    if (msg_op == MODMSG_OP_SIMCTRL_REQ) {
        // For this message type, we expect a simctrl_msg_t in
        // data. This contains an opaque data pointer and length. The
        // sim control module has done bounds checking on the
        // underlying array for us, we can thus trust the
        // length. However, it might not be a null-terminated string
        // and we can't necessarily just set one byte past the last
        // one to null, as it may overrun the underlying buffer.
        simctrl_msg_t *message = data;

        // We always expect JSON for this module, thus try to parse it
        json_tokener *tokener = json_tokener_new();
        json_object *request_obj =
            json_tokener_parse_ex(tokener, message->data, message->len);

        // The parsing will not succeed without a null byte. If the
        // string just didn't contain that but was otherwise valid,
        // throw it in as well.
        if (request_obj == NULL
            && json_tokener_get_error(tokener) == json_tokener_continue) {
            const char null = '\0';
            request_obj = json_tokener_parse_ex(tokener, &null, 1);
        }

        // Generic response object for every request type
        json_object *response_obj = json_object_new_object();

        // Now check whether we've got a valid object
        if (request_obj == NULL) {
            enum json_tokener_error err = json_tokener_get_error(tokener);
            const char* errdesc = json_tokener_error_desc(err);
            json_object *addinfo = json_object_new_object();
            json_object_object_add(addinfo, "description",
                                   json_object_new_string(errdesc));
            gpio_simctrl_report_error(response_obj, "payload_parse_error",
                                      addinfo);
            msg_ret = MSGRET_FAIL;
            // Safe to remove this reference, we've increased the
            // reference count in the report_error function
            json_object_put(addinfo);
            goto report_error;
        }

        // Okay, parsing worked, let's see whether we know the type
        json_object *request_type;
        json_bool type_present = json_object_object_get_ex(request_obj, "_type",
                                                           &request_type);
        if (!type_present) {
            gpio_simctrl_report_error(response_obj, "payload_missing_type",
                                      NULL);
            msg_ret = MSGRET_FAIL;
            goto report_error;
        }
        if (!json_object_is_type(request_type, json_type_string)) {
            gpio_simctrl_report_error(response_obj, "payload_type_not_a_string",
                                      NULL);
            msg_ret = MSGRET_FAIL;
            goto report_error;
        }
        const char *request_type_str = json_object_get_string(request_type);

        if (strcmp(request_type_str, "gpio_count") == 0) {
            json_object_object_add(response_obj, "_type",
                                   json_object_new_string("gpio_count"));
            json_object_object_add(response_obj, "gpio_count",
                                   json_object_new_int64(s->sim_gpio_length));
        } else if (strcmp(request_type_str, "set_input") == 0) {
            // Extract the GPIO index
            json_object *gpio_index;
            json_bool gpio_index_present =
                json_object_object_get_ex(request_obj, "gpio_index",
                                          &gpio_index);
            if (!gpio_index_present) {
                gpio_simctrl_report_error(response_obj, "gpio_index_missing",
                                          NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }
            if (!json_object_is_type(gpio_index, json_type_int)) {
                gpio_simctrl_report_error(response_obj, "gpio_index_not_an_int",
                                          NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }
            uint64_t gpio_index_int = json_object_get_int64(gpio_index);

            // Check whether the gpio_index is within the GPIO count bounds
            if (gpio_index_int > s->sim_gpio_length) {
                gpio_simctrl_report_error(response_obj,
                                          "gpio_index_out_of_bounds", NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }

            // Extract the target GPIO input state
            json_object *input_state;
            json_bool input_state_present =
                json_object_object_get_ex(request_obj, "state", &input_state);
            if (!input_state_present) {
                gpio_simctrl_report_error(response_obj, "input_state_missing",
                                          NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }
            if (!json_object_is_type(input_state, json_type_boolean)) {
                gpio_simctrl_report_error(response_obj,
                                          "input_state_not_a_bool",
                                          NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }
            json_bool input_state_bool = json_object_get_boolean(input_state);

            // Set the input state in the simulation IOs
            *s->sim_gpio_i &= ~(1 << gpio_index_int);
            *s->sim_gpio_i |= input_state_bool << gpio_index_int;

            // Report a success, without a payload
            json_object_put(response_obj);
            response_obj = NULL;
        } else if (strcmp(request_type_str, "get_state") == 0) {
            // Extract the GPIO index
            json_object *gpio_index;
            json_bool gpio_index_present =
                json_object_object_get_ex(request_obj, "gpio_index",
                                          &gpio_index);
            if (!gpio_index_present) {
                gpio_simctrl_report_error(response_obj, "gpio_index_missing",
                                          NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }
            if (!json_object_is_type(gpio_index, json_type_int)) {
                gpio_simctrl_report_error(response_obj, "gpio_index_not_an_int",
                                          NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }
            uint64_t gpio_index_int = json_object_get_int64(gpio_index);

            // Check whether the gpio_index is within the GPIO count bounds
            if (gpio_index_int > s->sim_gpio_length) {
                gpio_simctrl_report_error(response_obj,
                                          "gpio_index_out_of_bounds", NULL);
                msg_ret = MSGRET_FAIL;
                goto report_error;
            }

            // Extract the current GPIO state
            json_bool output_enabled =
                (*s->sim_gpio_oe >> gpio_index_int) & 0b1;
            json_bool gpio_state = (output_enabled)
                ? (*s->sim_gpio_o >> gpio_index_int) & 0b1
                : (*s->sim_gpio_i >> gpio_index_int) & 0b1;
            const char *driven_by = (output_enabled) ? "output" : "input";

            // Add the appropriate fields to the JSON
            json_object_object_add(response_obj, "_type",
                                   json_object_new_string("get_state"));
            json_object_object_add(response_obj, "gpio_index",
                                   json_object_new_int64(gpio_index_int));
            json_object_object_add(response_obj, "driven_by",
                                   json_object_new_string(driven_by));
            json_object_object_add(response_obj, "state",
                                   json_object_new_boolean(gpio_state));
        } else {
            gpio_simctrl_report_error(response_obj, "payload_unknown_type",
                                      NULL);
            msg_ret = MSGRET_FAIL;
        }

    report_error:

        if (response_obj != NULL) {
            // Allocate a new simctrl_msg_t to contain a pointer to the data,
            // the length and a our reference to the top-level json-c object
            // for freeing later.
            simctrl_msg_t *retmsg = malloc(sizeof(simctrl_msg_t));
            const char *encoded = json_object_to_json_string(response_obj);
            retmsg->data = (void*) encoded;
            retmsg->len = strlen(encoded);
            // By convention, all of the gpio retdata objects contain the
            // top-level json-c object as their retdata_private field.
            retmsg->retdata_private = (void*) response_obj;
            *retdata = (void*) retmsg;
        }

        if (request_obj != NULL) {
            json_object_put(request_obj);
        }

        if (tokener != NULL) {
            json_tokener_free(tokener);
        }
    } else if (msg_op == MODMSG_OP_SIMCTRL_RETFREE) {
        // This message is sent whenever we've passed back some non-NULL retdata
        // to the simctrl module. The retdata is then passed in as data. By
        // convention, the data.data will always contain the JSON response
        // string, and data.retdata_private is a handle of the json-c object
        // holding that string. Thus we just need to free that.
        simctrl_msg_t *retmsg = data;
        json_object_put((json_object *) retmsg->retdata_private);

        // Now, free the container holding this data
        free(retmsg);
    } else {
        msg_ret = MSGRET_INVALID_OP;
    }

    return msg_ret;
}

static struct ext_module_s ext_mod = {
    "gpio",
    gpio_start,
    gpio_new,
    gpio_add_pads,
    NULL,
    gpio_tick,
    gpio_msg,
};

int litex_sim_ext_module_init(int (*register_module)(struct ext_module_s *)) {
    int ret = RC_OK;
    ret = register_module(&ext_mod);
    return ret;
}
