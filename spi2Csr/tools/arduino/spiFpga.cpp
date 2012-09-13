/*
 * spiFpga
 * Copyright (C) 2012 by Florent Kermarrec <florent@enjoy-digital.fr>
 * Copyright (C) 2011 by James Bowman <jamesb@excamera.com> 
 *
 */
 
#include "WProgram.h"
#include <avr/pgmspace.h>
#include <SPI.h>
#include <spiFpga.h>

SFClass SF;

void SFClass::begin()
{
	pinMode(SS_PIN, OUTPUT);
	SPI.begin();
	SPI.setClockDivider(SPI_CLOCK_DIV2);
	SPI.setBitOrder(MSBFIRST);
	SPI.setDataMode(SPI_MODE0);
	SPSR = (1 << SPI2X);
	digitalWrite(SS_PIN, HIGH);
}

void SFClass::end() {
}

void SFClass::__start(unsigned int addr)
{
	digitalWrite(SS_PIN, LOW);
	SPI.transfer(highByte(addr));
	SPI.transfer(lowByte(addr));  
}

void SFClass::__wstart(unsigned int addr)
{
	__start(0x8000|addr);
}

void SFClass::__end()
{
	digitalWrite(SS_PIN, HIGH);
}

char SFClass::rd(unsigned int addr)
{
	__start(addr);
	char r = SPI.transfer(0);
	__end();
	return r;
}

void SFClass::wr(unsigned int addr, char v)
{
	__wstart(addr);
	SPI.transfer(v);
	__end();
}