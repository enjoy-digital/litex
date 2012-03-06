CC=clang
INSTDIR=/usr/lib/ivl

OBJ=ipc.o main.o

all: migensim.vpi

%.o: %.c
	$(CC) -fPIC -Wall -O2 -c -o $@ $<

migensim.vpi: $(OBJ)
	$(CC) -shared -o $@ $(OBJ) -lvpi

install: migensim.vpi
	install -m755 -t $(INSTDIR) $^

clean:
	rm -f $(OBJ)
	rm -f migensim.vpi

.PHONY: install clean
