#ifndef __STDARG_H
#define __STDARG_H

#include <stdlib.h>

#ifdef __cplusplus
extern "C" {
#endif

#define va_start(v, l) __builtin_va_start((v), l)
#define va_arg(ap, type) __builtin_va_arg((ap), type)
#define va_copy(aq, ap) __builtin_va_copy((aq), (ap))
#define va_end(ap) __builtin_va_end(ap)
#define va_list __builtin_va_list

int vsnprintf(char *buf, size_t size, const char *fmt, va_list args);
int vscnprintf(char *buf, size_t size, const char *fmt, va_list args);
int vsprintf(char *buf, const char *fmt, va_list args);

#ifdef __cplusplus
}
#endif

#endif /* __STDARG_H */
