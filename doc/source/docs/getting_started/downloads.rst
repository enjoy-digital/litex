.. _sdk-download-and-install:

====================
Download and install
====================
1. Install Python3 and Xilinx's Vivado software

2. Obtain Migen and install it:
  - git clone https://github.com/enjoy-digital/migen
  - cd migen
  - python3 setup.py install
  - cd ..

3. Obtain Miscope and install it:
  - git clone https://github.com/enjoy-digital/miscope
  - cd miscope
  - python3 setup.py install
  - cd ..

4. Obtain MiSoC:
  - git clone https://github.com/enjoy-digital/misoc --recursive

5. Copy lite-sata in working directory and move to it.

6. Build and load design:
  - python3 make.py all

7. Test design:
  - go to test directory and run:
  - python3 bist.py
