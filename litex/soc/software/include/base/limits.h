#ifndef __LIMITS_H
#define __LIMITS_H

#ifdef __cplusplus
extern "C" {
#endif

#define ULONG_MAX 0xffffffff

#define UINT_MAX 0xffffffff
#define INT_MIN 0x80000000
#define INT_MAX 0x7fffffff

#define USHRT_MAX 0xffff
#define SHRT_MIN 0x8000
#define SHRT_MAX 0x7fff

#define UCHAR_MAX 0xff

#define CHAR_BIT 8

#ifdef __cplusplus
}
#endif

#endif /* __LIMITS_H */
