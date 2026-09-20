#!/usr/bin/env python3
"""
LIFEFLY — Laptop Deploy & Monitor Script
Runs on your LAPTOP. Deploys pi_listener.py to the Raspberry Pi
via SSH and starts it. Also monitors the connection.

Usage: python deploy_and_run.py
"""

import subprocess
import sys
import os
import time

RPI_HOST = "192.168.137.62"
RPI_USER = "uav"
RPI_SSH = f"{RPI_USER}@{RPI_HOST}"
PI_DIR = "/home/uav/lifefly"

CYAN = "\033[1;96m"
GREEN = "\033[1;92m"
RED = "\033[1;91m"
YELLOW = "\033[1;93m"
WHITE = "\033[1;97m"
DIM = "\033[2m"
RESET = "\033[0m"

def run_ssh(cmd, timeout=15):
    """Run a command on Pi via SSH."""
    full = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", RPI_SSH, cmd]
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=timeout)
        return result.returncode == 0, result.stdout.strip(), result.stderr.strip()
    except subprocess.TimeoutExpired:
        return False, "", "Timeout"
    except Exception as e:
        return False, "", str(e)

def run_scp(local_file, remote_path):
    """Copy a file to Pi via SCP."""
    full = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=10", local_file, f"{RPI_SSH}:{remote_path}"]
    try:
        result = subprocess.run(full, capture_output=True, text=True, timeout=30)
        return result.returncode == 0, result.stderr.strip()
    except Exception as e:
        return False, str(e)

def main():
    print(f"""
{CYAN}╔═══════════════════════════════════════════════════════╗
║  LIFEFLY — DEPLOY TO RASPBERRY Pi                     ║
║  Target: ssh {RPI_SSH:<37} ║
╚═══════════════════════════════════════════════════════╝{RESET}
    """)

    # Step 1: Check SSH connection
    print(f"{WHITE}[Step 1/4]{RESET} Testing SSH connection to {RPI_SSH}...")
    ok, out, err = run_ssh("echo OK")
    if not ok:
        print(f"{RED}  ✗ Cannot reach Pi: {err}{RESET}")
        print(f"\n{YELLOW}  Make sure:{RESET}")
        print(f"    1. Raspberry Pi is powered ON")
        print(f"    2. Pi is connected to same network (hotspot/WiFi)")
        print(f"    3. SSH is enabled on Pi (sudo raspi-config → Interface → SSH)")
        print(f"    4. IP is correct: {RPI_HOST}")
        print(f"\n  {DIM}Try: ssh {RPI_SSH}{RESET}")
        sys.exit(1)
    print(f"{GREEN}  ✓ Pi is ONLINE{RESET}")

    # Step 2: Create directory on Pi
    print(f"\n{WHITE}[Step 2/4]{RESET} Creating directory on Pi...")
    run_ssh(f"mkdir -p {PI_DIR}")
    print(f"{GREEN}  ✓ {PI_DIR} ready{RESET}")

    # Step 3: Install requests on Pi
    print(f"\n{WHITE}[Step 3/4]{RESET} Installing Python requests on Pi...")
    ok, out, err = run_ssh("pip3 install requests 2>&1 | tail -1", timeout=60)
    if ok:
        print(f"{GREEN}  ✓ requests installed{RESET}")
    else:
        print(f"{YELLOW}  ⚠ Trying with --break-system-packages...{RESET}")
        run_ssh("pip3 install requests --break-system-packages 2>&1 | tail -1", timeout=60)

    # Step 4: Copy pi_listener.py to Pi
    print(f"\n{WHITE}[Step 4/4]{RESET} Copying pi_listener.py to Pi...")
    script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pi_listener.py")
    if not os.path.exists(script_path):
        print(f"{RED}  ✗ pi_listener.py not found at {script_path}{RESET}")
        sys.exit(1)

    ok, err = run_scp(script_path, f"{PI_DIR}/pi_listener.py")
    if ok:
        print(f"{GREEN}  ✓ pi_listener.py copied to Pi{RESET}")
    else:
        print(f"{RED}  ✗ Copy failed: {err}{RESET}")
        sys.exit(1)

    # Done!
    print(f"""
{GREEN}{'=' * 55}
  ✓ DEPLOYMENT COMPLETE!
{'=' * 55}{RESET}

{WHITE}Now run the listener on Pi. Choose one option:{RESET}

{CYAN}Option A — Run from this laptop (SSH auto-start):{RESET}
  ssh {RPI_SSH} "python3 {PI_DIR}/pi_listener.py"

{CYAN}Option B — SSH into Pi and run manually:{RESET}
  ssh {RPI_SSH}
  python3 {PI_DIR}/pi_listener.py

{DIM}The script will show all missions from Firebase sorted by priority.
New missions dispatched from the website will appear in real-time.{RESET}
""")

    # Ask if user wants to start it now
    choice = input(f"{CYAN}Start pi_listener.py on Pi now? (y/n): {RESET}").strip().lower()
    if choice == 'y':
        print(f"\n{GREEN}[+] Starting pi_listener.py on Pi...{RESET}")
        print(f"{DIM}    (Press Ctrl+C to stop){RESET}\n")

        # Run interactively so user sees output
        try:
            proc = subprocess.Popen(
                ["ssh", "-o", "StrictHostKeyChecking=no", "-t", RPI_SSH,
                 f"python3 {PI_DIR}/pi_listener.py"],
                stdin=sys.stdin
            )
            proc.wait()
        except KeyboardInterrupt:
            print(f"\n{YELLOW}[!] Disconnected from Pi.{RESET}")
    else:
        print(f"\n{DIM}Run it later with: ssh {RPI_SSH} \"python3 {PI_DIR}/pi_listener.py\"{RESET}")

if __name__ == "__main__":
    main()
