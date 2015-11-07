#ifndef __STDINT_H
#define __STDINT_H

#ifdef __cplusplus
extern "C" {
#endif

typedef int intptr_t;
typedef unsigned int uintptr_t;

typedef unsigned long long uint64_t;
typedef unsigned int uint32_t;
typedef unsigned short uint16_t;
typedef unsigned char uint8_t;

typedef long long int64_t;
typedef int int32_t;
typedef short int16_t;
typedef char int8_t;

#define __int_c_join(a, b) a ## b
#define __int_c(v, suffix) __int_c_join(v, suffix)
#define __uint_c(v, suffix) __int_c_join(v##U, suffix)

#define INT64_C(v) __int_c(v, LL)
#define UINT64_C(v) __uint_c(v, LL)
#define INT32_C(v) v
#define UINT32_C(v) v##U

#ifdef __cplusplus
}
#endif

#endif /* __STDINT_H */
