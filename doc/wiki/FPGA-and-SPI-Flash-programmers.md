LiteX relies on several external tools to load the FPGA bitstream in SRAM or flash it in SPI Flash. This page provide information to install them.

## OpenOCD

OpenOCD is used in LiteX to load bitstream in SRAM or flash SPI-Flash on most of the suported Xilinx/Lattice devices. Please use and install **our fork of OpenOCD** for the boards using the OpenOCD programmer:

    git clone https://github.com/enjoy-digital/openocd
    cd openocd  
    ./bootstrap  
    ./configure --enable-ftdi  
    make  
    sudo make install

## openFPGALoader

openFPGALoader is an awesome FPGA loader tool developed by @trabucayre that supports most of the boards used by the open-FPGA communities (and also the more exotic ones!). We are relying on it in LiteX for an increasing number of boards (Gowin, Efinix boards) and already switched to it for some ECP5 boards. You can use **upstream openFPGALoader** with LiteX:

    apt-get install libftdi1-2 libftdi1-dev libhidapi-hidraw0 libhidapi-dev libudev-dev cmake pkg-config make g++
    git clone https://github.com/trabucayre/openFPGALoader
    cd openFPGALoader
    mkdir build
    cd build
    cmake ../
    make
    sudo make install
