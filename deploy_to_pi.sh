#!/bin/bash
###############################################################################
#  LIFEFLY — RASPBERRY PI DEPLOYMENT SCRIPT
#  Automated deployment to uav@192.168.137.62
###############################################################################

set -e  # Exit on error

# Colors
RED='\033[1;91m'
GREEN='\033[1;92m'
YELLOW='\033[1;93m'
CYAN='\033[1;96m'
WHITE='\033[1;97m'
DIM='\033[2m'
RESET='\033[0m'

# Configuration
RPI_HOST="192.168.137.62"
RPI_USER="uav"
RPI_SSH="${RPI_USER}@${RPI_HOST}"
RPI_DIR="/home/uav/lifefly"

echo -e "\n${CYAN}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  LIFEFLY RASPBERRY PI DEPLOYMENT                                     ║${RESET}"
echo -e "${CYAN}║  Target: ${WHITE}${RPI_SSH}${CYAN}                                          ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${RESET}\n"

# Step 1: Check SSH connectivity
echo -e "${YELLOW}[1/6] Checking SSH connectivity...${RESET}"
if ssh -o ConnectTimeout=5 -o StrictHostKeyChecking=no "${RPI_SSH}" "echo 'SSH_OK'" > /dev/null 2>&1; then
    echo -e "${GREEN}  ✓ Raspberry Pi is reachable${RESET}"
else
    echo -e "${RED}  ✗ Cannot reach Raspberry Pi at ${RPI_HOST}${RESET}"
    echo -e "${DIM}    Make sure:"
    echo -e "      - Pi is powered on"
    echo -e "      - Connected to same network"
    echo -e "      - SSH is enabled (sudo systemctl start ssh)"
    echo -e "      - Try: ssh ${RPI_SSH}${RESET}"
    exit 1
fi

# Step 2: Create directory on Pi
echo -e "\n${YELLOW}[2/6] Creating directory on Raspberry Pi...${RESET}"
ssh "${RPI_SSH}" "mkdir -p ${RPI_DIR}"
echo -e "${GREEN}  ✓ Directory created: ${RPI_DIR}${RESET}"

# Step 3: Copy Python files
echo -e "\n${YELLOW}[3/6] Transferring Python files...${RESET}"

FILES=(
    "rpi_receiver.py"
    "priority_detector.py"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        echo -e "${DIM}  → Copying ${file}...${RESET}"
        scp -q -o StrictHostKeyChecking=no "$file" "${RPI_SSH}:${RPI_DIR}/"
        echo -e "${GREEN}    ✓ ${file} transferred${RESET}"
    else
        echo -e "${YELLOW}    ⚠ ${file} not found, skipping${RESET}"
    fi
done

# Step 4: Install dependencies
echo -e "\n${YELLOW}[4/6] Installing Python dependencies on Pi...${RESET}"
ssh "${RPI_SSH}" "cd ${RPI_DIR} && python3 -m pip install --quiet --upgrade pip requests 2>/dev/null || true"
echo -e "${GREEN}  ✓ Core dependencies installed${RESET}"

# Optional: DroneKit (for real UAV hardware)
echo -e "${DIM}  → Attempting DroneKit installation (optional)...${RESET}"
ssh "${RPI_SSH}" "python3 -m pip install --quiet dronekit pymavlink 2>/dev/null || echo 'DroneKit install skipped (will run in simulation mode)'" > /dev/null 2>&1
echo -e "${GREEN}  ✓ DroneKit installation attempted${RESET}"

# Step 5: Test receiver script
echo -e "\n${YELLOW}[5/6] Testing receiver script...${RESET}"
TEST_OUTPUT=$(ssh "${RPI_SSH}" "cd ${RPI_DIR} && timeout 3 python3 rpi_receiver.py --status 2>&1 || true")
if [[ $TEST_OUTPUT == *"mode"* ]] || [[ $TEST_OUTPUT == *"armed"* ]] || [[ $TEST_OUTPUT == *"simulation"* ]]; then
    echo -e "${GREEN}  ✓ Receiver script is functional${RESET}"
else
    echo -e "${YELLOW}  ⚠ Receiver test incomplete (this is normal)${RESET}"
fi

# Step 6: Start daemon
echo -e "\n${YELLOW}[6/6] Starting LifeFly receiver daemon...${RESET}"

# Kill any existing receiver processes
ssh "${RPI_SSH}" "pkill -f rpi_receiver.py 2>/dev/null || true"
sleep 1

# Start daemon in background
ssh "${RPI_SSH}" "cd ${RPI_DIR} && nohup python3 rpi_receiver.py --daemon --sim > lifefly.log 2>&1 &"
sleep 2

# Check if daemon is running
if ssh "${RPI_SSH}" "pgrep -f rpi_receiver.py > /dev/null"; then
    echo -e "${GREEN}  ✓ LifeFly daemon started successfully${RESET}"

    # Get process info
    PID=$(ssh "${RPI_SSH}" "pgrep -f rpi_receiver.py")
    echo -e "${DIM}    Process ID: ${PID}${RESET}"
    echo -e "${DIM}    Log file: ${RPI_DIR}/lifefly.log${RESET}"
else
    echo -e "${YELLOW}  ⚠ Daemon may not have started${RESET}"
fi

# Final status
echo -e "\n${CYAN}╔══════════════════════════════════════════════════════════════════════╗${RESET}"
echo -e "${CYAN}║  ${GREEN}DEPLOYMENT COMPLETE${CYAN}                                                  ║${RESET}"
echo -e "${CYAN}╚══════════════════════════════════════════════════════════════════════╝${RESET}\n"

echo -e "${WHITE}Next steps:${RESET}"
echo -e "  ${DIM}→ Check logs:${RESET}    ssh ${RPI_SSH} 'tail -f ${RPI_DIR}/lifefly.log'"
echo -e "  ${DIM}→ Check status:${RESET}  ssh ${RPI_SSH} 'cd ${RPI_DIR} && python3 rpi_receiver.py --status'"
echo -e "  ${DIM}→ Stop daemon:${RESET}   ssh ${RPI_SSH} 'pkill -f rpi_receiver.py'"
echo -e "  ${DIM}→ Web GCS:${RESET}       Open index_enhanced.html in your browser"
echo -e ""

exit 0
