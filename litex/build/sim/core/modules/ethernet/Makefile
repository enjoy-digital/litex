include ../variables.mak
CFLAGS += -Itapcfg/src/include

all: $(OBJ_DIR)/ethernet.so

include ../rules.mak

OBJS = $(addprefix $(OBJ_DIR)/, ethernet.o tapcfg.o taplog.o)

$(OBJ_DIR)/ethernet.so: $(OBJS)
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^

$(OBJ_DIR)/tapcfg.o: tapcfg/src/lib/tapcfg.c
	$(CC) $(CFLAGS) -c -o $@ $<

$(OBJ_DIR)/taplog.o: tapcfg/src/lib/taplog.c
	$(CC) $(CFLAGS) -c -o $@ $<
