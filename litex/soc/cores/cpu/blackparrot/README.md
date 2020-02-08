TODO: Edit
git submodule update --init --recursive (for blackparrot pre-alpha repo)
cd pre_alpha_release
follow getting_started to install blackparrot
cd ..
source ./setEnvironment.sh #should be sourced each time you open a terminal or just add this line to bashrc
Add $BP_TOP/external/bin to $PATH for verilator and riscv-gnu tools
./update_BP.sh #to modify some of the files in Blackparrot repo (one-time process)
Currently, we could simulate the LITEX-BIOS on BP processor. 

[![asciicast](https://asciinema.org/a/286568.svg)](https://asciinema.org/a/286568)

