include ../variables.mak
MODULES = xgmii_ethernet ethernet serial2console serial2tcp clocker spdeeprom gmii_ethernet jtagremote $(if $(VIDEO), video)

.PHONY: $(MODULES) $(EXTRA_MOD_LIST)
all: $(MODULES) $(EXTRA_MOD_LIST)

$(MODULES): %:
	mkdir -p $@
	$(MAKE) MOD=$@ -C $@ -f $(SRC_DIR)/modules/$@/Makefile
	cp $@/$@.so $@.so

$(EXTRA_MOD_LIST): %:
	mkdir -p $@
	$(MAKE) MOD=$@ -C $@ -f $(EXTRA_MOD_BASE_DIR)/$@/Makefile
	cp $@/$@.so $@.so

.PHONY: clean
clean:
	for module in $(MODULES); do \
		$(MAKE) -C $$module $@; \
	done
