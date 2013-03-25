#ifndef __STDIO_H
#define __STDIO_H

#include <stddef.h>

#ifdef __cplusplus
extern "C" {
#endif

int putchar(int c);
int puts(const char *s);

int snprintf(char *buf, size_t size, const char *fmt, ...);
int scnprintf(char *buf, size_t size, const char *fmt, ...);
int sprintf(char *buf, const char *fmt, ...);

int printf(const char *fmt, ...);

/* Not sure this belongs here... */
typedef long long loff_t;
typedef long off_t;
typedef int mode_t;
typedef int dev_t;

/*
 * Note: this library does not provide FILE operations.
 * User code must implement them.
 */

#ifndef BUFSIZ
#define BUFSIZ 1024
#endif

#ifndef EOF
#define EOF -1
#endif

#ifndef SEEK_SET
#define SEEK_SET	0
#endif

#ifndef SEEK_CUR
#define SEEK_CUR	1
#endif

#ifndef SEEK_END
#define SEEK_END	2
#endif

typedef int FILE;

extern FILE *stdin;
extern FILE *stdout;
extern FILE *stderr;

int fprintf(FILE *stream, const char *format, ...);
int fflush(FILE *stream);

FILE *fopen(const char *path, const char *mode);
FILE *freopen(const char *path, const char *mode, FILE *stream);
char *fgets(char *s, int size, FILE *stream);
size_t fread(void *ptr, size_t size, size_t nmemb, FILE *stream);
size_t fwrite(const void *ptr, size_t size, size_t nmemb, FILE *stream);
int getc(FILE *stream);
int fputc(int c, FILE *stream);
int ferror(FILE *stream);
int feof(FILE *stream);
int fclose(FILE *fp);

int fseek(FILE *stream, long offset, int whence);
long ftell(FILE *stream);

#ifdef __cplusplus
}
#endif

#endif /* __STDIO_H */
