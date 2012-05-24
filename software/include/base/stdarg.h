#ifndef __STDARG_H
#define __STDARG_H

#include <stdlib.h>

#if (__GNUC__ > 4) || ((__GNUC__ == 4) && (__GNUC_MINOR__ >= 4))
#define va_start(v,l) __builtin_va_start((v),l)
#else
#define va_start(v,l) __builtin_stdarg_start((v),l)
#endif

#define va_arg(ap, type) \
	__builtin_va_arg((ap), type)

#define va_end(ap) \
	__builtin_va_end(ap)

#define va_list \
	__builtin_va_list

int vsnprintf(char *buf, size_t size, const char *fmt, va_list args);
int vscnprintf(char *buf, size_t size, const char *fmt, va_list args);
int vsprintf(char *buf, const char *fmt, va_list args);

#endif /* __STDARG_H */
