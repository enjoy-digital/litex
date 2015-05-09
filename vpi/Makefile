INSTDIR = $(shell iverilog-vpi --install-dir)

CFLAGS = -Wall -O2 $(CFLAGS_$@)
VPI_CFLAGS := $(shell iverilog-vpi --cflags)
# Define the below flags for a Windows build.
# Make sure to run iverilog-vpi with -mingw and -ivl options if necessary!
# i.e. iverilog-vpi -mingw=C:\msys64\mingw32 -ivl=C:\msys64\mingw32
# MINGW_FLAGS=-lWs2_32

OBJ=ipc.o main.o

all: migensim.vpi

%.o: %.c
	$(CC) $(CFLAGS) $(VPI_CFLAGS) -c $(INCDIRS) -o $@ $<

migensim.vpi: $(OBJ)
	iverilog-vpi $(MINGW_FLAGS) --name=migensim $^

install: migensim.vpi
	install -m755 -t $(INSTDIR) $^

clean:
	rm -f $(OBJ)
	rm -f migensim.vpi

.PHONY: install clean
