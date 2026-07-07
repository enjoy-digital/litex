#!/bin/bash
# EmuLiteX - Complete Setup Script (Ubuntu Only)
# Usage: ./setup.sh [OPTIONS]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values (everything enabled by default)
CONFIG="standard"
SIMULATION_CPU="vexriscv"
CPU_VARIANT="standard"
HELP=0
UPDATE=0
SIMULATION_ONLY=0
EXTRA_ARGS=""

# Print banner
print_banner() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  EmuLiteX - Setup Script${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Print usage
print_usage() {
    cat << EOF
Usage: ./setup.sh [OPTIONS]

Options:
    --config=NAME       Install config: minimal, standard, full (default: standard)
    --cpu=TYPE          CPU type: vexriscv, serv, cva6, ibex, rocket, vexriscv_smp (default: vexriscv)
    --variant=TYPE      CPU variant for rocket: full, linux, medium, small (default: standard)
    --extra-args="..."  Extra arguments to pass to litex_sim (e.g., --with-sdram)
    --sim-only          Only run simulation (skip setup)
    --update            Force update repositories and reinstall
    --help, -h          Show this help message

Examples:
    ./setup.sh                                    # Install everything and run simulation
    ./setup.sh --config=minimal                   # Minimal installation
    ./setup.sh --cpu=serv                         # Run simulation with SERV CPU
    ./setup.sh --cpu=rocket --variant=full        # Run simulation with Rocket CPU (full variant)
    ./setup.sh --extra-args="--with-sdram"        # Run simulation with SDRAM
    ./setup.sh --extra-args="--with-sdram --with-etherbone"  # Multiple args
    ./setup.sh --sim-only --cpu=cva6              # Only run simulation
    ./setup.sh --update                           # Force update and reinstall

Note: By default, this script:
    1. Installs all system dependencies (verilator, gcc-riscv, etc.)
    2. Creates Python virtual environment
    3. Runs litex_setup.py --init --install --config=standard (only if not installed)
    4. Runs litex_sim --cpu-type=vexriscv
EOF
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --config=*) CONFIG="${1#*=}"; shift ;;
            --cpu=*) SIMULATION_CPU="${1#*=}"; shift ;;
            --variant=*) CPU_VARIANT="${1#*=}"; shift ;;
            --extra-args=*) EXTRA_ARGS="${1#*=}"; shift ;;
            --sim-only) SIMULATION_ONLY=1; shift ;;
            --update) UPDATE=1; shift ;;
            --help|-h) HELP=1; shift ;;
            *) echo -e "${RED}Unknown option: $1${NC}"; print_usage; exit 1 ;;
        esac
    done
}

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

# Function to check if system package is installed
system_package_installed() {
    if command -v apt-get &> /dev/null; then
        dpkg -l "$1" 2>/dev/null | grep -q "^ii"
    else
        return 1
    fi
}

# Install SBT if not already installed
install_sbt() {
    if command_exists sbt; then
        echo -e "${GREEN}✓ SBT already installed${NC}"
        return 0
    fi
    
    echo -e "${YELLOW}SBT not found. Installing...${NC}"
    
    # Remove broken repositories
    sudo rm -f /etc/apt/sources.list.d/sbt.list /etc/apt/sources.list.d/sbt_old.list 2>/dev/null
    
    # Install Java if needed
    if ! command_exists java; then
        sudo apt-get install -y openjdk-17-jdk
    fi
    
    # Download and install SBT
    wget -qO /tmp/sbt-2.0.1.tgz https://github.com/sbt/sbt/releases/download/v2.0.1/sbt-2.0.1.tgz
    sudo tar -xzf /tmp/sbt-2.0.1.tgz -C /usr/local/
    sudo mv /usr/local/sbt-2.0.1 /usr/local/sbt 2>/dev/null || true
    sudo ln -sf /usr/local/sbt/bin/sbt /usr/local/bin/sbt
    rm -f /tmp/sbt-2.0.1.tgz
    
    if command_exists sbt; then
        echo -e "${GREEN}✓ SBT installed successfully${NC}"
    else
        echo -e "${RED}✗ SBT installation failed${NC}"
        exit 1
    fi
}

# Install system dependencies (only if not already installed)
install_system_deps() {
    echo -e "\n${YELLOW}Checking system dependencies...${NC}"
    
    # Ubuntu/Debian only
    if ! command -v apt-get &> /dev/null; then
        echo -e "${RED}This script only supports Ubuntu/Debian systems.${NC}"
        echo -e "${YELLOW}Please install dependencies manually or use a different OS.${NC}"
        exit 1
    fi
    
    # Ubuntu/Debian
    sudo apt-get update
    
    # Python basics
    for pkg in python3 python3-pip python3-venv python3-dev git; do
        if system_package_installed "$pkg"; then
            echo -e "${GREEN}✓ $pkg already installed${NC}"
        else
            echo -e "${YELLOW}Installing $pkg...${NC}"
            sudo apt-get install -y "$pkg"
        fi
    done
    
    # Build tools
    for pkg in build-essential cmake make; do
        if system_package_installed "$pkg"; then
            echo -e "${GREEN}✓ $pkg already installed${NC}"
        else
            echo -e "${YELLOW}Installing $pkg...${NC}"
            sudo apt-get install -y "$pkg"
        fi
    done
    
    # RISC-V toolchain
    if command_exists riscv64-unknown-elf-gcc; then
        echo -e "${GREEN}✓ RISC-V toolchain already installed${NC}"
    else
        echo -e "${YELLOW}Installing RISC-V toolchain...${NC}"
        sudo apt-get install -y gcc-riscv64-unknown-elf gcc-riscv64-linux-gnu binutils-riscv64-unknown-elf 2>/dev/null || \
        echo -e "${YELLOW}⚠ RISC-V toolchain not available in repositories${NC}"
    fi
    
    # Build systems
    for pkg in meson ninja-build; do
        if command_exists "$pkg" || command_exists "ninja"; then
            echo -e "${GREEN}✓ $pkg already installed${NC}"
        else
            echo -e "${YELLOW}Installing $pkg...${NC}"
            sudo apt-get install -y "$pkg"
        fi
    done
    
    # Simulation tools
    if command_exists verilator; then
        echo -e "${GREEN}✓ verilator already installed${NC}"
    else
        echo -e "${YELLOW}Installing verilator from source (apt's version is too old)...${NC}"
        sudo apt-get install -y git help2man perl python3 make autoconf g++ flex bison ccache libgoogle-perftools-dev numactl perl-doc libfl2 libfl-dev zlib1g zlib1g-dev
        git clone --depth 1 --branch v5.034 https://github.com/verilator/verilator /tmp/verilator-build
        (cd /tmp/verilator-build && autoconf && ./configure && make -j$(nproc) && sudo make install)
        rm -rf /tmp/verilator-build
    fi
    
    # GTKWave (optional - for viewing waveforms)
    if command_exists gtkwave; then
        echo -e "${GREEN}✓ gtkwave already installed${NC}"
    else
        echo -e "${YELLOW}Installing gtkwave...${NC}"
        sudo apt-get install -y gtkwave
    fi
    
    # Libraries
    for pkg in libevent-dev libjson-c-dev libboost-all-dev libssl-dev libffi-dev; do
        if system_package_installed "$pkg"; then
            echo -e "${GREEN}✓ $pkg already installed${NC}"
        else
            echo -e "${YELLOW}Installing $pkg...${NC}"
            sudo apt-get install -y "$pkg"
        fi
    done
    
    echo -e "${GREEN}✓ Ubuntu/Debian dependencies installed${NC}"
}

# Setup virtual environment
setup_venv() {
    echo -e "\n${YELLOW}Setting up virtual environment...${NC}"
    
    if [ -d "venv" ]; then
        echo -e "${GREEN}✓ Virtual environment already exists${NC}"
    else
        python3 -m venv venv
        echo -e "${GREEN}✓ Virtual environment created${NC}"
    fi
    
    source venv/bin/activate
    pip install --upgrade pip setuptools wheel --quiet 2>/dev/null || true
    echo -e "${GREEN}✓ Virtual environment activated${NC}"
}

# Run litex_setup.py
run_litex_setup() {
    echo -e "\n${YELLOW}Running litex_setup.py...${NC}"
    
    if [ ! -f "litex_setup.py" ]; then
        echo -e "${RED}Error: litex_setup.py not found!${NC}"
        exit 1
    fi
    
    # If --update flag is passed, force update
    if [ "$UPDATE" = "1" ]; then
        echo -e "${YELLOW}Force update requested...${NC}"
        CMD="./litex_setup.py --update --install --config=$CONFIG"
        echo -e "${BLUE}Command: $CMD${NC}"
        eval "$CMD"
        echo -e "${GREEN}✓ litex_setup.py completed${NC}"
        return
    fi
    
    # Check if litex is already installed
    if pip show litex &> /dev/null; then
        echo -e "${GREEN}✓ litex already installed (skipping setup)${NC}"
        echo -e "${GREEN}✓ To force update, run: ./setup.sh --update${NC}"
        return
    fi
    
    # Not installed - check if repos exist
    if [ -d "../litex" ]; then
        echo -e "${YELLOW}Repositories exist but litex is not installed. Installing...${NC}"
        CMD="./litex_setup.py --install --config=$CONFIG"
        echo -e "${BLUE}Command: $CMD${NC}"
        eval "$CMD"
        echo -e "${GREEN}✓ litex_setup.py completed${NC}"
    else
        echo -e "${YELLOW}Repositories not found. Running fresh install...${NC}"
        CMD="./litex_setup.py --init --install --config=$CONFIG"
        echo -e "${BLUE}Command: $CMD${NC}"
        eval "$CMD"
        echo -e "${GREEN}✓ litex_setup.py completed${NC}"
    fi
}

# Run simulation
run_simulation() {
    # Check if SBT is needed and install if missing
    [[ "$SIMULATION_CPU" == "vexriscv_smp" ]] && install_sbt

    echo -e "\n${YELLOW}Running simulation...${NC}"
    echo -e "${BLUE}CPU: $SIMULATION_CPU${NC}"
    echo -e "${BLUE}Variant: $CPU_VARIANT${NC}"
    if [ -n "$EXTRA_ARGS" ]; then
        echo -e "${BLUE}Extra args: $EXTRA_ARGS${NC}"
    fi
    echo -e "${YELLOW}Press Ctrl+C to exit${NC}"
    echo ""
    
    # Check if venv is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "venv" ]; then
            source venv/bin/activate
        else
            echo -e "${RED}Error: Virtual environment not found!${NC}"
            exit 1
        fi
    fi
    
    # Create timestamped project directory with CPU name
    PROJECT_DIR="../sim_projects/${SIMULATION_CPU}_$(date '+%d-%m-%H-%M')"
    mkdir -p "$PROJECT_DIR"
    
    echo -e "${BLUE}Project directory: $PROJECT_DIR${NC}"
    
    cd "$PROJECT_DIR"
    
    # Build the command
    CMD="litex_sim --cpu-type=\"$SIMULATION_CPU\" --cpu-variant=\"$CPU_VARIANT\""
    if [ -n "$EXTRA_ARGS" ]; then
        CMD="$CMD $EXTRA_ARGS"
    fi
    
    echo -e "${BLUE}Running: $CMD${NC}"
    echo ""
    
    eval "$CMD"
}

# Main function
main() {
    print_banner
    
    # Parse arguments
    parse_args "$@"
    
    # Show help
    if [ $HELP -eq 1 ]; then
        print_usage
        exit 0
    fi
    
    # If sim-only, skip everything and run simulation
    if [ "$SIMULATION_ONLY" = "1" ]; then
        if [ ! -d "venv" ]; then
            echo -e "${RED}Error: Virtual environment not found. Run setup first.${NC}"
            exit 1
        fi
        run_simulation
        exit 0
    fi
    
    # Step 1: Install system dependencies
    install_system_deps
    
    # Step 2: Setup virtual environment
    setup_venv
    
    # Step 3: Run litex_setup.py inside venv
    run_litex_setup
    
    # Step 4: Run simulation
    run_simulation
}

# Run main
main "$@"