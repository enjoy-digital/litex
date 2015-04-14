INSTDIR = $(shell iverilog-vpi --install-dir)

CFLAGS = -Wall -O2 $(CFLAGS_$@)
VPI_CFLAGS := $(shell iverilog-vpi --cflags)

OBJ=ipc.o main.o

all: migensim.vpi

%.o: %.c
	$(CC) $(CFLAGS) $(VPI_CFLAGS) -c $(INCDIRS) -o $@ $<

migensim.vpi: $(OBJ)
	iverilog-vpi --name=migensim $^

install: migensim.vpi
	install -m755 -t $(INSTDIR) $^

clean:
	rm -f $(OBJ)
	rm -f migensim.vpi

.PHONY: install clean
