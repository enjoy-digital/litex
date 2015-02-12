.. _sdk-download-and-install:

====================
Download and install
====================
1. Install Python3 and your vendor's software

2. Obtain Migen and install it:
  - git clone https://github.com/m-labs/migen
  - cd migen
  - python3 setup.py install
  - cd ..

3. Obtain LiteScope and install it:
  - git clone https://github.com/enjoy-digital/litescope
  - cd litescope
  - python3 setup.py install
  - cd ..

4. Obtain MiSoC and install it:
  - git clone https://github.com/m-labs/misoc --recursive
  - cd misoc
  - python3 setup.py install
  - cd ..

.. note::
	In case you have issues with Migen/MiSoC, please retry with our forks at:
	https://github.com/enjoy-digital/misoc
	https://github.com/enjoy-digital/migen
	until new features are merged.

5. Obtain LiteEth
  - git clone https://github.com/enjoy-digital/liteeth

6. Build and load UDP loopback design (only for KC705 for now):
  - python3 make.py all (-s UDPSoCDevel to add LiteScopeLA)

7. Test design (only for KC705 for now):
  - try to ping 192.168.1.40
  - go to ./test directory:
  - change com port in config.py to your com port
  - run make test_udp

8. Build and load Etherbone design (only for KC705 for now):
  - python3 make.py -t Etherbone

9. Test design (only for KC705 for now):
  - try to ping 192.168.1.40
  - go to ./test directory run:
  - run make test_etherbone