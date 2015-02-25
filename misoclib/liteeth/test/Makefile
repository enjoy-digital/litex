LEDIR = ../../
PYTHON = python3

CMD = PYTHONPATH=$(LEDIR) $(PYTHON)

model_tb:
	$(CMD) ./model/mac.py
	$(CMD) ./model/arp.py
	$(CMD) ./model/ip.py
	$(CMD) ./model/udp.py
	$(CMD) ./model/icmp.py
	$(CMD) ./model/etherbone.py

mac_core_tb:
	$(CMD) mac_core_tb.py

mac_wishbone_tb:
	$(CMD) mac_wishbone_tb.py

arp_tb:
	$(CMD) arp_tb.py

ip_tb:
	$(CMD) ip_tb.py

udp_tb:
	$(CMD) udp_tb.py

icmp_tb:
	$(CMD) icmp_tb.py

etherbone_tb:
	$(CMD) etherbone_tb.py
