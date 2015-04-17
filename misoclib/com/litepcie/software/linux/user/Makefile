CFLAGS=-O2 -Wall -g -I../kernel -MMD
LDFLAGS=-g
CC=gcc
AR=ar

PROGS=litepcie_util

all: $(PROGS)

litepcie_util: litepcie_util.o litepcie_lib.o
	$(CC) $(LDFLAGS) -o $@ $^ -lrt -lm

clean:
	rm -f $(PROGS) *.o *.a *.d *~

%.o: %.c
	$(CC) -c $(CFLAGS) -o $@ $<

-include $(wildcard *.d)
