#!/bin/bash

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# Default values
SERIAL_PORT="/dev/ttyUSB1"
BAUDRATE="115200"

# Find project path
find_project() {
    local search_path="${1:-../fpga_projects}"
    
    # If specific path provided, use it
    if [ -n "$1" ] && [ -d "$1" ]; then
        echo "$(cd "$1" && pwd)"
        return 0
    fi
    
    # Find all digilent_arty_vexriscv_smp_* folders
    local projects=$(find "$search_path" -maxdepth 1 -type d -name "digilent_arty_vexriscv_smp_*" 2>/dev/null | sort -r)
    
    # If demo mode, find project with demo folder
    if [ "$DEMO_MODE" = "1" ]; then
        for proj in $projects; do
            if [ -d "$proj/demo" ] && [ -f "$proj/demo/demo.elf" ]; then
                echo "$(cd "$proj" && pwd)"
                return 0
            fi
        done
    fi
    
    # Return the most recent project
    for proj in $projects; do
        echo "$(cd "$proj" && pwd)"
        return 0
    done
    
    # No project found
    return 1
}

# Parse arguments
DEMO_MODE=0
PROJECT_PATH=""
LITEX_TERM=0

while [[ $# -gt 0 ]]; do
    case $1 in
        --demo)
            DEMO_MODE=1
            shift
            ;;
        litex_term)
            LITEX_TERM=1
            shift
            ;;
        --help|-h)
            echo "Usage: ./debug.sh [OPTIONS] [path]"
            echo ""
            echo "Options:"
            echo "  --demo          Prefer projects with demo folder"
            echo "  litex_term      Open serial terminal (BIOS only)"
            echo "  --help, -h      Show this help"
            echo ""
            echo "Examples:"
            echo "  ./debug.sh                          # Auto-detect latest project"
            echo "  ./debug.sh --demo                   # Auto-detect project with demo"
            echo "  ./debug.sh litex_term               # Open serial terminal (BIOS)"
            echo "  ./debug.sh ../fpga_projects/...     # Use specific project"
            exit 0
            ;;
        *)
            PROJECT_PATH="$1"
            shift
            ;;
    esac
done

# Handle litex_term mode (BIOS only)
if [ "$LITEX_TERM" = "1" ]; then
    echo -e "${YELLOW}Opening serial terminal (BIOS)...${NC}"
    echo -e "${BLUE}Port: $SERIAL_PORT${NC}"
    echo -e "${BLUE}Baudrate: $BAUDRATE${NC}"
    echo -e "${YELLOW}Press Ctrl+A then Ctrl+X to exit${NC}"
    echo ""
    
    if [ ! -c "$SERIAL_PORT" ]; then
        echo -e "${RED}✗ Serial port $SERIAL_PORT not found.${NC}"
        echo -e "${YELLOW}Available ports:${NC}"
        ls /dev/ttyUSB* 2>/dev/null || echo "    No /dev/ttyUSB* found"
        echo ""
        echo -e "${YELLOW}Override: export SERIAL_PORT=/dev/ttyUSB0${NC}"
        exit 1
    fi
    
    # Check if picocom exists
    if ! command -v picocom &> /dev/null; then
        echo -e "${YELLOW}Installing picocom...${NC}"
        sudo apt-get install -y picocom
    fi
    
    picocom -b "$BAUDRATE" "$SERIAL_PORT"
    exit 0
fi

# Find project
if [ -n "$PROJECT_PATH" ]; then
    if [ -d "$PROJECT_PATH" ]; then
        PROJECT_PATH="$(cd "$PROJECT_PATH" && pwd)"
    else
        echo -e "${RED}⚠ Project not found: $PROJECT_PATH${NC}"
        exit 1
    fi
else
    if ! PROJECT_PATH=$(find_project "$PROJECT_PATH"); then
        echo -e "${RED}⚠ No project found in ../fpga_projects/${NC}"
        echo -e "${YELLOW}Run: ./fpga_setup.sh${NC}"
        exit 1
    fi
fi

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}       FPGA Debug Menu${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${GREEN}📁 Project:${NC} ${CYAN}$PROJECT_PATH${NC}"
if [ -d "$PROJECT_PATH/demo" ]; then
    echo -e "${GREEN}📦 Demo:${NC} ${CYAN}Available${NC}"
else
    echo -e "${YELLOW}📦 Demo:${NC} ${YELLOW}Not built (run --demo)${NC}"
fi
echo ""

echo -e "${YELLOW}  1)${NC} Start OpenOCD"
echo -e "${YELLOW}  2)${NC} GDB - Demo"
echo -e "${YELLOW}  3)${NC} GDB - BIOS"
echo -e "${YELLOW}  4)${NC} Load Demo (litex_term --kernel)"
echo -e "${YELLOW}  5)${NC} Open Serial Terminal (BIOS only)"
echo -e "${YELLOW}  6)${NC} Exit"
echo ""
echo -e "${BLUE}----------------------------------------${NC}"
read -p "$(echo -e ${GREEN}"Choice [1-6]: "${NC})" choice

case $choice in
    1)
        echo ""
        echo -e "${YELLOW}Starting OpenOCD...${NC}"
        echo -e "${BLUE}Command: openocd -d2 -f ../litex-boards/litex_boards/prog/openocd_xc7_ft2232.cfg -f litex/config/riscv_jtag_tunneled.cfg${NC}"
        echo ""
        openocd -d2 -f ../litex-boards/litex_boards/prog/openocd_xc7_ft2232.cfg -f litex/config/riscv_jtag_tunneled.cfg
        ;;
    2)
        if [ ! -f "$PROJECT_PATH/demo/demo.elf" ]; then
            echo -e "${RED}demo/demo.elf not found!${NC}"
            echo -e "${YELLOW}Run: ./fpga_setup.sh --demo${NC}"
            exit 1
        fi
        echo ""
        echo -e "${GREEN}Debugging Demo...${NC}"
        echo -e "${BLUE}Project: $PROJECT_PATH${NC}"
        echo -e "${BLUE}Command: gdb-multiarch -q demo/demo.elf -ex \"target extended-remote localhost:3333\"${NC}"
        echo ""
        cd "$PROJECT_PATH"
        gdb-multiarch -q demo/demo.elf -ex "target extended-remote localhost:3333"
        ;;
    3)
        if [ ! -f "$PROJECT_PATH/build/digilent_arty/software/bios/bios.elf" ]; then
            echo -e "${RED}bios.elf not found!${NC}"
            echo -e "${YELLOW}Run: ./fpga_setup.sh${NC}"
            exit 1
        fi
        echo ""
        echo -e "${GREEN}Debugging BIOS...${NC}"
        echo -e "${BLUE}Project: $PROJECT_PATH${NC}"
        echo -e "${BLUE}Command: gdb-multiarch -q build/digilent_arty/software/bios/bios.elf -ex \"target extended-remote localhost:3333\"${NC}"
        echo ""
        cd "$PROJECT_PATH"
        gdb-multiarch -q build/digilent_arty/software/bios/bios.elf -ex "target extended-remote localhost:3333"
        ;;
    4)
        if [ ! -f "$PROJECT_PATH/demo/demo.bin" ]; then
            echo -e "${RED}demo/demo.bin not found!${NC}"
            echo -e "${YELLOW}Run: ./fpga_setup.sh --demo${NC}"
            exit 1
        fi
        echo ""
        echo -e "${YELLOW}Loading Demo...${NC}"
        echo -e "${BLUE}Demo: $PROJECT_PATH/demo/demo.bin${NC}"
        echo -e "${YELLOW}Press Ctrl+A then Ctrl+X to exit${NC}"
        echo ""
        
        if [ ! -c "$SERIAL_PORT" ]; then
            echo -e "${RED}✗ Serial port $SERIAL_PORT not found.${NC}"
            echo -e "${YELLOW}Available ports:${NC}"
            ls /dev/ttyUSB* 2>/dev/null || echo "    No /dev/ttyUSB* found"
            exit 1
        fi
        
        # Check if litex_term exists
        if ! command -v litex_term &> /dev/null; then
            echo -e "${RED}litex_term not found!${NC}"
            echo -e "${YELLOW}Activate venv: source venv/bin/activate${NC}"
            exit 1
        fi
        
        litex_term "$SERIAL_PORT" --speed "$BAUDRATE" --kernel "$PROJECT_PATH/demo/demo.bin"
        ;;
    5)
        echo ""
        echo -e "${YELLOW}Opening serial terminal (BIOS only)...${NC}"
        echo -e "${BLUE}Port: $SERIAL_PORT${NC}"
        echo -e "${BLUE}Baudrate: $BAUDRATE${NC}"
        echo -e "${YELLOW}Press Ctrl+A then Ctrl+X to exit${NC}"
        echo ""
        
        if [ ! -c "$SERIAL_PORT" ]; then
            echo -e "${RED}✗ Serial port $SERIAL_PORT not found.${NC}"
            echo -e "${YELLOW}Available ports:${NC}"
            ls /dev/ttyUSB* 2>/dev/null || echo "    No /dev/ttyUSB* found"
            exit 1
        fi
        
        if ! command -v picocom &> /dev/null; then
            echo -e "${YELLOW}Installing picocom...${NC}"
            sudo apt-get install -y picocom
        fi
        
        picocom -b "$BAUDRATE" "$SERIAL_PORT"
        ;;
    6)
        echo -e "${GREEN}Exiting...${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid choice!${NC}"
        exit 1
        ;;
esac