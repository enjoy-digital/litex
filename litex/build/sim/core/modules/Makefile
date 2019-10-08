MODULES = xgmii_ethernet ethernet serial2console serial2tcp clocker
SHROBJS = $(MODULES:=.so)

.PHONY: $(MODULES)
all: $(MODULES)

$(MODULES): %:
	$(MAKE) -C $@

.PHONY: clean
clean:
	for module in $(MODULES); do \
		$(MAKE) -C $$module $@; \
	done
