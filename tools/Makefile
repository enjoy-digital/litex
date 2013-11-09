TARGETS=mkmscimg flterm byteswap
CC=gcc
RM ?= rm -f

all: $(TARGETS)

%: %.c
	$(CC) -O2 -Wall -I../common -s -o $@ $<

install: mkmscimg flterm
	install -d /usr/local/bin
	install -m755 -t /usr/local/bin $^

.PHONY: all clean install

clean:
	$(RM) $(TARGETS)
