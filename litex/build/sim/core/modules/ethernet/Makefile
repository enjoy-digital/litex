include ../../variables.mak
UNAME_S := $(shell uname -s)

include $(SRC_DIR)/modules/rules.mak

CFLAGS += -I$(MOD_SRC_DIR)/tapcfg/src/include
OBJS = $(MOD).o tapcfg.o taplog.o

$(MOD).so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^
endif

tapcfg.o: $(MOD_SRC_DIR)/tapcfg/src/lib/tapcfg.c
	$(CC) $(CFLAGS) -c -o $@ $<

taplog.o: $(MOD_SRC_DIR)/tapcfg/src/lib/taplog.c
	$(CC) $(CFLAGS) -c -o $@ $<
