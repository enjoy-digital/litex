#ifndef __CONSOLE_H
#define __CONSOLE_H

#ifdef __cplusplus
extern "C" {
#endif

#define readchar getchar
#define putsnonl(X) fputs(X, stdout)

int readchar_nonblock(void);

#ifdef __cplusplus
}
#endif

#endif /* __CONSOLE_H */
