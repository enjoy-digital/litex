CC ?= gcc
UNAME_S := $(shell uname -s)

ifeq ($(UNAME_S),Darwin)
    CFLAGS += -I/usr/local/include/
    LDFLAGS += -L/usr/local/lib -ljson-c
    CFLAGS += -Wall -O3 -ggdb -fPIC
else
    CFLAGS += -Wall -O3 -ggdb -fPIC -Werror
endif
LDFLAGS += -levent -shared -fPIC

OBJ_DIR ?= .
