LEDIR = ../../
PYTHON = python3

CMD = PYTHONPATH=$(LEDIR) $(PYTHON)

model_tb:
	$(CMD) ./model/mac.py
	$(CMD) ./model/arp.py
	$(CMD) ./model/ip.py

mac_core_tb:
	$(CMD) mac_core_tb.py

mac_wishbone_tb:
	$(CMD) mac_wishbone_tb.py

arp_tb:
	$(CMD) arp_tb.py

ip_tb:
	$(CMD) ip_tb.py	
