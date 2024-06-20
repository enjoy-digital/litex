include ../../variables.mak
UNAME_S := $(shell uname -s)

include $(SRC_DIR)/modules/rules.mak

CFLAGS += -I$(TAPCFG_DIRECTORY)/src/include
OBJS = $(MOD).o

$(MOD).so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^
endif
