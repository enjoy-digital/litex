/*
 * spiFpga
 * Copyright (C) 2012 by Florent Kermarrec <florent@enjoy-digital.fr>
 * Copyright (C) 2011 by James Bowman <jamesb@excamera.com> 
 *
 */

#ifndef _SF_H_INCLUDED
#define _SF_H_INCLUDED

#ifndef SS_PIN
#define SS_PIN 10
#endif

class SFClass {
public:
  static void begin();
  static void end();
  static void __start(unsigned int addr);
  static void __wstart(unsigned int addr);
  static void __end(void);
  static char rd(unsigned int addr);
  static void wr(unsigned int addr, char v);
};

extern SFClass SF;

#endif
