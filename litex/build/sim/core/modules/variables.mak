CC ?= gcc
CFLAGS += -Wall -O3 -ggdb -fPIC -Werror
LDFLAGS += -levent -shared -fPIC

OBJ_DIR ?= .
