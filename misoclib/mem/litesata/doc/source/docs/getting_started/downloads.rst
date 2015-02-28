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

.. note::
  In case you have issues with Migen, please retry with our fork at:
  https://github.com/enjoy-digital/migen
  until new features are merged.

3. Obtain LiteScope and install it:
  - git clone https://github.com/enjoy-digital/litescope
  - cd litescope
  - python3 setup.py install
  - cd ..

4. Obtain LiteSATA
  - git clone https://github.com/enjoy-digital/litesata

5. Build and load BIST design (only for KC705 for now):
  - python3 make.py all

6. Test design (only for KC705 for now):
  - go to ./test directory and run:
  - python3 bist.py

7. Visualize Link Layer transactions (if BISTSoCDevel):
  - go to ./test directory and run:
  - python3 test_la.py [your_cond]
  - your_cond can be wr_cmd, id_cmd, rd_resp, ...
  (open test_la.py to see all conditions or add yours)

8. If you only want to build the core and use it with your
regular design flow:
  - python3 make.py -t core build-core
