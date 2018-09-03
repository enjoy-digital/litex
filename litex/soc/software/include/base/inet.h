/* Copyright © 2005-2014 Rich Felker, et al.
 *
 * Permission is hereby granted, free of charge, to any person obtaining
 * a copy of this software and associated documentation files (the
 * "Software"), to deal in the Software without restriction, including
 * without limitation the rights to use, copy, modify, merge, publish,
 * distribute, sublicense, and/or sell copies of the Software, and to
 * permit persons to whom the Software is furnished to do so, subject to
 * the following conditions:
 *
 * The above copyright notice and this permission notice shall be
 * included in all copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
 * EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
 * MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
 * IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
 * CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
 * TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
 * SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
 */

#ifndef __INET_H
#define __INET_H

#include <stdint.h>

static __inline uint16_t __bswap_16(uint16_t __x)
{
	return (__x<<8) | (__x>>8);
}

static __inline uint32_t __bswap_32(uint32_t __x)
{
	return (__x>>24) | ((__x>>8)&0xff00) | ((__x<<8)&0xff0000) | (__x<<24);
}

static __inline uint64_t __bswap_64(uint64_t __x)
{
	return (__bswap_32(__x)+(0ULL<<32)) | __bswap_32(__x>>32);
}

#define bswap_16(x) __bswap_16(x)
#define bswap_32(x) __bswap_32(x)
#define bswap_64(x) __bswap_64(x)

uint16_t htons(uint16_t n);
uint32_t htonl(uint32_t n);
uint16_t ntohs(uint16_t n);
uint32_t ntohl(uint32_t n);

#endif /* __INET_H */
