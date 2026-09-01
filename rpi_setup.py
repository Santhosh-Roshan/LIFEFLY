#!/usr/bin/env python3
"""
LifeFly Pi Setup Script
Run ON the Raspberry Pi to set up the UAV receiver daemon.
Copy this to the Pi: scp rpi_setup.py uav@192.168.137.62:/home/uav/
Then run:  python3 /home/uav/rpi_setup.py
"""

import os
import subprocess
import sys

HOME = os.path.expanduser("~")
LIFEFLY_DIR = os.path.join(HOME, "lifefly")

def run(cmd):
    print(f"  $ {cmd}")
    subprocess.run(cmd, shell=True, check=True)

def main():
    print("\n╔══════════════════════════════════════════╗")
    print("║  LIFEFLY RASPBERRY PI SETUP              ║")
    print("╚══════════════════════════════════════════╝\n")

    # Create directory
    os.makedirs(LIFEFLY_DIR, exist_ok=True)
    print(f"[✓] Created {LIFEFLY_DIR}")

    # Install dependencies
    print("\n[*] Installing Python dependencies...")
    run(f"{sys.executable} -m pip install --upgrade pip")
    run(f"{sys.executable} -m pip install requests")

    # Try to install DroneKit (optional)
    print("\n[*] Installing DroneKit (optional — for real FC connection)...")
    try:
        run(f"{sys.executable} -m pip install dronekit pymavlink")
        print("[✓] DroneKit installed")
    except Exception:
        print("[!] DroneKit install failed — will run in simulation mode")

    # Create systemd service for auto-start
    service_content = f"""[Unit]
Description=LifeFly UAV Receiver Daemon
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User={os.environ.get('USER', 'uav')}
WorkingDirectory={LIFEFLY_DIR}
ExecStart={sys.executable} {LIFEFLY_DIR}/rpi_receiver.py --daemon --sim
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
"""
    service_path = "/etc/systemd/system/lifefly.service"
    print(f"\n[*] Creating systemd service...")
    try:
        with open("/tmp/lifefly.service", "w") as f:
            f.write(service_content)
        run(f"sudo cp /tmp/lifefly.service {service_path}")
        run("sudo systemctl daemon-reload")
        run("sudo systemctl enable lifefly")
        print(f"[✓] Service installed at {service_path}")
        print("    Start with: sudo systemctl start lifefly")
        print("    Check with: sudo systemctl status lifefly")
    except Exception as e:
        print(f"[!] Service creation failed: {e}")
        print("    You can still run manually: python3 rpi_receiver.py --daemon")

    print(f"""
╔══════════════════════════════════════════════════════════╗
║  SETUP COMPLETE                                          ║
╠══════════════════════════════════════════════════════════╣
║                                                          ║
║  1. Copy rpi_receiver.py to {LIFEFLY_DIR}/
║     scp rpi_receiver.py uav@192.168.137.62:{LIFEFLY_DIR}/
║                                                          ║
║  2. Start the daemon:                                    ║
║     python3 {LIFEFLY_DIR}/rpi_receiver.py --daemon       ║
║                                                          ║
║  3. Or use systemd:                                      ║
║     sudo systemctl start lifefly                         ║
║     sudo systemctl status lifefly                        ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
""")

if __name__ == "__main__":
    main()
