#ifndef __STDIO_H
#define __STDIO_H

#include <stddef.h>

int putchar(int c);
int puts(const char *s);

int snprintf(char *buf, size_t size, const char *fmt, ...);
int scnprintf(char *buf, size_t size, const char *fmt, ...);
int sprintf(char *buf, const char *fmt, ...);

int printf(const char *fmt, ...);

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

#endif /* __STDIO_H */
