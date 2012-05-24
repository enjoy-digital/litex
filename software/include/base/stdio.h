#ifndef __STDIO_H
#define __STDIO_H

#include <stdlib.h>

int putchar(int c);
int puts(const char *s);

int snprintf(char *buf, size_t size, const char *fmt, ...);
int scnprintf(char *buf, size_t size, const char *fmt, ...);
int sprintf(char *buf, const char *fmt, ...);

int printf(const char *fmt, ...);

#endif /* __STDIO_H */
