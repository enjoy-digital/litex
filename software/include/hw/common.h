#ifndef __HW_COMMON_H
#define __HW_COMMON_H

#ifdef __ASSEMBLER__
#define MMPTR(x) x
#else
#define MMPTR(x) (*((volatile unsigned int *)(x)))
#endif

#endif
