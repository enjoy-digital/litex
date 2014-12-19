MSCDIR = ../../../
PYTHON = python3

CMD = PYTHONPATH=$(MSCDIR) $(PYTHON)

CC=gcc
CFLAGS =-Wall -O0

phy_datapath_tb:
	$(CMD) phy_datapath_tb.py

crc_tb:
	$(CC) $(CFLAGS) $(INC) -o crc crc.c
	$(CMD) crc_tb.py

scrambler_tb:
	$(CC) $(CFLAGS) $(INC) -o scrambler scrambler.c
	$(CMD) scrambler_tb.py

cont_tb:
	$(CMD) cont_tb.py

link_tb:
	$(CMD) link_tb.py

command_tb:
	$(CMD) command_tb.py

bist_tb:
	$(CMD) bist_tb.py

clean:
	rm crc scrambler *.vcd
