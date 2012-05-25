#ifndef __SETJMP_H
#define __SETJMP_H

#define _JBLEN 19

typedef	int jmp_buf[_JBLEN];

int setjmp(jmp_buf env);
void longjmp(jmp_buf env, int val);

#endif /* __SETJMP_H */

