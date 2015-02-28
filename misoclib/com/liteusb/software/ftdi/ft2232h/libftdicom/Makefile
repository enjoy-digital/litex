CC=gcc
CFLAGS =-Wall -O0
CFLAGS_DLL =-Wall -O0 -g -shared -Wl,--out-implib,libftdicom.a
INC=-I. -I../libusb
LIBS_PATHS= -L. -L../libusb
LIBS_DLL= -lusb-1.0 -lpthreadGC2

all: libftdicom.dll

libftdicom.dll: crc32.c fastftdi.c ftdicom.c
	$(CC) $(INC) -o $@ $(CFLAGS_DLL) $^ $(LIBS_PATHS) $(LIBS_DLL)
	
clean:
	rm libftdicom.a
	rm libftdicom.dll