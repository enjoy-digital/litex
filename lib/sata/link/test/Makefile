MSCDIR = ../../../../
PYTHON = python3

CMD = PYTHONPATH=$(MSCDIR) $(PYTHON)

CC=gcc
CFLAGS =-Wall -O0

crc_tb:
	$(CC) $(CFLAGS) $(INC) -o crc crc.c
	./crc /> crc_ref
	$(CMD) crc_tb.py

scrambler_tb:
	$(CC) $(CFLAGS) $(INC) -o scrambler scrambler.c
	./scrambler /> scrambler_ref
	$(CMD) scrambler_tb.py

clean:
	rm crc crc_ref scrambler scrambler_ref
