/*
 * usbkbd.v
 *
 * Copyright 2020, Gary Wong <gtw@gnu.org>
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in
 *    the documentation and/or other materials provided with the
 *    distribution.
 * 
 * THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
 * "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
 * LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
 * FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
 * COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
 * INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
 * (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
 * SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
 * STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
 * ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED
 * OF THE POSSIBILITY OF SUCH DAMAGE.
 */

#include <generated/mem.h>
#include <string.h>

#ifdef VIDEOCHAR_BASE

#include <console.h>
#include <videochar.h>

static void clear( void ) {
    
    memset( (char *) VIDEOCHAR_BASE, 0, 0x2000 );
}

static void videochar_write( char c ) {

    static int x = 0, y = 12;
    static int attr = 0x02;
    static short *const screen = (short *) VIDEOCHAR_BASE;
    static int esc, csi, param;

    if( csi ) {
	if( c >= '0' && c <= '9' ) {
	    param = param * 10 + c - '0';
	    return;	    
	} else if( c == ';' ) {
	    param = 0;
	    return;
	}

	switch( c ) {
	case 'A': /* CUU */
	    y -= param ? param : 1;
	    if( y < 0 )
		y = 0;

	    break;
	    
	case 'B': /* CUD */
	    y += param ? param : 1;
	    if( y > 27 )
		y = 27;

	    break;

	case 'C': /* CUF */
	    x += param ? param : 1;
	    if( x > 99 )
		x = 99;

	    break;

	case 'D': /* CUB */
	    x -= param ? param : 1;
	    if( x < 0 )
		x = 0;

	    break;

	case 'H': /* CUP: parameters not implemented */
	    x = y = 0;
	    break;
	    
	case 'J': /* ED: parameters not implemented */
	    clear();
	    break;
	    
	case 'm': /* SGR */
	    if( !param )
		attr = 0x02;
	    else if( param == 1 )
		attr |= 0x08;
	    else if( param == 2 )
		attr &= ~0x08;
	    else if( param == 7 )
		attr = ( ( attr & 0xF0 ) >> 4 ) | ( ( attr & 0x0F ) << 4 );
	    else if( param >= 30 && param <= 37 )
		attr = ( attr & ~0x0F ) | ( param - 30 );
	    else if( param >= 40 && param <= 47 )
		attr = ( attr & ~0xF0 ) | ( ( param - 40 ) << 4 );
	    
	    break;
	}

	csi = 0;

	return;
    }
    
    if( esc ) {	
	esc = c == 0x1B;
	if( ( csi = c == '[' ) ) /* many other sequences are defined,
				    but we ignore them */
	    param = 0;
	
	return;
    }
    
    switch( c ) {
	/* \a should beep */
	
    case '\b':
	if( x )
	    x--;
	
	return;

    case '\t':
	if( x < 0xF8 )
	    x = ( x + 8 ) & 0xF8;
	
	return;
	
    case '\n':
	y++;

	if( y > 27 ) {
	    memmove( (char *) VIDEOCHAR_BASE + 0xC00,
		     (char *) VIDEOCHAR_BASE + 0xD00,
		     0xF00 );
	    memset( (char *) VIDEOCHAR_BASE + ( 27 << 8 ), 0, 0x100 );
	    
	    y = 27;
	}
	
	return;
	
    case '\r':
	x = 0;
	return;

	/* 0x0E (SO) should change character set */
	/* 0x0F (SI) should change character set */

	/* 0x18 (CAN) and 0x1A (SUB) should abort escape sequence */
	
    case '\e':
	esc = 1;
	return;	
    }

    if( x < 0x80 )
	screen[ ( y << 7 ) + x++ ] = c | ( attr << 8 );
}

extern void videochar_init( void ) {

    console_set_write_hook( videochar_write );
}

#endif
