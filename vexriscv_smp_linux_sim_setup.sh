#!/bin/bash
# EmuLiteX - VexRiscv-SMP Linux Simulation Setup Script
# Usage: ./vexriscv_smp_linux_sim_setup.sh

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
EXTRA_ARGS=""
FLAG=0
HELP=0

# Print banner
print_banner() {
    echo -e "${BLUE}========================================${NC}"
    echo -e "${BLUE}  VexRiscv-SMP Linux Simulation Setup${NC}"
    echo -e "${BLUE}========================================${NC}"
    echo ""
}

# Print usage
print_usage() {
    cat << EOF
Usage: ./vexriscv_smp_linux_sim_setup.sh [OPTIONS]

Options:
    --extra-args="..."  Extra arguments to pass to litex_sim (e.g., --trace --trace-fst --sim-debug)
    --flag              see all flags for simulation
    --help, -h          Show this help message

Examples:
    ./vexriscv_smp_linux_sim_setup.sh                              # Run simulation
    ./vexriscv_smp_linux_sim_setup.sh --extra-args="--trace"      # Run with tracing
    ./vexriscv_smp_linux_sim_setup.sh --extra-args="--trace --trace-fst --sim-debug"  # Multiple args
EOF
}

# Parse arguments
parse_args() {
    EXTRA_ARGS=""
    while [[ $# -gt 0 ]]; do
        case $1 in
            --extra-args=*)   EXTRA_ARGS="${1#*=}";     shift ;;
            --flag) FLAG=1; shift ;;
            --help|-h)        HELP=1;                   shift ;;
            --)               shift; EXTRA_ARGS="$*"; break ;;
            *)                echo -e "${RED}Unknown option: $1${NC}"; print_usage; exit 1 ;;
        esac
    done
}

# Function to check if command exists
sim_flags() {

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
        
    litex_sim --help
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
    echo -e "\n${YELLOW}Creating simulation project...${NC}"
    
    # Create sim_projects directory if it doesn't exist
    SIM_PROJECTS_DIR="${SCRIPT_DIR}/../sim_projects"
    if [ ! -d "${SIM_PROJECTS_DIR}" ]; then
        echo -e "${YELLOW}Creating ${SIM_PROJECTS_DIR}...${NC}"
        mkdir -p "${SIM_PROJECTS_DIR}"
    fi
    
    # Create timestamped project directory
    PROJECT_DIR="${SIM_PROJECTS_DIR}/linux_${CPU_TYPE}_$(date '+%d-%m-%H-%M')"
    mkdir -p "${PROJECT_DIR}"
    
    echo -e "${BLUE}Project directory: ${PROJECT_DIR}${NC}"
    
    # Copy linux_image folder to project directory
    cp -r "${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image" "${PROJECT_DIR}/"
    
    echo -e "${GREEN}✓ Linux images copied to project${NC}"
    echo -e "${GREEN}  Location: ${PROJECT_DIR}/linux_image/${NC}"
}

# Function to run the simulation
run_simulation() {
    echo -e "\n${YELLOW}Running Linux simulation...${NC}"
    echo -e "${BLUE}CPU: ${CPU_TYPE}${NC}"
    echo -e "${BLUE}Project: ${PROJECT_DIR}${NC}"
    if [ -n "$EXTRA_ARGS" ]; then
        echo -e "${BLUE}Extra args: $EXTRA_ARGS${NC}"
    fi
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
    
    # Run the simulation from the project directory
    cd "${PROJECT_DIR}"
    echo -e "${GREEN}✓ Changed to project directory: ${BLUE}${PROJECT_DIR}${NC}"
    
    # Build the command
    CMD="litex_sim --cpu-type=\"${CPU_TYPE}\" \
        --cpu-variant=linux \
        --with-sdram \
        --sdram-module=MT48LC16M16 \
        --sdram-init \"${PROJECT_DIR}/linux_image/boot_ram0.json\""
    
    if [ -n "$EXTRA_ARGS" ]; then
        CMD="$CMD $EXTRA_ARGS"
    fi
    
    echo -e "${BLUE}Running: $CMD${NC}"
    echo ""
    
    eval "$CMD"
}

# Main function
main() {
    parse_args "$@"
    
    if [ "$HELP" = "1" ]; then
        print_usage
        exit 0
    fi
    
    # Show flag
    if [ $FLAG -eq 1 ]; then
        sim_flags
        exit 0
    fi    

    print_banner
    setup_linux_images
    create_project
    
    echo -e "\n${GREEN}✓ Setup complete!${NC}"
    echo -e "${BLUE}Images are in: ${LINUX_IMAGES_DIR}/${CPU_TYPE}/linux_image/${NC}"
    echo -e "${BLUE}Project: ${PROJECT_DIR}${NC}"
    echo ""
    
    run_simulation
}

# Run main
main "$@"
