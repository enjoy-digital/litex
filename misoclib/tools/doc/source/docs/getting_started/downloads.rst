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
	In case you have issues with Migen, please retry with our forks at:
	https://github.com/enjoy-digital/migen
	until new features are merged.

3. Obtain LiteScope
  - git clone https://github.com/enjoy-digital/litescope

4. Build and load example design:
  - python3 make.py all

5. Test design:
  - go to ./test directoryand run:
  - python3 test_io.py
  - python3 test_la.py
