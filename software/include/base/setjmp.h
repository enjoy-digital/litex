#ifndef __SETJMP_H
#define __SETJMP_H

#ifdef __cplusplus
extern "C" {
#endif

#define _JBLEN 19

typedef	int jmp_buf[_JBLEN];

int setjmp(jmp_buf env);
void longjmp(jmp_buf env, int val);

#ifdef __cplusplus
}
#endif

#endif /* __SETJMP_H */
