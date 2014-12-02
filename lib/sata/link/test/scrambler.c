// Adapted from SATA specification
/****************************************************************************/
/*                                                                          */
/* scramble.c                                                               */
/*                                                                          */
/* This sample code generates the entire sequence of 65535 Dwords produced  */
/* by the scrambler defined in the Serial ATA specification. The            */
/* specification calls for an LFSR to generate a string of bits that will   */
/* be packaged into 32 bit Dwords to be XORed with the data Dwords. The     */
/* generator polynomial specified is:                                       */
/*         16  15  13  4                                                    */
/* G(x) = x + x + x + x + 1                                                 */
/*                                                                          */
/* Parallelized versions of the scrambler are initialized to a value        */
/* derived from the initialization value of 0xFFFF defined in the           */
/* specification. This implementation is initialized to 0xF0F6. Other       */
/* parallel implementations will have different initial values. The         */
/* important point is that the first Dword output of any implementation     */
/* must equal 0xC2D2768D.                                                   */
/* This code does not represent an elegant solution for a C implementation, */
/* but it does demonstrate a method of generating the sequence that can be  */
/* easily implemented in hardware. A block diagram of the circuit emulated  */
/* by this code is shown below.                                             */
/*                                                                          */
/* +-----------------------------------+                                    */
/* |                                   |                                    */
/* |                                   |                                    */
/* |     +---+                +---+    |                                    */
/* |     | R |                | * |    |                                    */
/* +---->| e |----------+---->| M |----+----> Output(31 downto 16)          */
/*       | g |          |     | 1 |                                         */
/*       +---+          |     +---+                                         */
/*                      |                                                   */
/*                      |     +---+                                         */
/*                      |     | * |                                         */
/*                      +---->| M |---------> Output(15 downto 0)           */
/*                            | 2 |                                         */
/*                            +---+                                         */
/*                                                                          */
/* The register shown in the block diagram is a 16 bit register. The two    */
/* boxes, *M1 and *M2, each represent a multiply by a 16 by 16 binary       */
/* matrix. A 16 by 16 matrix times a 16 bit vector yields a 16 bit vector.  */
/* The two vectors are the two halves of the 32 bit scrambler value. The    */
/* upper half of the scrambler value is stored back into the context        */
/* register to be used to generate the next value in the scrambler          */
/*                                                                          */
/****************************************************************************/
#include <stdlib.h>
#include <stdio.h>
int main(int argc, char *argv[])
{
   int               i, j;
   unsigned int      length;
   unsigned short    context;
   unsigned long     scrambler;
   unsigned char     now[16];
   unsigned char     next[32];
   context = 0xF0F6;

   scanf("0x%8x", &length);

   for (i = 0; i < length; ++i)  {
      for (j = 0; j < 16; ++j)  {
         now[j] = (context >> j) & 0x01;
      }
      next[31] = now[12] ^ now[10] ^ now[7]  ^ now[3]  ^ now[1]  ^ now[0];
      next[30] = now[15] ^ now[14] ^ now[12] ^ now[11] ^ now[9]  ^ now[6]  ^ now[3]  ^ now[2]  ^ now[0];
      next[29] = now[15] ^ now[13] ^ now[12] ^ now[11] ^ now[10] ^ now[8]  ^ now[5]  ^ now[3]  ^ now[2]  ^ now[1];
      next[28] = now[14] ^ now[12] ^ now[11] ^ now[10] ^ now[9]  ^ now[7]  ^ now[4]  ^ now[2]  ^ now[1]  ^ now[0];
      next[27] = now[15] ^ now[14] ^ now[13] ^ now[12] ^ now[11] ^ now[10] ^ now[9]  ^ now[8]  ^ now[6]  ^ now[1]  ^ now[0];
      next[26] = now[15] ^ now[13] ^ now[11] ^ now[10] ^ now[9]  ^ now[8]  ^ now[7]  ^ now[5]  ^ now[3]  ^ now[0];
      next[25] = now[15] ^ now[10] ^ now[9]  ^ now[8]  ^ now[7]  ^ now[6]  ^ now[4]  ^ now[3]  ^ now[2];
      next[24] = now[14] ^ now[9]  ^ now[8]  ^ now[7]  ^ now[6]  ^ now[5]  ^ now[3]  ^ now[2]  ^ now[1];
      next[23] = now[13] ^ now[8]  ^ now[7]  ^ now[6]  ^ now[5]  ^ now[4]  ^ now[2]  ^ now[1]  ^ now[0];
      next[22] = now[15] ^ now[14] ^ now[7]  ^ now[6]  ^ now[5]  ^ now[4]  ^ now[1]  ^ now[0];
      next[21] = now[15] ^ now[13] ^ now[12] ^ now[6]  ^ now[5]  ^ now[4]  ^ now[0];
      next[20] = now[15] ^ now[11] ^ now[5]  ^ now[4];
      next[19] = now[14] ^ now[10] ^ now[4]  ^ now[3];
      next[18] = now[13] ^ now[9]  ^ now[3]  ^ now[2];
      next[17] = now[12] ^ now[8]  ^ now[2]  ^ now[1];
      next[16] = now[11] ^ now[7]  ^ now[1]  ^ now[0];


      next[15] = now[15] ^ now[14] ^ now[12] ^ now[10] ^ now[6]  ^ now[3]  ^ now[0];
      next[14] = now[15] ^ now[13] ^ now[12] ^ now[11] ^ now[9]  ^ now[5]  ^ now[3]  ^ now[2];
      next[13] = now[14] ^ now[12] ^ now[11] ^ now[10] ^ now[8]  ^ now[4]  ^ now[2]  ^ now[1];
      next[12] = now[13] ^ now[11] ^ now[10] ^ now[9]  ^ now[7]  ^ now[3]  ^ now[1]  ^ now[0];
      next[11] = now[15] ^ now[14] ^ now[10] ^ now[9]  ^ now[8]  ^ now[6]  ^ now[3]  ^ now[2]  ^ now[0];
      next[10] = now[15] ^ now[13] ^ now[12] ^ now[9]  ^ now[8]  ^ now[7]  ^ now[5]  ^ now[3]  ^ now[2]  ^ now[1];
      next[9]  = now[14] ^ now[12] ^ now[11] ^ now[8]  ^ now[7]  ^ now[6]  ^ now[4]  ^ now[2]  ^ now[1]  ^ now[0];
      next[8]  = now[15] ^ now[14] ^ now[13] ^ now[12] ^ now[11] ^ now[10] ^ now[7]  ^ now[6]  ^ now[5]  ^ now[1]  ^ now[0];
      next[7]  = now[15] ^ now[13] ^ now[11] ^ now[10] ^ now[9]  ^ now[6]  ^ now[5]  ^ now[4]  ^ now[3]  ^ now[0];
      next[6]  = now[15] ^ now[10] ^ now[9]  ^ now[8]  ^ now[5]  ^ now[4]  ^ now[2];
      next[5]  = now[14] ^ now[9]  ^ now[8]  ^ now[7]  ^ now[4]  ^ now[3]  ^ now[1];
      next[4]  = now[13] ^ now[8]  ^ now[7]  ^ now[6]  ^ now[3]  ^ now[2]  ^ now[0];
      next[3]  = now[15] ^ now[14] ^ now[7]  ^ now[6]  ^ now[5]  ^ now[3]  ^ now[2]  ^ now[1];
      next[2]  = now[14] ^ now[13] ^ now[6]  ^ now[5]  ^ now[4]  ^ now[2]  ^ now[1]  ^ now[0];
      next[1]  = now[15] ^ now[14] ^ now[13] ^ now[5]  ^ now[4]  ^ now[1]  ^ now[0];
      next[0]  = now[15] ^ now[13] ^ now[4]  ^ now[0];

      scrambler = 0;
      for (j = 31; j >= 0; --j)  {
         scrambler = scrambler << 1;
         scrambler |= next[j];
      }
      context = scrambler >> 16;
      printf("%08x\n", (unsigned int) scrambler);

   }

   return 0;

}