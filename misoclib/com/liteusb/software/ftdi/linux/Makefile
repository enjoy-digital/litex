UNAME := $(shell uname)

LIBNAME := libftdicom


# Load libusb via pkg-config
PACKAGES := libusb-1.0
CFLAGS += $(shell pkg-config --cflags $(PACKAGES))
LDFLAGS += $(shell pkg-config --libs $(PACKAGES))

# Large file support
CFLAGS += $(shell getconf LFS_CFLAGS)

CFLAGS += -fPIC

SO := $(LIBNAME).so
SO_LDFLAGS := $(LDFLAGS) -shared

# Local headers
CFLAGS += -I../include

SO_OBJS := ../fastftdi.o

CFLAGS += -O3 -g --std=c99

all: $(SO)
	cp libftdicom.so ../libftdicom.so

$(SO): $(SO_OBJS)
	cc -o $@ $^ $(SO_LDFLAGS)

*.o: *.h Makefile

clean:
	rm -f $(SO) $(OBJS) $(SO_OBJS)
