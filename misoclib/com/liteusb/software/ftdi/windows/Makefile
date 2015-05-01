CC=gcc
CFLAGS_DLL =-Wall -O0 -g -shared -Wl,--subsystem,windows -DDLL
LIBS= -lusb-1.0

all: libftdicom.dll
	cp libftdicom.dll ../libftdicom.dll

libftdicom.dll: ../fastftdi.c
	$(CC) -o $@ $(CFLAGS_DLL) $^ $(LIBS)

clean:
	rm -f libftdicom.dll ../libftdicom.dll
