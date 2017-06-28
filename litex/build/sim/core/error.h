/* Copyright (C) 2017 LambdaConcept */

#ifndef __ERROR_H_
#define __ERROR_H_

#define RC_OK 0
#define RC_ERROR -1
#define RC_INVARG -2
#define RC_NOENMEM -3
#define RC_JSERROR -4

#define eprintf(format, ...) fprintf (stderr, "%s:%d "format, __FILE__, __LINE__,  ##__VA_ARGS__)

#endif
