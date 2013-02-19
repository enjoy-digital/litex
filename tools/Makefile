TARGETS=mkmmimg flterm byteswap
CC=gcc

all: $(TARGETS)

%: %.c
	$(CC) -O2 -Wall -I../common -s -o $@ $<

install: mkmmimg flterm
	install -d /usr/local/bin
	install -m755 -t /usr/local/bin $^

.PHONY: clean install

clean:
	rm -f $(TARGETS)
