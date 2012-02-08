TARGETS=mkmmimg flterm
CC=clang

all: $(TARGETS)

%: %.c
	$(CC) -O2 -Wall -I. -s -o $@ $<

install: mkmmimg flterm
	cp mkmmimg /usr/bin
	cp flterm /usr/bin

.PHONY: clean install

clean:
	rm -f $(TARGETS)
