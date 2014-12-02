MSCDIR = ../../../../
PYTHON = python3

CMD = PYTHONPATH=$(MSCDIR) $(PYTHON)

CC=gcc
CFLAGS =-Wall -O0

crc_tb:
	$(CC) $(CFLAGS) $(INC) -o crc crc.c
	$(CMD) crc_tb.py

scrambler_tb:
	$(CC) $(CFLAGS) $(INC) -o scrambler scrambler.c
	$(CMD) scrambler_tb.py

link_tb:
	$(CMD) link_tb.py

all: crc_tb scrambler_tb

clean:
	rm crc scrambler *.vcd
