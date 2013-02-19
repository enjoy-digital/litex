/*
 * Milkymist SoC
 * Copyright (C) 2007, 2008, 2009, 2010 Sebastien Bourdeauducq
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

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int main(int argc, char *argv[])
{
	FILE *fdi, *fdo;
	unsigned short wi;
	unsigned short wo;
	int i;
	
	if(argc != 3) {
		fprintf(stderr, "Usage: byteswap <infile> <outfile>\n");
		return 1;
	}
	fdi = fopen(argv[1], "rb");
	if(!fdi) {
		perror("Unable to open input file");
		return 1;
	}
	fdo = fopen(argv[2], "w");
	if(!fdo) {
		perror("Unable to open output file");
		fclose(fdi);
		return 1;
	}
	while(1) {
		if(fread(&wi, 2, 1, fdi) <= 0) break;
		wo = 0;
		for(i=0;i<16;i++)
			if(wi & (1 << i))
				wo |= (0x8000 >> i);
		/* comment out the next line on big endian machines! */
		wo = ((wo & 0x00ff) << 8) | ((wo & 0xff00) >> 8);
		fwrite(&wo, 2, 1, fdo);
	}
	fclose(fdi);
	if(fclose(fdo) != 0) {
		perror("Unable to close output file");
		return 1;
	}
	return 0;
}
