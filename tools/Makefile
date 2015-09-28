TARGETS=byteswap
CC=gcc
RM ?= rm -f

all: $(TARGETS)

%: %.c
	$(CC) -O2 -Wall -I../common -s -o $@ $<

.PHONY: all clean

clean:
	$(RM) $(TARGETS)
