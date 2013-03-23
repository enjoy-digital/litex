#ifndef __STDDEF_H
#define __STDDEF_H

#ifdef __cplusplus
#define NULL 0
#else
#define NULL ((void *)0)
#endif

typedef unsigned long size_t;
typedef long ptrdiff_t;

#define offsetof(s,m) (size_t)&(((s *)0)->m)

#endif /* __STDDEF_H */
