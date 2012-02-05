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
 
/* WARNING: This tool is little endian in 16-bit mode 
 * and big endian in 32-bit mode. 
 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>

int main(int argc, char *argv[])
{
	int i;
	int pad;
	FILE *fdi, *fdo;
	unsigned char w[4];
	int mode16;
	
	if((argc != 4) && (argc != 5)) {
		fprintf(stderr, "Usage: bin2hex <infile> <outfile> <size> [16]\n");
		return 1;
	}
	pad = atoi(argv[3]);
	if(pad <= 0) {
		fprintf(stderr, "Incorrect size\n");
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
	mode16 = (argc == 5) && (strcmp(argv[4], "16") == 0);
	if(mode16) {
		while(1) {
			if(fread(w, 2, 1, fdi) <= 0) break;
			fprintf(fdo, "%02hhx%02hhx\n", w[1], w[0]);
			pad--;
		}
	} else {
		while(1) {
			if(fread(w, 4, 1, fdi) <= 0) break;
			fprintf(fdo, "%02hhx%02hhx%02hhx%02hhx\n", w[0], w[1], w[2], w[3]);
			pad--;
		}
	}
	fclose(fdi);
	if(pad<0)
		fprintf(stderr, "Warning: Input binary is larger than specified size\n");
	if(mode16) {
		for(i=0;i<pad;i++)
			fprintf(fdo, "0000\n");
	} else {
		for(i=0;i<pad;i++)
			fprintf(fdo, "00000000\n");
	}
	if(fclose(fdo) != 0) {
		perror("Unable to close output file");
		return 1;
	}
	return 0;
}
