include ../variables.mak
CFLAGS += -Itapcfg/src/include
UNAME_S := $(shell uname -s)

all: $(OBJ_DIR)/ethernet.so

include ../rules.mak

OBJS = $(addprefix $(OBJ_DIR)/, ethernet.o tapcfg.o taplog.o)

$(OBJ_DIR)/ethernet.so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^
endif

$(OBJ_DIR)/tapcfg.o: tapcfg/src/lib/tapcfg.c
	$(CC) $(CFLAGS) -c -o $@ $<

$(OBJ_DIR)/taplog.o: tapcfg/src/lib/taplog.c
	$(CC) $(CFLAGS) -c -o $@ $<
