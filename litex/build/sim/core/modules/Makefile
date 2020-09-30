include ../variables.mak
MODULES = xgmii_ethernet ethernet serial2console serial2tcp clocker spdeeprom

.PHONY: $(MODULES)
all: $(MODULES)

$(MODULES): %:
	mkdir -p $@
	$(MAKE) MOD=$@ -C $@ -f $(SRC_DIR)/modules/$@/Makefile
	cp $@/$@.so $@.so

.PHONY: clean
clean:
	for module in $(MODULES); do \
		$(MAKE) -C $$module $@; \
	done
