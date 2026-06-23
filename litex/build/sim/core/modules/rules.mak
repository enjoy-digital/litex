CC ?= gcc
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Darwin)
	ifeq ($(UNAME_M),x86_64)
		HOMEBREW_PREFIX ?= /usr/local
	else
		HOMEBREW_PREFIX ?= /opt/homebrew
	endif
	HOMEBREW_ZLIB_LIB := $(HOMEBREW_PREFIX)/opt/zlib/lib
	CFLAGS += -I$(HOMEBREW_PREFIX)/include
	LDFLAGS += -L$(HOMEBREW_PREFIX)/lib -Wl,-rpath,$(HOMEBREW_PREFIX)/lib
	ifneq ($(wildcard $(HOMEBREW_ZLIB_LIB)/libz.*),)
		LDFLAGS += -L$(HOMEBREW_ZLIB_LIB) -Wl,-rpath,$(HOMEBREW_ZLIB_LIB)
	endif
	LDFLAGS += -ljson-c
	CFLAGS += -Wall -O3 -ggdb -fPIC
else
	CFLAGS += -Wall -O3 -ggdb -fPIC -Werror
endif
LDFLAGS += -levent -shared -fPIC

MOD_SRC_DIR=$(SRC_DIR)/modules/$(MOD)
EXTRA_MOD_SRC_DIR=$(EXTRA_MOD_BASE_DIR)/$(MOD)

all: $(MOD).so

%.o: $(MOD_SRC_DIR)/%.c
	$(CC) -c $(CFLAGS) -I$(MOD_SRC_DIR)/../.. -o $@ $<

%.o: $(EXTRA_MOD_SRC_DIR)/%.c
	$(CC) -c $(CFLAGS) -I$(SRC_DIR) -o $@ $<

%.so: %.o
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $<
endif

.PHONY: clean
clean:
	rm -f *.o *.so
