.. _sdk-download-and-install:

====================
Download and install
====================
1. Install Python3 and Xilinx's Vivado software

2. Obtain Migen and install it:
  - git clone https://github.com/m-labs/migen
  - cd migen
  - python3 setup.py install
  - cd ..

3. Obtain Miscope and install it:
  - git clone https://github.com/m-labs/miscope
  - cd miscope
  - python3 setup.py install
  - cd ..

4. Obtain MiSoC:
  - git clone https://github.com/m-labs/misoc --recursive
  XXX add setup.py to MiSoC for external use of misoclib?

5. Obtain LiteSATA
  - git clone https://github.com/enjoy-digital/litesata

6. Build and load BIST design (only for KC705 for now):
  - python3 make.py all

7. Test design (only for KC705 for now):
  - go to ./test directory and run:
  - python3 bist.py

8. If you only want to build the core and use it with your
regular design flow:
  - python3 make.py -t core build-core