.. _sdk-download-and-install:

====================
Download and install
====================
1. Install Python3 and Xilinx's Vivado software

2. Obtain Migen and install it:
  - git clone https://github.com/m-labs/migen
  - cd migen
  - python3 setup.py install
  -cd ..

3. Obtain LiteScope and install it:
  - git clone https://github.com/enjoy-digital/litescope
  - cd litescope
  - python3 setup.py install
  - cd ..

4. Obtain MiSoC:
  - git clone https://github.com/m-labs/misoc --recursive
  XXX add setup.py to MiSoC for external use of misoclib?

5. Obtain LiteEth
  - git clone https://github.com/enjoy-digital/liteeth

6. Build and load UDP loopback design (only for KC705 for now):
  - python3 make.py all (-s UDPSoCDevel to add LiteScopeLA)

7. Test design (only for KC705 for now):
  - go to ./test directory and run:
  - change com port in config.py to your com port
  - try to ping 192.168.1.40
  - python3 test_udp.py
