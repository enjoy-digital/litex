#!/bin/bash
# EmuLiteX - VexRiscv-SMP Linux on FPGA Setup Script
# Usage: ./vexriscv_smp_linux_fpga_setup.sh

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Default values
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LINUX_IMAGES_DIR="${SCRIPT_DIR}/../linux_images"
CPU_TYPE="vexriscv_smp"

BOARD="digilent_arty"
BOARD_VARIANT="a7-100"
FLASH_ONLY=0
HELP=0
EXTRA_ARGS=""
PROJECT_WITH_BIT=""

# Print banner
print_banner() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  VexRiscv-SMP Linux on FPGA Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Print usage
print_usage() {
    cat << EOF
Usage: ./vexriscv_smp_linux_fpga_setup.sh [OPTIONS]

Options:
    --board=NAME        FPGA board: digilent_arty (default)
    --board-variant=VAR Board variant: a7-100, a7-35, s7-50 (default: a7-100)
    --flash-only        Skip build, flash existing bitstream for specified CPU + open terminal
    --extra-args="..."  Extra arguments to pass to the build command (e.g., --sys-clk-freq=100e6)
    --help, -h          Show this help message

Examples:
    ./vexriscv_smp_linux_fpga_setup.sh                    # Full flow: build + flash + terminal
    ./vexriscv_smp_linux_fpga_setup.sh --extra-args="--sys-clk-freq=100e6"  # Build with 100MHz
    ./vexriscv_smp_linux_fpga_setup.sh --extra-args="--sys-clk-freq=50e6 --sdram-rate=1:1"  # Multiple args
    ./vexriscv_smp_linux_fpga_setup.sh --flash-only       # Find latest vexriscv_smp_linux folder and run from that
EOF
}

# Parse arguments
parse_args() {
    EXTRA_ARGS=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --board=*)        BOARD="${1#*=}";          shift ;;
            --board-variant=*) BOARD_VARIANT="${1#*=}"; shift ;;
            --extra-args=*)   EXTRA_ARGS="${1#*=}";     shift ;;
            --flash-only)     FLASH_ONLY=1;             shift ;;
            --help|-h)        HELP=1;                   shift ;;
            --)               shift; EXTRA_ARGS="$*"; break ;;
            *)                echo -e "${RED}Unknown option: $1${NC}"; print_usage; exit 1 ;;
        esac
    done
}

# Find existing bitstream (most recent)
find_existing_bitstream() {
    if [ ! -d "../fpga_projects" ]; then
        return 1
    fi
    
    BITSTREAM=$(find ../fpga_projects/linux_* -type f -name "*.bit" 2>/dev/null | xargs ls -t 2>/dev/null | head -1)
    
    if [ -n "$BITSTREAM" ] && [ -f "$BITSTREAM" ]; then
        echo "$BITSTREAM"
        return 0
    else
        return 1
    fi
}

# Function to setup Linux images
setup_linux_images() {
    echo -e "\n${YELLOW}Setting up Linux images for ${CPU_TYPE}...${NC}"
    
    # Create linux_images directory if it doesn't exist
    if [ ! -d "${LINUX_IMAGES_DIR}" ]; then
        echo -e "${YELLOW}Creating ${LINUX_IMAGES_DIR}...${NC}"
        mkdir -p "${LINUX_IMAGES_DIR}"
    fi
    
    # Create CPU-specific directory if it doesn't exist
    if [ ! -d "${LINUX_IMAGES_DIR}/${CPU_TYPE}" ]; then
        echo -e "${YELLOW}Creating ${LINUX_IMAGES_DIR}/${CPU_TYPE}...${NC}"
        mkdir -p "${LINUX_IMAGES_DIR}/${CPU_TYPE}"
    fi
    
    # Check if images already exist
    if [ -f "${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image/Image" ]; then
        echo -e "${GREEN}✓ Linux images already exist${NC}"
        return 0
    fi
    
    # Download and extract
    echo -e "${YELLOW}Downloading Linux images...${NC}"
    cd "${LINUX_IMAGES_DIR}/${CPU_TYPE}"
    
    # Download the zip file
    wget --header="Referer: https://github.com/litex-hub/linux-on-litex-vexriscv/issues/164" \
         https://github.com/litex-hub/linux-on-litex-vexriscv/files/8331338/linux_2022_03_23.zip
    
    # Create linux_image directory and extract
    mkdir -p linux_image
    unzip linux_2022_03_23.zip -d linux_image/
    
    # Remove the zip file
    rm linux_2022_03_23.zip

    # Create the working boot_ram0.json file  <-- ADD THIS BLOCK
    cat > "${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image/boot_ram0.json" << 'BOOT_EOF'
{
    "Image":       "0x40000000",
    "rv32.dtb":    "0x40ef0000",
    "rootfs.cpio": "0x41000000",
    "opensbi.bin": "0x40f00000"
}
BOOT_EOF
    
    echo -e "${GREEN}✓ Linux images downloaded and extracted${NC}"
    echo -e "${GREEN}  Location: ${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image/${NC}"
}

# Function to create project and copy images
create_project() {
    echo -e "\n${YELLOW}Creating fpga project...${NC}"
    
    # Create fpga_projects directory if it doesn't exist
    FPGA_PROJECTS_DIR="${SCRIPT_DIR}/../fpga_projects"
    if [ ! -d "${FPGA_PROJECTS_DIR}" ]; then
        echo -e "${YELLOW}Creating ${FPGA_PROJECTS_DIR}...${NC}"
        mkdir -p "${FPGA_PROJECTS_DIR}"
    fi
    
    # Create timestamped project directory
    PROJECT_DIR="${FPGA_PROJECTS_DIR}/linux_${CPU_TYPE}_$(date '+%d-%m-%H-%M')"
    mkdir -p "${PROJECT_DIR}"
    
    echo -e "${BLUE}Project directory: ${PROJECT_DIR}${NC}"
    
    # Copy linux_image folder to project directory
    cp -r "${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image" "${PROJECT_DIR}/"
    
    echo -e "${GREEN}✓ Linux images copied to project${NC}"
    echo -e "${GREEN}  Location: ${PROJECT_DIR}/linux_image/${NC}"
}

# Function to build bitstream
build_bitstream() {
    echo -e "\n${YELLOW}Building bitstream...${NC}"
    echo -e "${BLUE}CPU: ${CPU_TYPE}${NC}"
    echo -e "${BLUE}Project: ${PROJECT_DIR}${NC}"
    echo -e "${BLUE}This may take 15-30 minutes...${NC}"
    echo -e "${BLUE}Press Ctrl+C to exit${NC}"
    echo ""
    
    # Check if virtual environment is activated
    if [ -z "$VIRTUAL_ENV" ]; then
        if [ -d "venv" ]; then
            source venv/bin/activate
            echo -e "${GREEN}✓ Virtual environment activated${NC}"
        else
            echo -e "${RED}Error: Virtual environment not found!${NC}"
            exit 1
        fi
    fi
    
    # Run the build from the project directory
    cd "${PROJECT_DIR}"

    TARGET_MODULE="litex_boards.targets.${BOARD}"

    CMD="python3 -m $TARGET_MODULE --build --load --cpu-type=$CPU_TYPE --cpu-variant=linux --uart-baudrate=921600"

    if [ -n "$BOARD_VARIANT" ]; then
        CMD="$CMD --variant=$BOARD_VARIANT"
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
    else
        echo -e "${RED}✗ No bitstream found!${NC}"
        exit 1
    fi
    
    cd - > /dev/null    
}

flash_bitstream() {
    echo -e "\n${YELLOW}Flashing bitstream via OpenOCD (--load)...${NC}"

    # Find the most recent project dir containing a .bit for this CPU
    PROJECT_WITH_BIT=$(find ../fpga_projects/linux_* -type f \
    -name "*.bit" \
    2>/dev/null | xargs ls -t 2>/dev/null | head -1 | xargs -I{} dirname {} \
    | sed 's|/build/.*||')

    if [ -z "$PROJECT_WITH_BIT" ] || [ ! -d "$PROJECT_WITH_BIT" ]; then
        echo -e "${RED}No ${CPU_TYPE} bitstream found in ../fpga_projects/${NC}"
        exit 1
    fi

    echo -e "${BLUE}Project dir: $PROJECT_WITH_BIT${NC}"

    cd "$PROJECT_WITH_BIT"

    CMD="python3 -m litex_boards.targets.${BOARD} --load --cpu-type=$CPU_TYPE"
    [ -n "$BOARD_VARIANT" ] && CMD="$CMD --variant=$BOARD_VARIANT"

    echo -e "${BLUE}Running: $CMD${NC}"
    eval "$CMD"

    cd - > /dev/null
    echo -e "${GREEN}✓ FPGA loaded successfully${NC}"
}

load_linux() {
    echo -e "\n${YELLOW}Loading Linux via litex_term...${NC}"

    LINUX_IMAGE_DIR="${PROJECT_WITH_BIT}/linux_image"
    
    if [ ! -d "$LINUX_IMAGE_DIR" ]; then
        echo -e "${RED}No linux_image found at: $LINUX_IMAGE_DIR${NC}"
        echo -e "${YELLOW}Please run full setup first:${NC}"
        echo -e "${BLUE}  ./vexriscv_smp_linux_fpga_setup.sh${NC}"
        exit 1
    fi
    
    echo -e "${BLUE}Linux images: $LINUX_IMAGE_DIR${NC}"
    echo -e "${BLUE}Serial port: /dev/ttyUSB1${NC}"
    echo -e "${BLUE}Baudrate: 921600${NC}"
    echo -e "${YELLOW}Press Ctrl+A then Ctrl+X to exit litex_term${NC}"
    echo ""
    
    litex_term /dev/ttyUSB1 --speed 921600 \
        --images "${LINUX_IMAGE_DIR}/boot.json" 
}

# Main function
main() {
    print_banner
    parse_args "$@"
    
    if [ $HELP -eq 1 ]; then
        print_usage
        exit 0
    fi

    # --flash-only: just flash existing bitstream for the vexriscv_smp CPU + open terminal
    if [ "$FLASH_ONLY" = "1" ]; then
        echo -e "${YELLOW}Flash-only mode: searching for existing ${CPU_TYPE} bitstream...${NC}"
        
        BITSTREAM=$(find_existing_bitstream)
        if [ -n "$BITSTREAM" ]; then
            echo -e "${GREEN}✓ Found bitstream: $BITSTREAM${NC}"
        else
            echo -e "${RED}✗ No ${CPU_TYPE} bitstream found in ../fpga_projects/${NC}"
            echo -e "${YELLOW}Please run full setup to build a bitstream first:${NC}"
            echo -e "${BLUE}  ./vexriscv_smp_linux_fpga_setup.sh${NC}"
            exit 1
        fi
        
        if [ -d "venv" ]; then
            source venv/bin/activate
        fi
        
        flash_bitstream
        load_linux
        exit 0
    fi

    setup_linux_images
    create_project
    
    echo -e "\n${GREEN}✓ Setup complete!${NC}"
    echo -e "${BLUE}Images are in: ${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image/${NC}"
    echo -e "${BLUE}Project: ${PROJECT_DIR}${NC}"
    echo ""
    
    build_bitstream
    flash_bitstream
    load_linux
}

# Run main
main "$@"
