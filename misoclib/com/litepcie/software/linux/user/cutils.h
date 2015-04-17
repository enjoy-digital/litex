#include <inttypes.h>
#include <math.h>
#include <immintrin.h>

#ifndef _BOOL_defined
#define _BOOL_defined
#undef FALSE
#undef TRUE

typedef int BOOL;
enum {
    FALSE = 0,
    TRUE = 1,
};
#endif

static inline int sub_mod_int(int a, int b, int m)
{
    a -= b;
    if (a < 0)
        a += m;
    return a;
}

static inline int add_mod_int(int a, int b, int m)
{
    a += b;
    if (a >= m)
        a -= m;
    return a;
}
