TARGETS=flterm byteswap
CC=gcc
RM ?= rm -f
PREFIX ?= /usr/local

all: $(TARGETS)

%: %.c
	$(CC) -O2 -Wall -I../common -s -o $@ $<

install: flterm
	install -d $(PREFIX)/bin
	install -m755 -t $(PREFIX)/bin $^

.PHONY: all clean install

clean:
	$(RM) $(TARGETS)
