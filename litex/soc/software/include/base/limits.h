#ifndef __LIMITS_H
#define __LIMITS_H

#ifdef __cplusplus
extern "C" {
#endif

#ifdef __LP64__
#define ULONG_MAX	18446744073709551615UL
#else
#define ULONG_MAX	4294967295UL
#endif

#define UINT_MAX	4294967295U
#define INT_MIN		(-INT_MAX - 1)
#define INT_MAX		2147483647

#define USHRT_MAX	65535
#define SHRT_MIN	(-32768)
#define SHRT_MAX	32767

#define UCHAR_MAX	255

#define CHAR_BIT 8

#ifdef __cplusplus
}
#endif

#endif /* __LIMITS_H */
