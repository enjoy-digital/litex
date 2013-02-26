/*
  Uart2Spi
  Copyright 2012 - Florent Kermarrec - florent@enjoy-digital.fr
  
  Protocol:
  -Write : 0x01 + 16b Addr + 8b Data
  -Read  : 0x02 + 16b Addr + 8b Don't Care

  Todo:
  Support Spi Burst Mode
  
 */
#include <SPI.h>
#include <spiFpga.h>

void setup() {
  SF.begin();
  SPI.setClockDivider(8);
  Serial.begin(115200);
}

int  cmd = 0;

void loop()
{
 if (Serial.available() == 4)
 {
   cmd = Serial.read();
   //Write Cmd
   if (cmd == 0x01)
   {
     char addrMsb = Serial.read();
     char addrLsb = Serial.read();
     char data = Serial.read();
     SF.wr(addrMsb<<8|addrLsb, data);
   }
   //Read Cmd
   if (cmd == 0x02)
   {
     char addrMsb = Serial.read();
     char addrLsb = Serial.read();
     Serial.read();
     char data;
     data = SF.rd(addrMsb<<8|addrLsb);
     Serial.print(data);
   }
   else {
     Serial.flush();
   }
 }
}