/*
 * Milkymist SoC (Software)
 * Copyright (C) 2007, 2008, 2009 Sebastien Bourdeauducq
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

#include "softfloat.h"

/*
 * 'Equal' wrapper. This returns 0 if the numbers are equal, or (1 | -1)
 * otherwise. So we need to invert the output.
 */
int __eqsf2(float32 a, float32 b)
{
	return !float32_eq(a, b);
}

/*
 * 'Not Equal' wrapper. This returns -1 or 1 (say, 1!) if the numbers are
 * not equal, 0 otherwise. However no not equal call is provided, so we have
 * to use an 'equal' call and invert the result. The result is already
 * inverted though! Confusing?!
 */
int __nesf2(float32 a, float32 b)
{
	return !float32_eq(a, b);
}

/*
 * 'Greater Than' wrapper. This returns 1 if the number is greater, 0
 * or -1 otherwise. Unfortunately, no such function exists. We have to
 * instead compare the numbers using the 'less than' calls in order to
 * make up our mind. This means that we can call 'less than or equal' and
 * invert the result.
 */
int __gtsf2(float32 a, float32 b)
{
	return !float32_le(a, b);
}

/*
 * 'Greater Than or Equal' wrapper. We emulate this by inverting the result
 * of a 'less than' call.
 */
int __gesf2(float32 a, float32 b)
{
	return !float32_lt(a, b);
}

/*
 * 'Less Than' wrapper.
 */
int __ltsf2(float32 a, float32 b)
{
	return float32_lt(a, b);
}

/*
 * 'Less Than or Equal' wrapper. A 0 must turn into a 1, and a 1 into a 0.
 */
int __lesf2(float32 a, float32 b)
{
	return !float32_le(a, b);
}

/*
 * Float negate... This isn't provided by the library, but it's hardly the
 * hardest function in the world to write... :) In fact, because of the
 * position in the registers of arguments, the double precision version can
 * go here too ;-)
 */
float32 __negsf2(float32 x)
{
	return x ^ 0x80000000;
}

/*
 * 32-bit operations.
 */
float32 __addsf3(float32 a, float32 b)
{
	return float32_add(a, b);
}

float32 __subsf3(float32 a, float32 b)
{
	return float32_sub(a, b);
}

float32 __mulsf3(float32 a, float32 b)
{
	return float32_mul(a, b);
}

float32 __divsf3(float32 a, float32 b)
{
	return float32_div(a, b);
}

float32 __floatsisf(int x)
{
	return int32_to_float32(x);
}

int __fixsfsi(float32 x)
{
	return float32_to_int32_round_to_zero(x);
}

unsigned int __fixunssfsi(float32 x)
{
	return float32_to_int32_round_to_zero(x); // XXX
}

