TARGETS=flterm byteswap
CC=gcc
RM ?= rm -f

all: $(TARGETS)

%: %.c
	$(CC) -O2 -Wall -I../common -s -o $@ $<

install: flterm
	install -d /usr/local/bin
	install -m755 -t /usr/local/bin $^

.PHONY: all clean install

clean:
	$(RM) $(TARGETS)
