include variables.mak
UNAME_S := $(shell uname -s)
UNAME_M := $(shell uname -m)

ifeq ($(UNAME_S),Darwin)
	ifeq ($(UNAME_M),x86_64)
		CFLAGS += -I/usr/local/include
		LDFLAGS += -L/usr/local/lib
	else
		CFLAGS += -I/opt/homebrew/include
		LDFLAGS += -L/opt/homebrew/lib
	endif
	LDFLAGS += -lpthread -ljson-c -lz -lm -lstdc++ -ldl -levent $(if $(VIDEO), -lSDL2)
else
	CC ?= gcc
	CFLAGS += -ggdb
	LDFLAGS += -lpthread -Wl,--no-as-needed -ljson-c -lz -lm -lstdc++ -Wl,--no-as-needed -ldl -levent $(if $(VIDEO), -lSDL2)
endif

CFLAGS += -Wall -$(OPT_LEVEL) $(if $(COVERAGE), -DVM_COVERAGE) $(if $(TRACE_FST), -DTRACE_FST)

CC_SRCS ?= "--cc sim.v"

SRC_DIR ?= .
INC_DIR ?= .
MOD_DIR = $(SRC_DIR)/modules
export OBJ_DIR = $(abspath obj_dir)

SRCS_SIM_ABSPATH = $(wildcard $(SRC_DIR)/*.c)
SRCS_SIM = $(notdir $(SRCS_SIM_ABSPATH))
SRCS_SIM_CPP = sim_init.cpp $(SRC_DIR)/veril.cpp
OBJS_SIM = $(SRCS_SIM:.c=.o)

all: modules sim

mkdir:
	mkdir -p $(OBJ_DIR)

$(OBJS_SIM): %.o: $(SRC_DIR)/%.c | mkdir
	$(CC) -c $(CFLAGS) -o $(OBJ_DIR)/$@ $<

.PHONY: sim
sim: $(OBJS_SIM) | mkdir
	verilator -Wno-fatal -O3 $(CC_SRCS) --top-module sim --exe \
		-DPRINTF_COND=0 \
		$(SRCS_SIM_CPP) $(OBJS_SIM) \
		--top-module sim \
		$(if $(THREADS), --threads $(THREADS),) \
		-CFLAGS "$(CFLAGS) -I$(SRC_DIR)" \
		-LDFLAGS "$(LDFLAGS)" \
		--trace \
		$(if $(TRACE_FST), --trace-fst,) \
		$(if $(COVERAGE), --coverage,) \
		--unroll-count 256 \
		--output-split 5000 \
		--output-split-cfuncs 500 \
		--output-split-ctrace 500 \
		$(INC_DIR) \
		-Wno-BLKANDNBLK \
		-Wno-WIDTH \
		-Wno-COMBDLY \
		-Wno-CASEINCOMPLETE \
		--relative-includes
	make -j$(JOBS) -C $(OBJ_DIR) -f Vsim.mk Vsim

.PHONY: modules
modules:
	mkdir -p modules
	$(MAKE) -C modules -f $(MOD_DIR)/Makefile

.PHONY: clean
clean:
	rm -rf $(OBJ_DIR)
