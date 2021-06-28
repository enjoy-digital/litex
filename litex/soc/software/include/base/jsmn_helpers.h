#ifndef __JSMN_HELPERS_H__
#define __JSMN_HELEPRS_H__

#define JSMN_HEADER
#include "jsmn.h"

int print_tokens(char *json_buffer, const char *searched);
int json_token_check(const char *json_buffer, jsmntok_t *token, const char *searched);

#endif
