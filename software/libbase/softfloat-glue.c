/*	$NetBSD: fplib_glue.c,v 1.2 2000/02/22 01:18:28 mycroft Exp $	*/

/*-
 * Copyright (c) 1997 The NetBSD Foundation, Inc.
 * All rights reserved.
 *
 * This code is derived from software contributed to The NetBSD Foundation
 * by Neil A. Carson and Mark Brinicombe
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. All advertising materials mentioning features or use of this software
 *    must display the following acknowledgement:
 *	This product includes software developed by the NetBSD
 *	Foundation, Inc. and its contributors.
 * 4. Neither the name of The NetBSD Foundation nor the names of its
 *    contributors may be used to endorse or promote products derived
 *    from this software without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE NETBSD FOUNDATION, INC. AND CONTRIBUTORS
 * ``AS IS'' AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
 * TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
 * PURPOSE ARE DISCLAIMED.  IN NO EVENT SHALL THE FOUNDATION OR CONTRIBUTORS
 * BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
 * CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
 * SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
 * INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
 * CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
 * POSSIBILITY OF SUCH DAMAGE.
 */

#include "milieu.h"
#include "softfloat.h"

int __eqsf2(float32 a,float32 b);
int __eqdf2(float64 a,float64 b);
int __nesf2(float32 a,float32 b);
int __nedf2(float64 a,float64 b);
int __gtsf2(float32 a,float32 b);
int __gtdf2(float64 a,float64 b);
int __gesf2(float32 a,float32 b);
int __gedf2(float64 a,float64 b);
int __ltsf2(float32 a,float32 b);
int __ltdf2(float64 a,float64 b);
int __lesf2(float32 a,float32 b);
int __ledf2(float64 a,float64 b);
float32 __negsf2(float32 a);
float64 __negdf2(float64 a);

/********************************* COMPARISONS ********************************/

/*
 * 'Equal' wrapper. This returns 0 if the numbers are equal, or (1 | -1)
 * otherwise. So we need to invert the output.
 */

int __eqsf2(float32 a,float32 b) {
	return float32_eq(a,b)?0:1;
}

int __eqdf2(float64 a,float64 b) {
	return float64_eq(a,b)?0:1;
}

/*
 * 'Not Equal' wrapper. This returns -1 or 1 (say, 1!) if the numbers are
 * not equal, 0 otherwise. However no not equal call is provided, so we have
 * to use an 'equal' call and invert the result. The result is already
 * inverted though! Confusing?!
 */
int __nesf2(float32 a,float32 b) {
	return float32_eq(a,b)?0:-1;
}

int __nedf2(float64 a,float64 b) {
	return float64_eq(a,b)?0:-1;
}

/*
 * 'Greater Than' wrapper. This returns 1 if the number is greater, 0
 * or -1 otherwise. Unfortunately, no such function exists. We have to
 * instead compare the numbers using the 'less than' calls in order to
 * make up our mind. This means that we can call 'less than or equal' and
 * invert the result.
 */
int __gtsf2(float32 a,float32 b) {
	return float32_le(a,b)?0:1;
}

int __gtdf2(float64 a,float64 b) {
	return float64_le(a,b)?0:1;
}

/*
 * 'Greater Than or Equal' wrapper. We emulate this by inverting the result
 * of a 'less than' call.
 */
int __gesf2(float32 a,float32 b) {
	return float32_lt(a,b)?-1:0;
}

int __gedf2(float64 a,float64 b) {
	return float64_lt(a,b)?-1:0;
}

/*
 * 'Less Than' wrapper. A 1 from the ARM code needs to be turned into -1.
 */
int __ltsf2(float32 a,float32 b) {
	return float32_lt(a,b)?-1:0;
}

int __ltdf2(float64 a,float64 b) {
	return float64_lt(a,b)?-1:0;
}

/*
 * 'Less Than or Equal' wrapper. A 0 must turn into a 1, and a 1 into a 0.
 */
int __lesf2(float32 a,float32 b) {
	return float32_le(a,b)?0:1;
}

int __ledf2(float64 a,float64 b) {
	return float64_le(a,b)?0:1;
}

/*
 * Float negate... This isn't provided by the library, but it's hardly the
 * hardest function in the world to write... :) In fact, because of the
 * position in the registers of arguments, the double precision version can
 * go here too ;-)
 */
float32 __negsf2(float32 a) {
	return (a ^ 0x80000000);
}

float64 __negdf2(float64 a) {
	a.high ^= 0x80000000;
	return a;
}

/*
 * 32-bit operations. This is not BSD code.
 */
float32 __addsf3(float32 a, float32 b);
float32 __addsf3(float32 a, float32 b)
{
	return float32_add(a, b);
}

float32 __subsf3(float32 a, float32 b);
float32 __subsf3(float32 a, float32 b)
{
	return float32_sub(a, b);
}

float32 __mulsf3(float32 a, float32 b);
float32 __mulsf3(float32 a, float32 b)
{
	return float32_mul(a, b);
}

float32 __divsf3(float32 a, float32 b);
float32 __divsf3(float32 a, float32 b)
{
	return float32_div(a, b);
}

float32 __floatsisf(int32 x);
float32 __floatsisf(int32 x)
{
	return int32_to_float32(x);
}

float32 __floatunsisf(int32 x);
float32 __floatunsisf(int32 x)
{
	return int32_to_float32(x); // XXX
}

int32 __fixsfsi(float32 x);
int32 __fixsfsi(float32 x)
{
	return float32_to_int32_round_to_zero(x);
}

uint32 __fixunssfsi(float32 x);
uint32 __fixunssfsi(float32 x)
{
	return float32_to_int32_round_to_zero(x); // XXX
}

flag __unordsf2(float32 a, float32 b);
flag __unordsf2(float32 a, float32 b)
{
	/*
	 * The comparison is unordered if either input is a NaN.
	 * Test for this by comparing each operand with itself.
	 * We must perform both comparisons to correctly check for
	 * signalling NaNs.
	 */
	return 1 ^ (float32_eq(a, a) & float32_eq(b, b));
}

/*
 * 64-bit operations. This is not BSD code.
 */
float64 __adddf3(float64 a, float64 b);
float64 __adddf3(float64 a, float64 b)
{
	return float64_add(a, b);
}

float64 __subdf3(float64 a, float64 b);
float64 __subdf3(float64 a, float64 b)
{
	return float64_sub(a, b);
}

float64 __muldf3(float64 a, float64 b);
float64 __muldf3(float64 a, float64 b)
{
	return float64_mul(a, b);
}

float64 __divdf3(float64 a, float64 b);
float64 __divdf3(float64 a, float64 b)
{
	return float64_div(a, b);
}

float64 __floatsidf(int32 x);
float64 __floatsidf(int32 x)
{
	return int32_to_float64(x);
}

float64 __floatunsidf(int32 x);
float64 __floatunsidf(int32 x)
{
	return int32_to_float64(x); // XXX
}

int32 __fixdfsi(float64 x);
int32 __fixdfsi(float64 x)
{
	return float64_to_int32_round_to_zero(x);
}

uint32 __fixunsdfsi(float64 x);
uint32 __fixunsdfsi(float64 x)
{
	return float64_to_int32_round_to_zero(x); // XXX
}

flag __unorddf2(float64 a, float64 b);
flag __unorddf2(float64 a, float64 b)
{
	/*
	 * The comparison is unordered if either input is a NaN.
	 * Test for this by comparing each operand with itself.
	 * We must perform both comparisons to correctly check for
	 * signalling NaNs.
	 */
	return 1 ^ (float64_eq(a, a) & float64_eq(b, b));
}
