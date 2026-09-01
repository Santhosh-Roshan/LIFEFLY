#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LIFEFLY — RASPBERRY PI UAV RECEIVER                                 ║
║  Priority-Based Intra-Hospital UAV Medical Delivery Network          ║
║  This runs ON the Raspberry Pi (ssh uav@192.168.137.62)              ║
╚══════════════════════════════════════════════════════════════════════╝

DEPLOYMENT: Copy this file to the Raspberry Pi:
  scp rpi_receiver.py uav@192.168.137.62:/home/uav/lifefly/

This script:
  1. Listens to Firebase for incoming mission requests
  2. Manages a priority queue (P1 > P2 > P3 > P4)
  3. Sends MAVLink commands to the flight controller via serial/USB
  4. Reports UAV telemetry back to Firebase
  5. Handles arm, takeoff, navigate, and RTL commands
"""

import json
import time
import random
import datetime
import sys
import os
import argparse
import threading
import math

# ── Dependencies (install on Pi: pip3 install requests dronekit) ──
try:
    import requests
except ImportError:
    print("[!] Install requests: pip3 install requests")
    sys.exit(1)

# DroneKit is optional — runs in simulation mode if not available
DRONEKIT_AVAILABLE = False
try:
    from dronekit import connect, VehicleMode, LocationGlobalRelative
    from pymavlink import mavutil
    DRONEKIT_AVAILABLE = True
except ImportError:
    pass

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"
MISSIONS_URL = f"{FIREBASE_URL}/missions.json"
STATUS_URL   = f"{FIREBASE_URL}/uav_status.json"
ACK_URL      = f"{FIREBASE_URL}/mission_ack.json"

# Flight Controller Connection
# For real Pixhawk via serial: /dev/ttyACM0 or /dev/serial0
# For SITL simulation: tcp:127.0.0.1:5760
FC_CONNECTION_STRING = "/dev/ttyACM0"  # Change as needed
FC_BAUD_RATE = 57600

# UAV Parameters
DEFAULT_ALTITUDE = 25       # meters
CRUISE_SPEED = 12           # m/s (~43 km/h)
MAX_ALTITUDE = 120          # meters (DGCA India limit)
GEOFENCE_RADIUS_KM = 15     # max operating radius

# Priority Levels
PRIORITY_MAP = {
    1: "P1-CRITICAL",
    2: "P2-URGENT",
    3: "P3-STANDARD",
    4: "P4-LOW",
}

# ═══════════════════════════════════════════════════════════════
# ANSI COLORS
# ═══════════════════════════════════════════════════════════════

RESET  = "\033[0m"
CYAN   = "\033[1;96m"
GREEN  = "\033[1;92m"
RED    = "\033[1;91m"
YELLOW = "\033[1;93m"
WHITE  = "\033[1;97m"
DIM    = "\033[2m"
MAGENTA = "\033[1;95m"

# ═══════════════════════════════════════════════════════════════
# UAV CONTROLLER (DroneKit or Simulation)
# ═══════════════════════════════════════════════════════════════

class UAVController:
    """Controls the UAV via DroneKit/MAVLink or simulates flight."""
    
    def __init__(self, connection_string=None, simulation=False):
        self.vehicle = None
        self.simulation = simulation or not DRONEKIT_AVAILABLE
        self.armed = False
        self.altitude = 0.0
        self.mode = "STABILIZE"
        self.battery = 100.0
        self.gps_sats = 0
        self.lat = 17.3850
        self.lng = 78.4867
        self.ground_speed = 0.0
        self.connected = False
        
        if not self.simulation and connection_string:
            try:
                print(f"{CYAN}[UAV] Connecting to flight controller: {connection_string}{RESET}")
                self.vehicle = connect(connection_string, baud=FC_BAUD_RATE, wait_ready=True, timeout=60)
                self.connected = True
                print(f"{GREEN}[UAV] ✓ Flight controller connected{RESET}")
                print(f"  Firmware: {self.vehicle.version}")
                print(f"  Mode:     {self.vehicle.mode.name}")
                print(f"  Armed:    {self.vehicle.armed}")
            except Exception as e:
                print(f"{YELLOW}[UAV] ⚠ FC connection failed: {e}{RESET}")
                print(f"{YELLOW}[UAV] Falling back to SIMULATION mode{RESET}")
                self.simulation = True
        else:
            print(f"{YELLOW}[UAV] Running in SIMULATION mode (no DroneKit){RESET}")
    
    def get_telemetry(self):
        """Get current UAV telemetry data."""
        if self.vehicle and not self.simulation:
            loc = self.vehicle.location.global_relative_frame
            return {
                "mode": self.vehicle.mode.name,
                "armed": self.vehicle.armed,
                "battery_pct": self.vehicle.battery.level if self.vehicle.battery.level else 0,
                "altitude_m": round(loc.alt, 1) if loc else 0,
                "lat": round(loc.lat, 6) if loc else 0,
                "lng": round(loc.lon, 6) if loc else 0,
                "ground_speed_ms": round(self.vehicle.groundspeed, 1),
                "gps_satellites": self.vehicle.gps_0.satellites_visible if self.vehicle.gps_0 else 0,
                "heading_deg": self.vehicle.heading,
                "last_heartbeat": datetime.datetime.now(datetime.timezone.utc).isoformat()
            }
        else:
            # Simulation telemetry
            return {
                "mode": self.mode,
                "armed": self.armed,
                "battery_pct": round(self.battery, 1),
                "altitude_m": round(self.altitude, 1),
                "lat": round(self.lat, 6),
                "lng": round(self.lng, 6),
                "ground_speed_ms": round(self.ground_speed, 1),
                "gps_satellites": self.gps_sats,
                "heading_deg": random.randint(0, 359),
                "last_heartbeat": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "simulation": True
            }
    
    def arm(self):
        """Arm the UAV motors."""
        print(f"{YELLOW}[UAV] Arming motors...{RESET}")
        
        if self.vehicle and not self.simulation:
            self.vehicle.mode = VehicleMode("GUIDED")
            self.vehicle.armed = True
            timeout = 30
            while not self.vehicle.armed and timeout > 0:
                time.sleep(1)
                timeout -= 1
            if self.vehicle.armed:
                print(f"{GREEN}[UAV] ✓ Motors ARMED{RESET}")
                return True
            else:
                print(f"{RED}[UAV] ✗ Arming failed (pre-arm checks?){RESET}")
                return False
        else:
            # Simulation
            time.sleep(1)
            self.armed = True
            self.mode = "GUIDED"
            self.gps_sats = random.randint(10, 18)
            self.battery = 100.0
            print(f"{GREEN}[UAV-SIM] ✓ Motors ARMED (simulated){RESET}")
            return True
    
    def takeoff(self, altitude=DEFAULT_ALTITUDE):
        """Take off to specified altitude."""
        if altitude > MAX_ALTITUDE:
            altitude = MAX_ALTITUDE
            print(f"{YELLOW}[UAV] Altitude clamped to {MAX_ALTITUDE}m (DGCA limit){RESET}")
        
        print(f"{YELLOW}[UAV] Taking off to {altitude}m...{RESET}")
        
        if self.vehicle and not self.simulation:
            self.vehicle.simple_takeoff(altitude)
            while True:
                current_alt = self.vehicle.location.global_relative_frame.alt
                print(f"  Altitude: {current_alt:.1f}m / {altitude}m")
                if current_alt >= altitude * 0.95:
                    print(f"{GREEN}[UAV] ✓ Target altitude reached{RESET}")
                    break
                time.sleep(1)
            return True
        else:
            # Simulation
            for h in range(0, int(altitude) + 1, 5):
                self.altitude = float(h)
                print(f"  {DIM}Altitude: {h}m / {altitude}m{RESET}")
                time.sleep(0.3)
            self.altitude = float(altitude)
            self.ground_speed = 0.0
            print(f"{GREEN}[UAV-SIM] ✓ Altitude {altitude}m reached (simulated){RESET}")
            return True
    
    def navigate(self, target_lat, target_lng, altitude=DEFAULT_ALTITUDE):
        """Navigate to target GPS coordinates."""
        print(f"{YELLOW}[UAV] Navigating to [{target_lat:.6f}, {target_lng:.6f}] @ {altitude}m{RESET}")
        
        if self.vehicle and not self.simulation:
            target = LocationGlobalRelative(target_lat, target_lng, altitude)
            self.vehicle.simple_goto(target, groundspeed=CRUISE_SPEED)
            
            while True:
                current = self.vehicle.location.global_relative_frame
                dist = self._haversine(current.lat, current.lon, target_lat, target_lng)
                print(f"  Distance: {dist*1000:.0f}m")
                if dist < 0.003:  # Within 3 meters
                    print(f"{GREEN}[UAV] ✓ Target reached{RESET}")
                    break
                time.sleep(2)
            return True
        else:
            # Simulation: interpolate position
            steps = 20
            start_lat, start_lng = self.lat, self.lng
            self.ground_speed = CRUISE_SPEED
            
            for i in range(1, steps + 1):
                frac = i / steps
                self.lat = start_lat + (target_lat - start_lat) * frac
                self.lng = start_lng + (target_lng - start_lng) * frac
                self.battery -= 0.2
                
                dist_remaining = self._haversine(self.lat, self.lng, target_lat, target_lng)
                if i % 5 == 0:
                    print(f"  {DIM}Position: [{self.lat:.4f}, {self.lng:.4f}] — {dist_remaining*1000:.0f}m remaining{RESET}")
                time.sleep(0.2)
            
            self.lat = target_lat
            self.lng = target_lng
            self.ground_speed = 0.0
            print(f"{GREEN}[UAV-SIM] ✓ Target reached [{target_lat:.4f}, {target_lng:.4f}] (simulated){RESET}")
            return True
    
    def rtl(self):
        """Return to launch."""
        print(f"{YELLOW}[UAV] Returning to launch...{RESET}")
        
        if self.vehicle and not self.simulation:
            self.vehicle.mode = VehicleMode("RTL")
            return True
        else:
            self.mode = "RTL"
            self.ground_speed = CRUISE_SPEED
            time.sleep(2)
            self.lat = 17.3850
            self.lng = 78.4867
            self.altitude = 0.0
            self.armed = False
            self.ground_speed = 0.0
            self.mode = "STABILIZE"
            print(f"{GREEN}[UAV-SIM] ✓ Returned to base (simulated){RESET}")
            return True
    
    def land(self):
        """Land the UAV."""
        print(f"{YELLOW}[UAV] Landing...{RESET}")
        
        if self.vehicle and not self.simulation:
            self.vehicle.mode = VehicleMode("LAND")
            while self.vehicle.armed:
                time.sleep(1)
            return True
        else:
            self.mode = "LAND"
            for h in range(int(self.altitude), -1, -3):
                self.altitude = max(0, float(h))
                time.sleep(0.2)
            self.altitude = 0.0
            self.armed = False
            self.mode = "STABILIZE"
            print(f"{GREEN}[UAV-SIM] ✓ Landed (simulated){RESET}")
            return True
    
    @staticmethod
    def _haversine(lat1, lon1, lat2, lon2):
        """Distance in km."""
        R = 6371
        dlat = math.radians(lat2 - lat1)
        dlon = math.radians(lon2 - lon1)
        a = (math.sin(dlat/2)**2 +
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
             math.sin(dlon/2)**2)
        return R * 2 * math.asin(math.sqrt(a))
    
    def close(self):
        """Close vehicle connection."""
        if self.vehicle:
            self.vehicle.close()


# ═══════════════════════════════════════════════════════════════
# PRIORITY QUEUE MANAGER
# ═══════════════════════════════════════════════════════════════

class PriorityQueueManager:
    """Manages mission queue sorted by priority."""
    
    def __init__(self):
        self.queue = []
        self.completed = []
        self.active_mission = None
        self.lock = threading.Lock()
    
    def add_mission(self, mission):
        """Add mission and sort by priority."""
        with self.lock:
            self.queue.append(mission)
            # Sort: lower priority number = higher urgency
            self.queue.sort(key=lambda m: (m.get("priority", 3), m.get("timestamp", "")))
        
        pri = mission.get("priority", 3)
        print(f"{MAGENTA}[QUEUE] Added to priority queue: {mission.get('request_id')} — {PRIORITY_MAP.get(pri, 'P3')}{RESET}")
        print(f"  Queue depth: {len(self.queue)} missions")
    
    def get_next_mission(self):
        """Get highest priority mission."""
        with self.lock:
            if self.queue:
                return self.queue.pop(0)
        return None
    
    def peek(self):
        """View next mission without removing."""
        with self.lock:
            return self.queue[0] if self.queue else None
    
    def complete_mission(self, mission):
        """Mark mission as completed."""
        with self.lock:
            mission["completed_at"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            self.completed.append(mission)
            self.active_mission = None
    
    def get_queue_status(self):
        """Get queue summary."""
        with self.lock:
            return {
                "pending": len(self.queue),
                "completed": len(self.completed),
                "active": self.active_mission.get("request_id") if self.active_mission else None,
                "queue": [
                    {"id": m.get("request_id"), "priority": PRIORITY_MAP.get(m.get("priority", 3))}
                    for m in self.queue
                ]
            }


# ═══════════════════════════════════════════════════════════════
# FIREBASE SYNC
# ═══════════════════════════════════════════════════════════════

def update_firebase_status(telemetry_data):
    """Push UAV status to Firebase."""
    try:
        requests.put(STATUS_URL, json=telemetry_data, timeout=5)
    except:
        pass


def update_mission_status_firebase(firebase_key, status, extra=None):
    """Update a mission's status in Firebase."""
    url = f"{FIREBASE_URL}/missions/{firebase_key}.json"
    update = {"status": status}
    if extra:
        update.update(extra)
    try:
        requests.patch(url, json=update, timeout=5)
    except:
        pass


def send_mission_ack(mission_id, status, details=""):
    """Send acknowledgment back to Firebase."""
    ack = {
        "mission_id": mission_id,
        "status": status,
        "details": details,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "RASPBERRY_PI"
    }
    try:
        requests.post(ACK_URL, json=ack, timeout=5)
    except:
        pass


def fetch_pending_missions():
    """Fetch all QUEUED/TRANSMITTED missions from Firebase."""
    try:
        response = requests.get(MISSIONS_URL, timeout=10)
        if response.status_code == 200 and response.json():
            missions = response.json()
            pending = {}
            for key, m in missions.items():
                status = m.get("status", "QUEUED")
                if status in ["QUEUED", "TRANSMITTED"]:
                    m["_firebase_key"] = key
                    pending[key] = m
            return pending
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════
# MISSION EXECUTOR
# ═══════════════════════════════════════════════════════════════

def execute_mission(uav, queue_mgr, mission):
    """Execute a single mission: arm → takeoff → navigate → land → RTL."""
    mission_id = mission.get("request_id", "UNKNOWN")
    fb_key = mission.get("_firebase_key", "")
    target_lat = float(mission.get("latitude", 17.3850))
    target_lng = float(mission.get("longitude", 78.4867))
    priority = mission.get("priority", 3)
    
    print(f"\n{'▓' * 65}")
    print(f" {RED if priority == 1 else YELLOW if priority == 2 else GREEN}⚡ EXECUTING MISSION: {mission_id} — {PRIORITY_MAP.get(priority, 'P3')}{RESET}")
    print(f"{'▓' * 65}")
    print(f" Target: [{target_lat:.6f}, {target_lng:.6f}]")
    print(f" Branch: {mission.get('branch_name', 'N/A')}")
    print(f" Payload: {mission.get('request_details', 'N/A')}")
    print(f"{'─' * 65}")
    
    queue_mgr.active_mission = mission
    
    # Update Firebase status
    if fb_key:
        update_mission_status_firebase(fb_key, "ARMING")
    send_mission_ack(mission_id, "ARMING", "Pre-flight checks in progress")
    
    # 1. ARM
    print(f"\n{CYAN}[STEP 1/5] Pre-flight & Arming{RESET}")
    if not uav.arm():
        print(f"{RED}[!] Arming failed — mission aborted{RESET}")
        if fb_key:
            update_mission_status_firebase(fb_key, "FAILED", {"error": "Arming failed"})
        send_mission_ack(mission_id, "FAILED", "Unable to arm motors")
        return False
    
    if fb_key:
        update_mission_status_firebase(fb_key, "ARMED")
    update_firebase_status(uav.get_telemetry())
    
    # 2. TAKEOFF
    print(f"\n{CYAN}[STEP 2/5] Takeoff{RESET}")
    altitude = mission.get("altitude", DEFAULT_ALTITUDE)
    uav.takeoff(altitude)
    
    if fb_key:
        update_mission_status_firebase(fb_key, "IN_FLIGHT")
    send_mission_ack(mission_id, "IN_FLIGHT", f"Airborne at {altitude}m")
    update_firebase_status(uav.get_telemetry())
    
    # 3. NAVIGATE TO TARGET
    print(f"\n{CYAN}[STEP 3/5] En Route to Target{RESET}")
    uav.navigate(target_lat, target_lng, altitude)
    
    if fb_key:
        update_mission_status_firebase(fb_key, "AT_TARGET")
    send_mission_ack(mission_id, "AT_TARGET", "Payload delivery zone reached")
    update_firebase_status(uav.get_telemetry())
    
    # 4. PAYLOAD DELIVERY (hover & drop)
    print(f"\n{CYAN}[STEP 4/5] Payload Delivery{RESET}")
    print(f"{GREEN}  Hovering over target... Deploying payload...{RESET}")
    time.sleep(2)  # Simulate delivery
    
    if fb_key:
        update_mission_status_firebase(fb_key, "DELIVERED")
    send_mission_ack(mission_id, "DELIVERED", "Payload dropped successfully")
    
    # 5. RETURN TO BASE
    print(f"\n{CYAN}[STEP 5/5] Return to Launch{RESET}")
    uav.rtl()
    
    if fb_key:
        update_mission_status_firebase(fb_key, "COMPLETED")
    send_mission_ack(mission_id, "COMPLETED", "Mission complete. UAV at base.")
    update_firebase_status(uav.get_telemetry())
    
    # Mark complete in queue
    queue_mgr.complete_mission(mission)
    
    print(f"\n{'═' * 65}")
    print(f" {GREEN}✓ MISSION {mission_id} COMPLETED SUCCESSFULLY{RESET}")
    print(f"{'═' * 65}\n")
    
    return True


# ═══════════════════════════════════════════════════════════════
# TELEMETRY REPORTER (Background Thread)
# ═══════════════════════════════════════════════════════════════

def telemetry_reporter(uav, interval=5):
    """Periodically report telemetry to Firebase."""
    while True:
        try:
            telemetry = uav.get_telemetry()
            update_firebase_status(telemetry)
        except:
            pass
        time.sleep(interval)


# ═══════════════════════════════════════════════════════════════
# FIREBASE MISSION LISTENER (Background Thread)
# ═══════════════════════════════════════════════════════════════

def firebase_mission_listener(queue_mgr, processed_ids):
    """Listen for new missions from Firebase and add to priority queue."""
    
    # Pre-load existing missions
    try:
        existing = fetch_pending_missions()
        for key in existing:
            processed_ids.add(key)
    except:
        pass
    
    while True:
        try:
            all_missions = {}
            response = requests.get(MISSIONS_URL, timeout=10)
            if response.status_code == 200 and response.json():
                all_missions = response.json()
            
            for key, mission in all_missions.items():
                if key not in processed_ids:
                    status = mission.get("status", "QUEUED")
                    if status in ["QUEUED", "TRANSMITTED"]:
                        processed_ids.add(key)
                        mission["_firebase_key"] = key
                        
                        # Assign priority if missing
                        if "priority" not in mission:
                            weights = [15, 25, 40, 20]
                            mission["priority"] = random.choices([1, 2, 3, 4], weights=weights, k=1)[0]
                            # Update Firebase
                            url = f"{FIREBASE_URL}/missions/{key}.json"
                            try:
                                requests.patch(url, json={
                                    "priority": mission["priority"],
                                    "priority_label": PRIORITY_MAP.get(mission["priority"], "P3-STANDARD")
                                }, timeout=5)
                            except:
                                pass
                        
                        queue_mgr.add_mission(mission)
                        send_mission_ack(
                            mission.get("request_id", key),
                            "RECEIVED",
                            "Mission received by Raspberry Pi"
                        )
        except:
            pass
        
        time.sleep(3)


# ═══════════════════════════════════════════════════════════════
# MISSION PROCESSOR (Background Thread)
# ═══════════════════════════════════════════════════════════════

def mission_processor(uav, queue_mgr):
    """Process missions from the priority queue one by one."""
    while True:
        mission = queue_mgr.get_next_mission()
        if mission:
            execute_mission(uav, queue_mgr, mission)
            time.sleep(2)  # Cool down between missions
        else:
            time.sleep(3)


# ═══════════════════════════════════════════════════════════════
# CLI ARGUMENT HANDLER
# ═══════════════════════════════════════════════════════════════

def handle_cli_args():
    """Handle command-line arguments for direct SSH commands."""
    parser = argparse.ArgumentParser(description="LifeFly RPi UAV Receiver")
    parser.add_argument("--arm", action="store_true", help="Arm the UAV")
    parser.add_argument("--takeoff", type=float, nargs="?", const=25, help="Takeoff to altitude (m)")
    parser.add_argument("--navigate", nargs=3, type=float, metavar=("LAT", "LNG", "ALT"), help="Navigate to coords")
    parser.add_argument("--rtl", action="store_true", help="Return to launch")
    parser.add_argument("--land", action="store_true", help="Land immediately")
    parser.add_argument("--status", action="store_true", help="Print UAV status")
    parser.add_argument("--execute-mission", action="store_true", help="Execute mission from active_mission.json")
    parser.add_argument("--daemon", action="store_true", help="Run as background daemon (full listener mode)")
    parser.add_argument("--sim", action="store_true", help="Force simulation mode")
    parser.add_argument("--connection", type=str, default=FC_CONNECTION_STRING, help="FC connection string")
    
    return parser.parse_args()


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════

def main():
    args = handle_cli_args()
    
    # Initialize UAV controller
    uav = UAVController(
        connection_string=args.connection,
        simulation=args.sim or not DRONEKIT_AVAILABLE
    )
    
    # Handle direct CLI commands (called via SSH from laptop)
    if args.arm:
        uav.arm()
        print(json.dumps(uav.get_telemetry()))
        return
    
    if args.takeoff is not None:
        uav.arm()
        uav.takeoff(args.takeoff)
        print(json.dumps(uav.get_telemetry()))
        return
    
    if args.navigate:
        lat, lng, alt = args.navigate
        uav.navigate(lat, lng, alt)
        print(json.dumps(uav.get_telemetry()))
        return
    
    if args.rtl:
        uav.rtl()
        return
    
    if args.land:
        uav.land()
        return
    
    if args.status:
        print(json.dumps(uav.get_telemetry(), indent=2))
        return
    
    if args.execute_mission:
        mission_file = "/home/uav/lifefly/active_mission.json"
        if os.path.exists(mission_file):
            with open(mission_file, "r") as f:
                mission = json.load(f)
            qm = PriorityQueueManager()
            execute_mission(uav, qm, mission)
        else:
            print(f"{RED}[!] No active mission file found{RESET}")
        return
    
    # ── DAEMON MODE: Full listener with priority queue ──
    if args.daemon or True:  # Default to daemon mode
        print(f"""
{CYAN}╔══════════════════════════════════════════════════════════════╗
║  LIFEFLY RASPBERRY PI — UAV RECEIVER DAEMON                  ║
║  Priority-Based Intra-Hospital Medical Delivery               ║
╚══════════════════════════════════════════════════════════════╝{RESET}
        """)
        
        print(f" {DIM}Firebase:{RESET}  {GREEN}{FIREBASE_URL}{RESET}")
        print(f" {DIM}Mode:{RESET}     {YELLOW}{'SIMULATION' if uav.simulation else 'LIVE FLIGHT'}{RESET}")
        print(f" {DIM}FC:{RESET}       {args.connection}")
        print()
        
        queue_mgr = PriorityQueueManager()
        processed_ids = set()
        
        # Start background threads
        telemetry_thread = threading.Thread(
            target=telemetry_reporter, args=(uav,), daemon=True
        )
        telemetry_thread.start()
        print(f"{GREEN}[+] Telemetry reporter started (5s interval){RESET}")
        
        listener_thread = threading.Thread(
            target=firebase_mission_listener, args=(queue_mgr, processed_ids), daemon=True
        )
        listener_thread.start()
        print(f"{GREEN}[+] Firebase mission listener started{RESET}")
        
        processor_thread = threading.Thread(
            target=mission_processor, args=(uav, queue_mgr), daemon=True
        )
        processor_thread.start()
        print(f"{GREEN}[+] Mission processor started (priority queue active){RESET}")
        
        print(f"\n{CYAN}[*] All systems GO — Waiting for missions...{RESET}")
        print(f"{DIM}    Press Ctrl+C to shutdown{RESET}\n")
        
        try:
            while True:
                time.sleep(10)
                status = queue_mgr.get_queue_status()
                if status["pending"] > 0 or status["active"]:
                    print(f" {DIM}[QUEUE] Pending: {status['pending']} | "
                          f"Active: {status['active'] or 'None'} | "
                          f"Completed: {status['completed']}{RESET}")
        except KeyboardInterrupt:
            print(f"\n{RED}[×] LifeFly Pi Receiver shutting down...{RESET}")
            uav.close()


if __name__ == "__main__":
    main()
