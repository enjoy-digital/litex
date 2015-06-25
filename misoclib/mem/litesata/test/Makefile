MSCDIR = ../../../../
PYTHON = python3

CMD = PYTHONPATH=$(PYTHONPATH):$(MSCDIR) $(PYTHON)

CC=gcc
CFLAGS =-Wall -O0

phy_datapath_tb:
	$(CMD) phy_datapath_tb.py

crc_tb:
	$(CC) $(CFLAGS) $(INC) -o crc crc.c
	$(CMD) crc_tb.py

scrambler_tb: scrambler
	$(CMD) scrambler_tb.py

cont_tb:
	$(CMD) cont_tb.py

link_tb:
	$(CMD) link_tb.py

command_tb:
	$(CMD) command_tb.py

bist_tb: scrambler
	$(CMD) bist_tb.py

striping_tb:
	$(CMD) striping_tb.py

mirroring_tb:
	$(CMD) mirroring_tb.py

scrambler: scrambler.c
	$(CC) $(CFLAGS) $(INC) -o $@ $<

clean:
	rm -f crc scrambler *.vcd
