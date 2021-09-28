/* This file contains functions that were missing
 * during picolibc compilation. They are only stubs
 * and should be probably replaced with more
 * meaningful versions.
 */

#include <stddef.h>
#include <errno.h>

int getentropy(void *v, size_t s) {
    return -1;
}

int getpid(void) {
    return 1;
}

void _exit(int code) {
    while (1);
}

int kill(int pid, int name) {
    _exit(0);
    return 0;
}

void *_impure_ptr;
