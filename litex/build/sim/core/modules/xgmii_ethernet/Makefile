include ../variables.mak
LITEX_THIRD_PARTY = ../../../../../../third_party
CFLAGS += -I$(LITEX_THIRD_PARTY)/litex_sim_tapcfg/src/include
UNAME_S := $(shell uname -s)

all: $(OBJ_DIR)/xgmii_ethernet.so

include ../rules.mak

OBJS = $(addprefix $(OBJ_DIR)/, xgmii_ethernet.o tapcfg.o taplog.o)

$(OBJ_DIR)/xgmii_ethernet.so: $(OBJS)
ifeq ($(UNAME_S),Darwin)
	$(CC) $(LDFLAGS) -o $@ $^
else
	$(CC) $(LDFLAGS) -Wl,-soname,$@ -o $@ $^
endif

$(OBJ_DIR)/tapcfg.o: $(LITEX_THIRD_PARTY)/litex_sim_tapcfg/src/lib/tapcfg.c
	$(CC) $(CFLAGS) -c -o $@ $<

$(OBJ_DIR)/taplog.o: $(LITEX_THIRD_PARTY)/litex_sim_tapcfg/src/lib/taplog.c
	$(CC) $(CFLAGS) -c -o $@ $<
