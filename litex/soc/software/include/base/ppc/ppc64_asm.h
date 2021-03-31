/*
 * OpenPOWER Common Assembly Interfaces
 * Copyright (C) 2021 Raptor Engineering, LLC <sales@raptorengineering.com>
 *
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, version 3 of the License.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

#ifndef _PPC64_ASM_H_
#define _PPC64_ASM_H_

#include <stdint.h>

static inline void mtmsrd(uint64_t val)
{
	__asm__ volatile("mtmsrd %0" : : "r" (val) : "memory");
}

static inline uint64_t mfmsr(void)
{
	uint64_t rval;
	__asm__ volatile("mfmsr %0" : "=r" (rval) : : "memory");
	return rval;
}

static inline void mtdec(uint64_t val)
{
	__asm__ volatile("mtdec %0" : : "r" (val) : "memory");
}

static inline uint64_t mfdec(void)
{
	uint64_t rval;
	__asm__ volatile("mfdec %0" : "=r" (rval) : : "memory");
	return rval;
}

#endif // _PPC64_ASM_H_
