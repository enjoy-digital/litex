include ../../variables.mak
UNAME_S := $(shell uname -s)

include $(SRC_DIR)/modules/rules.mak

CFLAGS += -I$(TAPCFG_DIRECTORY)/src/include
LDFLAGS += -lz
OBJS = $(MOD).o tapcfg.o taplog.o

$(MOD).so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^
endif

tapcfg.o: $(TAPCFG_DIRECTORY)/src/lib/tapcfg.c
	$(CC) $(CFLAGS) -c -o $@ $<

taplog.o: $(TAPCFG_DIRECTORY)/src/lib/taplog.c
	$(CC) $(CFLAGS) -c -o $@ $<
