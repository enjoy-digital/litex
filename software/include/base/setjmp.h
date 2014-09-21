#ifndef __SETJMP_H
#define __SETJMP_H

#ifdef __cplusplus
extern "C" {
#endif

typedef	void *jmp_buf[5];

#define setjmp __builtin_setjmp
#define longjmp __builtin_longjmp

#ifdef __cplusplus
}
#endif

#endif /* __SETJMP_H */
