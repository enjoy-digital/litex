MSCDIR = ../../../
PYTHON = python3

CMD = PYTHONPATH=$(MSCDIR) $(PYTHON)

CC=gcc
CFLAGS =-Wall -O0

crc_tb:
	$(CC) $(CFLAGS) $(INC) -o crc crc.c
	./crc /> crc_ref

scrambler_tb:
	$(CC) $(CFLAGS) $(INC) -o scrambler scrambler.c
	./scrambler /> scrambler_ref

clean:
	rm crc crc_ref scrambler scrambler_ref
