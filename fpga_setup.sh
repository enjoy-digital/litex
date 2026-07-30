#!/bin/bash
# EmuLiteX - FPGA Setup Script (Ubuntu Only)
# Usage: ./fpga_setup.sh [OPTIONS]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
BOARD="digilent_arty"
BOARD_VARIANT="a7-100"
FPGA_CPU="vexriscv"
CPU_VARIANT="standard"
SERIAL_PORT="/dev/ttyUSB1"
BAUDRATE="115200"
FPGA_ONLY=0
FLASH_ONLY=0
FLAG_HELP=0
HELP=0
EXTRA_ARGS=""
SCRIPT_DIR="$(pwd)"
DEMO_MODE=0

# Print banner
print_banner() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  EmuLiteX - FPGA Setup Script${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

print_flag() {
    setup_venv
    python3 -m litex_boards.targets.digilent_arty --help      for board-specific options
}

# Print usage
print_usage() {
    cat << EOF
Usage: ./fpga_setup.sh [OPTIONS]

Options:
    --board=NAME        FPGA board: digilent_arty (default)
    --board-variant=VAR Board variant: a7-100, a7-35, s7-50 (default: a7-100)
    --cpu=TYPE          CPU type: vexriscv, ibex, serv, cva6... (default: vexriscv)
    --cpu-variant=VAR   CPU variant: standard, full, linux, medium, small (default: standard)
    --port=DEV          Serial device (default: /dev/ttyUSB1)
    --baudrate=N        Baudrate (default: 115200)
    --fpga-only         Skip dependency checks, just build + flash + open terminal
    --flash-only        Skip build, flash existing bitstream for specified CPU + open terminal
    --demo              Build and run demo application on FPGA (bare metal)
    --extra-args="..."  Extra arguments to pass to the build command (e.g., --sys-clk-freq=100e6)
    --help, -h          Show this help message
    --flag               Show the flag for the for passing in extra_args 
Examples:
    ./fpga_setup.sh                                    # Full flow: deps + build + flash + terminal
    ./fpga_setup.sh --extra-args="--sys-clk-freq=100e6"  # Build with 100MHz
    ./fpga_setup.sh --extra-args="--sys-clk-freq=50e6 --sdram-rate=1:1"  # Multiple args
    ./fpga_setup.sh --fpga-only --extra-args="--sys-clk-freq=100e6"
    ./fpga_setup.sh --flash-only --cpu=cva6
    ./fpga_setup.sh --cpu=ibex
EOF
}

# Parse arguments
parse_args() {
    EXTRA_ARGS=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --board=*)        BOARD="${1#*=}";          shift ;;
            --board-variant=*) BOARD_VARIANT="${1#*=}"; shift ;;
            --cpu=*)          FPGA_CPU="${1#*=}";       shift ;;
            --cpu-variant=*)  CPU_VARIANT="${1#*=}";    shift ;;
            --port=*)         SERIAL_PORT="${1#*=}";    shift ;;
            --baudrate=*)     BAUDRATE="${1#*=}";       shift ;;
            --extra-args=*)   EXTRA_ARGS="${1#*=}";     shift ;;
            --fpga-only)      FPGA_ONLY=1;              shift ;;
            --flash-only)     FLASH_ONLY=1;             shift ;;
            --demo) DEMO_MODE=1; shift ;;
            --help|-h)        HELP=1;                   shift ;;
            --flag)         FLAG_HELP=1;              shift ;;
            --)               shift; EXTRA_ARGS="$*"; break ;;
            *)                echo -e "${RED}Unknown option: $1${NC}"; print_usage; exit 1 ;;
        esac
    done
}

# Function to check if command exists
command_exists() {
    command -v "$1" &> /dev/null
}

system_package_installed() {
    if command -v apt-get &> /dev/null; then
        dpkg -l "$1" 2>/dev/null | grep -q "^ii"
    else
        return 1
    fi
}

# Check OpenOCD
check_openocd() {
    echo -e "\n${YELLOW}Checking OpenOCD...${NC}"

    if command_exists openocd; then
        CURRENT_VERSION=$(openocd --version 2>&1 | head -1 | grep -oP '0\.\d+\.\d+' || echo "0.0.0")
        if [[ "$CURRENT_VERSION" == "0.12.0" ]] || [[ "$CURRENT_VERSION" > "0.12.0" ]]; then
            echo -e "${GREEN}✓ OpenOCD already installed${NC}"
            return 0
        fi
    fi

    echo -e "${YELLOW}Installing OpenOCD...${NC}"

    # Remove old version if exists
    sudo apt remove -y openocd 2>/dev/null || true

    # Install dependencies
    sudo apt-get install -y \
        libusb-1.0-0-dev libhidapi-dev libjaylink-dev \
        libgpiod-dev pkg-config autoconf automake libtool

    # Build OpenOCD 0.12.0 from source in a temp directory
    if [ -d "/tmp/openocd" ]; then
        sudo rm -rf /tmp/openocd
    fi

    git clone https://github.com/openocd-org/openocd.git --depth=1 --branch v0.12.0 /tmp/openocd
    cd /tmp/openocd
    ./bootstrap
    ./configure --enable-ftdi --enable-jlink --enable-cmsis-dap
    make -j$(nproc)
    sudo make install
    sudo ldconfig
    cd -

    rm -rf /tmp/openocd

    echo -e "${GREEN}✓ OpenOCD installed successfully${NC}"
}

# Install system dependencies
install_system_deps() {
    echo -e "\n${YELLOW}Checking system dependencies...${NC}"
    
    if ! command -v apt-get &> /dev/null; then
        echo -e "${RED}This script only supports Ubuntu/Debian systems.${NC}"
        exit 1
    fi
    
    sudo apt-get update -qq
    
    for pkg in python3 python3-pip python3-venv python3-dev git \
               build-essential cmake make pkg-config \
               meson ninja-build \
               libevent-dev libjson-c-dev libboost-all-dev \
               libssl-dev libffi-dev picocom; do
        if system_package_installed "$pkg"; then
            echo -e "${GREEN}✓ $pkg${NC}"
        else
            echo -e "${YELLOW}Installing $pkg...${NC}"
            sudo apt-get install -y "$pkg"
        fi
    done
    
    # RISC-V toolchain
    if command_exists riscv64-unknown-elf-gcc; then
        echo -e "${GREEN}✓ RISC-V toolchain${NC}"
    else
        echo -e "${YELLOW}Installing RISC-V toolchain...${NC}"
        sudo apt-get install -y gcc-riscv64-unknown-elf \
            gcc-riscv64-linux-gnu binutils-riscv64-unknown-elf 2>/dev/null || \
        echo -e "${YELLOW}⚠ RISC-V toolchain not available in repositories${NC}"
    fi
    
    # Install OpenOCD
    check_openocd

    echo -e "${GREEN}✓ All system dependencies satisfied${NC}"
}

# Setup virtual environment
setup_venv() {
    echo -e "\n${YELLOW}Setting up virtual environment...${NC}"
    
    # Remove corrupted venv if exists
    if [ -d "venv" ] && [ ! -f "venv/bin/activate" ]; then
        echo -e "${YELLOW}Removing corrupted virtual environment...${NC}"
        rm -rf venv
    fi
    
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
    
    if pip show litex &> /dev/null; then
        echo -e "${GREEN}✓ litex already installed${NC}"
        return
    fi
    
    if [ -d "../litex" ]; then
        ./litex_setup.py --install --config=standard
    else
        ./litex_setup.py --init --install --config=standard
    fi
    
    echo -e "${GREEN}✓ litex_setup.py completed${NC}"
}

# Find existing bitstream (most recent for specified CPU)
find_existing_bitstream() {
    # Check if fpga_projects directory exists
    if [ ! -d "../fpga_projects" ]; then
        return 1
    fi
    
    # Look for bitstream with the specified CPU in fpga_projects, sorted by modification time (newest first)
    BITSTREAM=$(find ../fpga_projects -type f -name "*.bit" -path "*/${BOARD}_${FPGA_CPU}_*" 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
    
    if [ -n "$BITSTREAM" ] && [ -f "$BITSTREAM" ]; then
        echo "$BITSTREAM"
        return 0
    else
        return 1
    fi
}

# Build FPGA bitstream
build_bitstream() {
    echo -e "\n${YELLOW}Building FPGA bitstream...${NC}"
    echo -e "${BLUE}Board: $BOARD${NC}"
    [ -n "$BOARD_VARIANT" ] && echo -e "${BLUE}Board variant: $BOARD_VARIANT${NC}"
    echo -e "${BLUE}CPU: $FPGA_CPU${NC}"
    echo -e "${BLUE}CPU variant: $CPU_VARIANT${NC}"
    if [ -n "$EXTRA_ARGS" ]; then
        echo -e "${BLUE}Extra args: $EXTRA_ARGS${NC}"
    fi
    
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "venv" ]; then
            source venv/bin/activate
        else
            echo -e "${RED}Error: Virtual environment not found!${NC}"
            exit 1
        fi
    fi
    
    TARGET_MODULE="litex_boards.targets.${BOARD}"
    
    PROJECT_DIR="../fpga_projects/${BOARD}_${FPGA_CPU}_$(date '+%d-%m-%H-%M')"
    mkdir -p "$PROJECT_DIR"
    
    echo -e "${BLUE}Project directory: $PROJECT_DIR${NC}"
    
    cd "$PROJECT_DIR"
    
    CMD="python3 -m $TARGET_MODULE --build --cpu-type=$FPGA_CPU"
    
    if [ -n "$BOARD_VARIANT" ]; then
        CMD="$CMD --variant=$BOARD_VARIANT"
    fi
    
    if [ "$CPU_VARIANT" != "standard" ]; then
        CMD="$CMD --cpu-variant=$CPU_VARIANT"
    fi
    
    if [ -n "$EXTRA_ARGS" ]; then
        CMD="$CMD $EXTRA_ARGS"
    fi
    
    echo -e "${BLUE}Running: $CMD${NC}"
    echo ""
    
    eval "$CMD"
    
    # Find the bitstream
    BITSTREAM=$(find . -type f -name "*.bit" | head -1)
    if [ -n "$BITSTREAM" ]; then
        # Get absolute path
        FULL_PATH=$(realpath "$BITSTREAM")
        echo -e "${GREEN}✓ Bitstream generated: $FULL_PATH${NC}"
        echo "$FULL_PATH" > /tmp/last_bitstream
    else
        echo -e "${RED}✗ No bitstream found!${NC}"
        exit 1
    fi
    
    cd - > /dev/null
}

flash_bitstream() {
    echo -e "\n${YELLOW}Flashing bitstream via OpenOCD (--load)...${NC}"

    # Find the most recent project dir containing a .bit for this CPU
    PROJECT_WITH_BIT=$(find ../fpga_projects -type f \
        -name "*.bit" \
        -path "*/${BOARD}_${FPGA_CPU}_*" \
        2>/dev/null | xargs ls -t 2>/dev/null | head -1 | xargs -I{} dirname {} \
        | sed 's|/build/.*||')   # strip back to project root

    if [ -z "$PROJECT_WITH_BIT" ] || [ ! -d "$PROJECT_WITH_BIT" ]; then
        echo -e "${RED}No ${FPGA_CPU} bitstream found in ../fpga_projects/${NC}"
        exit 1
    fi

    echo -e "${BLUE}Project dir: $PROJECT_WITH_BIT${NC}"

    # cd to project dir so --load finds ./build/digilent_arty/gateware/*.bit
    cd "$PROJECT_WITH_BIT"

    CMD="python3 -m litex_boards.targets.${BOARD} --load --cpu-type=$FPGA_CPU"
    [ -n "$BOARD_VARIANT" ] && CMD="$CMD --variant=$BOARD_VARIANT"

    if [ -n "$EXTRA_ARGS" ]; then
        CMD="$CMD $EXTRA_ARGS"
    fi
    
    echo -e "${BLUE}Running: $CMD${NC}"
    eval "$CMD"

    cd - > /dev/null
    echo -e "${GREEN}✓ FPGA loaded successfully${NC}"
    echo -e "\n${GREEN}📁 Project Folder:${NC}\n${BLUE}$(cd "$PROJECT_WITH_BIT" && pwd)${NC}\n"
}

# Open serial terminal
open_terminal() {
    echo -e "\n${YELLOW}Opening serial terminal...${NC}"
    echo -e "${BLUE}Port: $SERIAL_PORT${NC}"
    echo -e "${BLUE}Baudrate: $BAUDRATE${NC}"
    echo -e "${YELLOW}Press Ctrl+A then Ctrl+X to exit picocom${NC}"
    echo ""
    
    # Check if picocom exists
    if ! command_exists picocom; then
        echo -e "${YELLOW}picocom not found. Installing...${NC}"
        sudo apt-get install -y picocom
    fi
    
    if [ ! -c "$SERIAL_PORT" ]; then
        echo -e "${RED}✗ Serial port $SERIAL_PORT not found.${NC}"
        echo -e "${YELLOW}  Available ports:${NC}"
        ls /dev/ttyUSB* 2>/dev/null || echo "    No /dev/ttyUSB* found"
        echo ""
        echo -e "${YELLOW}  Override with: --port=/dev/ttyUSB0${NC}"
        exit 1
    fi
    
    # If demo mode and not IBEX, load demo using --kernel
if [ "$DEMO_MODE" = "1" ] && [ "$FPGA_CPU" != "ibex" ]; then
        PROJECT_WITH_BIT=$(find ../fpga_projects -type f -name "*.bit" -path "*/${BOARD}_${FPGA_CPU}_*" 2>/dev/null | xargs ls -t 2>/dev/null | head -1 | xargs -I{} dirname {} | sed 's|/build/.*||')

        if [ -n "$PROJECT_WITH_BIT" ] && [ -f "${PROJECT_WITH_BIT}/demo/demo.bin" ]; then
            echo -e "${YELLOW}Loading demo via litex_term --kernel...${NC}"
            echo -e "${BLUE}Demo: ${PROJECT_WITH_BIT}/demo/demo.bin${NC}"
            echo ""
            litex_term "$SERIAL_PORT" --speed "$BAUDRATE" --kernel "${PROJECT_WITH_BIT}/demo/demo.bin"
        else
            echo -e "${RED}Demo binary not found!${NC}"
            echo -e "${YELLOW}Please build demo first with: --demo${NC}"
            exit 1
        fi
    else
        # Normal terminal (no demo)
        picocom -b "$BAUDRATE" "$SERIAL_PORT"
    fi
}

build_demo_fpga() {
    if [ "$FPGA_CPU" = "ibex" ]; then
        echo -e "${YELLOW}⚠ IBEX: CSR/Zicsr not supported, skipping demo${NC}"
        return 0
    fi

    DEMO_DIR="$(cd "$SCRIPT_DIR" && pwd)/litex/soc/software/demo"

    PROJECT_WITH_BIT=$(find ../fpga_projects -type f \
        -name "*.bit" \
        -path "*/${BOARD}_${FPGA_CPU}_*" \
        2>/dev/null | xargs ls -t 2>/dev/null | head -1 | xargs -I{} dirname {} \
        | sed 's|/build/.*||')

    if [ -z "$PROJECT_WITH_BIT" ] || [ ! -d "$PROJECT_WITH_BIT" ]; then
        echo -e "${RED}No ${FPGA_CPU} bitstream/project found!${NC}"
        return 1
    fi
    PROJECT_WITH_BIT="$(cd "$PROJECT_WITH_BIT" && pwd)"

    BUILD_DIR="${PROJECT_WITH_BIT}/build/${BOARD}"
    if [ ! -d "$BUILD_DIR" ]; then
        echo -e "${RED}Build directory not found at: $BUILD_DIR${NC}"
        return 1
    fi

    echo -e "${BLUE}Using build dir: $BUILD_DIR${NC}"

    cd "$DEMO_DIR"
    rm -rf demo/ demo.bin demo.fbi

    python3 demo.py --build-path="$BUILD_DIR"

    if [ -d "demo" ] && [ -f "demo/demo.bin" ]; then
        cp -r demo/ "$PROJECT_WITH_BIT/"
        echo -e "${GREEN}✓ Demo built and copied to: $PROJECT_WITH_BIT/demo/${NC}"
    else
        echo -e "${RED}Error: demo folder or demo.bin not found!${NC}"
        return 1
    fi

    rm -rf demo/ demo.bin demo.fbi
    cd - > /dev/null
}

# Main function
main() {
    print_banner

    # =============================================
    # Set default clock for CVA6 if not specified
    # CVA6 crashes at 100MHz with WNS -25ns, needs 50MHz
    if [ "$FPGA_CPU" = "cva6" ] && [[ ! "$EXTRA_ARGS" =~ --sys-clk-freq ]]; then
        echo -e "${YELLOW}Note: CVA6 requires 50MHz clock. Adding --sys-clk-freq=50e6${NC}"
        EXTRA_ARGS="$EXTRA_ARGS --sys-clk-freq=50e6"
    fi
    # =============================================
    
    parse_args "$@"
    
    if [ $HELP -eq 1 ]; then
        print_usage
        exit 0
    fi

    if [ $FLAG_HELP -eq 1 ]; then
        print_flag
        exit 0
    fi

    # Check for IBEX + demo combination
    if [ "$FPGA_CPU" = "ibex" ] && [ "$DEMO_MODE" = "1" ]; then
        echo -e "${RED}⚠ IBEX CPU does not support CSR/Zicsr instructions required by demo. And give illegal instruction${NC}"
        echo -e "${RED}⚠ Running FPGA build without demo...${NC}"
        DEMO_MODE=0
        echo ""
    fi

    echo -e "${BLUE}Board: $BOARD${NC}"
    [ -n "$BOARD_VARIANT" ] && echo -e "${BLUE}Board variant: $BOARD_VARIANT${NC}"
    echo -e "${BLUE}CPU: $FPGA_CPU${NC}"
    echo -e "${BLUE}CPU variant: $CPU_VARIANT${NC}"
    if [ -n "$EXTRA_ARGS" ]; then
        echo -e "${BLUE}Extra args: $EXTRA_ARGS${NC}"
    fi
    echo ""
    
    # --flash-only: just flash existing bitstream for the specified CPU + open terminal
    if [ "$FLASH_ONLY" = "1" ]; then
        echo -e "${YELLOW}Flash-only mode: searching for existing ${FPGA_CPU} bitstream...${NC}"
        
        if find_existing_bitstream > /dev/null; then
            BITSTREAM=$(find_existing_bitstream)
            echo -e "${GREEN}✓ Found bitstream: $BITSTREAM${NC}"
        else
            echo -e "${RED}✗ No ${FPGA_CPU} bitstream found in ../fpga_projects/${NC}"
            echo -e "${YELLOW}Please run full setup to build a bitstream first:${NC}"
            echo -e "${BLUE}  ./fpga_setup.sh --cpu=${FPGA_CPU}${NC}"
            exit 1
        fi
        
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        

        # Build demo if --demo flag
        if [ "$DEMO_MODE" = "1" ] && [ "$FPGA_CPU" != "ibex" ]; then
            build_demo_fpga
        fi

        flash_bitstream
        open_terminal
        exit 0
    fi
    
    # --fpga-only: skip dependency checks
    if [ "$FPGA_ONLY" = "1" ]; then
        echo -e "${YELLOW}FPGA-only mode: skipping dependency checks${NC}"
        if [ -d "venv" ]; then
            source venv/bin/activate
        else
            echo -e "${RED}Error: Virtual environment not found. Run full setup first.${NC}"
            exit 1
        fi
        build_bitstream
        flash_bitstream
        open_terminal
        exit 0
    fi
    
    # Full flow
    install_system_deps
    setup_venv
    run_litex_setup
    build_bitstream

    # Build demo if --demo flag
    if [ "$DEMO_MODE" = "1" ] && [ "$FPGA_CPU" != "ibex" ]; then
        build_demo_fpga
    fi

    flash_bitstream
    open_terminal
}

main "$@"