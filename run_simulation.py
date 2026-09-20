#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LIFEFLY — MAVLINK SITL MISSION CONTROLLER                          ║
║  Priority Queue + SITL Drone Simulation via MAVLink                  ║
║  Single Drone Sequential Execution with AI Auto-Priority             ║
╚══════════════════════════════════════════════════════════════════════╝

This script:
  1. Starts a dronekit-sitl MAVLink simulator
  2. Connects to the simulated vehicle via MAVLink
  3. Listens to Firebase for incoming missions from the web app
  4. Auto-assigns priority using AI keyword detection
  5. Queues missions by priority (P1 > P2 > P3 > P4)
  6. Executes missions one-at-a-time via MAVLink (arm→takeoff→nav→RTL)
  7. Updates Firebase in real-time so the hosted web app shows progress
  8. After delivery, marks "Delivered Successfully" and removes from queue
  9. Drone returns to base, picks up next queued mission

View the flight in:
  - Mission Planner (connect to tcp:127.0.0.1:5760)
  - MAVProxy (mavproxy.py --master=tcp:127.0.0.1:5760)
  - The Firebase-hosted web app (index.html) shows the satellite map view
"""

import time
import math
import datetime
import threading
import sys
import os
import requests

# ═══════════════════════════════════════════════════════════════
# DRONEKIT / SITL IMPORTS
# ═══════════════════════════════════════════════════════════════

try:
    import dronekit_sitl
except ImportError:
    print("[!] dronekit-sitl is not installed.")
    print("    Install it: pip install dronekit-sitl")
    print("    Or run in venv_dronekit environment.")
    sys.exit(1)

try:
    from dronekit import connect, VehicleMode, LocationGlobalRelative
except ImportError:
    print("[!] dronekit is not installed.")
    print("    Install it: pip install dronekit")
    sys.exit(1)

API_KEY = "AIzaSyCgHXLUhpMhw0X2XMfoh6WYGey0Y1bFmWI"
try:
    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    res = requests.post(auth_url, json={"returnSecureToken": True}, timeout=3)
    AUTH_TOKEN = "?auth=" + res.json().get("idToken")
except:
    AUTH_TOKEN = ""

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"
MISSIONS_URL = f"{FIREBASE_URL}/missions.json"
STATUS_URL   = f"{FIREBASE_URL}/uav_status.json"
ACK_URL      = f"{FIREBASE_URL}/mission_ack.json"
DRONE_TRACK_URL = f"{FIREBASE_URL}/drone_track.json"

# Base station (home position — SITL default is near Canberra but we override)
BASE_LAT = 17.3850
BASE_LNG = 78.4867
DEFAULT_ALTITUDE = 25  # meters
CRUISE_SPEED = 12      # m/s

# ANSI Colors
RESET   = "\033[0m"
CYAN    = "\033[1;96m"
GREEN   = "\033[1;92m"
RED     = "\033[1;91m"
YELLOW  = "\033[1;93m"
WHITE   = "\033[1;97m"
DIM     = "\033[2m"
MAGENTA = "\033[1;95m"
BOLD    = "\033[1m"

# ═══════════════════════════════════════════════════════════════
# AI PRIORITY DETECTION ENGINE
# ═══════════════════════════════════════════════════════════════

CRITICAL_KEYWORDS = [
    'lung', 'kidney', 'heart', 'liver', 'organ', 'transplant',
    'blood', 'blood pack', 'plasma', 'platelets', 'transfusion',
    'defibrillator', 'aed', 'ventilator',
    'anti-venom', 'antivenom', 'epinephrine', 'epipen', 'naloxone',
    'trauma', 'gunshot', 'hemorrhage', 'stroke', 'cardiac arrest',
    'anaphylaxis', 'sepsis', 'emergency surgery',
]

URGENT_KEYWORDS = [
    'insulin', 'diabetic', 'antibiotic', 'chemotherapy', 'dialysis',
    'surgical', 'oxygen', 'o2', 'iv fluid', 'saline',
    'burn', 'fracture', 'seizure', 'asthma', 'respiratory',
    'biopsy', 'specimen',
]

STANDARD_KEYWORDS = [
    'lab', 'sample', 'pathology', 'test', 'screening',
    'medication', 'medicine', 'prescription', 'pills',
    'bandage', 'dressing', 'syringe', 'gloves', 'mask',
    'vaccination', 'vaccine',
]

LOW_KEYWORDS = [
    'record', 'records', 'paperwork', 'document', 'report',
    'ppe', 'supplies', 'stock', 'bulk', 'inventory', 'non-urgent',
]


def ai_detect_priority(payload_text):
    """AI-based automatic priority detection from payload description."""
    if not payload_text:
        return 3, "P3-STANDARD", "No description provided"
    text = payload_text.lower()
    for kw in CRITICAL_KEYWORDS:
        if kw in text:
            return 1, "P1-CRITICAL", f"Critical keyword: {kw}"
    for kw in URGENT_KEYWORDS:
        if kw in text:
            return 2, "P2-URGENT", f"Urgent keyword: {kw}"
    for kw in LOW_KEYWORDS:
        if kw in text:
            return 4, "P4-LOW", f"Low-priority keyword: {kw}"
    for kw in STANDARD_KEYWORDS:
        if kw in text:
            return 3, "P3-STANDARD", f"Standard keyword: {kw}"
    return 3, "P3-STANDARD", "Default priority assigned"


# ═══════════════════════════════════════════════════════════════
# HAVERSINE DISTANCE
# ═══════════════════════════════════════════════════════════════

def haversine_km(lat1, lon1, lat2, lon2):
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat/2)**2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlon/2)**2)
    return R * 2 * math.asin(math.sqrt(a))


# ═══════════════════════════════════════════════════════════════
# FIREBASE HELPERS
# ═══════════════════════════════════════════════════════════════

def get_auth_url(base_url):
    return base_url + AUTH_TOKEN if "?" not in base_url else base_url + "&" + AUTH_TOKEN.replace("?auth=", "auth=")

def firebase_get(url):
    try:
        r = requests.get(get_auth_url(url), timeout=10)
        if r.status_code == 200:
            return r.json()
    except:
        pass
    return None

def firebase_put(url, data):
    try:
        requests.put(get_auth_url(url), json=data, timeout=10)
    except:
        pass


def firebase_patch(url, data):
    try:
        requests.patch(get_auth_url(url), json=data, timeout=10)
    except:
        pass


def firebase_post(url, data):
    try:
        requests.post(url, json=data, timeout=10)
    except:
        pass


def firebase_delete(url):
    try:
        requests.delete(get_auth_url(url), timeout=10)
    except:
        pass


def update_mission_status(firebase_key, status):
    url = f"{FIREBASE_URL}/missions/{firebase_key}.json"
    firebase_patch(url, {"status": status})


def send_ack(mission_id, status, details=""):
    firebase_post(ACK_URL, {
        "mission_id": mission_id,
        "status": status,
        "details": details,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "source": "SITL_GCS"
    })


def remove_completed_mission(firebase_key):
    url = f"{FIREBASE_URL}/missions/{firebase_key}.json"
    firebase_delete(url)


def push_drone_track(lat, lng, alt, status, mission_id="", heading=0):
    """Push real-time drone position to Firebase for the web app map."""
    firebase_put(DRONE_TRACK_URL, {
        "lat": round(lat, 6),
        "lng": round(lng, 6),
        "alt": round(alt, 1),
        "status": status,
        "mission_id": mission_id,
        "heading": heading,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })


def push_uav_telemetry(vehicle, is_sim=True):
    """Read telemetry from the MAVLink vehicle and push to Firebase."""
    loc = vehicle.location.global_relative_frame
    firebase_put(STATUS_URL, {
        "mode": vehicle.mode.name,
        "armed": vehicle.armed,
        "battery_pct": vehicle.battery.level if vehicle.battery and vehicle.battery.level else 0,
        "altitude_m": round(loc.alt, 1) if loc and loc.alt else 0,
        "lat": round(loc.lat, 6) if loc and loc.lat else 0,
        "lng": round(loc.lon, 6) if loc and loc.lon else 0,
        "ground_speed_ms": round(vehicle.groundspeed, 1),
        "gps_satellites": vehicle.gps_0.satellites_visible if vehicle.gps_0 else 0,
        "heading_deg": vehicle.heading,
        "last_heartbeat": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "simulation": is_sim
    })


# ═══════════════════════════════════════════════════════════════
# TELEMETRY REPORTER — Background thread
# ═══════════════════════════════════════════════════════════════

def telemetry_reporter_thread(vehicle):
    """Periodically push telemetry + drone position to Firebase."""
    while True:
        try:
            push_uav_telemetry(vehicle)
            loc = vehicle.location.global_relative_frame
            if loc and loc.lat:
                status = "IN_FLIGHT" if vehicle.armed else "IDLE"
                push_drone_track(loc.lat, loc.lon, loc.alt or 0, status,
                                 heading=vehicle.heading)
        except:
            pass
        time.sleep(2)


# ═══════════════════════════════════════════════════════════════
# MAVLINK FLIGHT OPERATIONS
# ═══════════════════════════════════════════════════════════════

def arm_and_takeoff(vehicle, target_alt):
    """Arms the vehicle and takes off to target altitude via MAVLink."""
    print(f"  {YELLOW}[PRE-ARM] Waiting for vehicle to be armable...{RESET}")
    while not vehicle.is_armable:
        time.sleep(1)

    print(f"  {YELLOW}[ARM] Setting GUIDED mode and arming...{RESET}")
    vehicle.mode = VehicleMode("GUIDED")
    vehicle.armed = True

    while not vehicle.armed:
        time.sleep(1)
    print(f"  {GREEN}[ARM] ✓ Motors armed{RESET}")

    print(f"  {YELLOW}[TAKEOFF] Ascending to {target_alt}m...{RESET}")
    vehicle.simple_takeoff(target_alt)

    while True:
        alt = vehicle.location.global_relative_frame.alt
        if alt is not None:
            print(f"    Altitude: {alt:.1f}m / {target_alt}m")
            if alt >= target_alt * 0.95:
                print(f"  {GREEN}[TAKEOFF] ✓ Target altitude reached{RESET}")
                break
        time.sleep(1)


def fly_to_target(vehicle, target_lat, target_lng, target_alt, mission_id=""):
    """Navigate to target GPS coordinates via MAVLink."""
    dist = haversine_km(
        vehicle.location.global_relative_frame.lat,
        vehicle.location.global_relative_frame.lon,
        target_lat, target_lng
    )
    print(f"  {YELLOW}[NAV] Flying to [{target_lat:.4f}, {target_lng:.4f}] — {dist:.2f}km{RESET}")

    target_point = LocationGlobalRelative(target_lat, target_lng, target_alt)
    vehicle.simple_goto(target_point, groundspeed=CRUISE_SPEED)

    while True:
        loc = vehicle.location.global_relative_frame
        if loc.lat and loc.lon:
            remaining = haversine_km(loc.lat, loc.lon, target_lat, target_lng)
            print(f"    Position: [{loc.lat:.4f}, {loc.lon:.4f}] — {remaining*1000:.0f}m remaining")

            # Push live position to Firebase for the web app map
            push_drone_track(loc.lat, loc.lon, loc.alt or 0, "IN_FLIGHT",
                             mission_id, vehicle.heading)

            if remaining < 0.005:  # Within ~5 meters
                print(f"  {GREEN}[NAV] ✓ Target reached{RESET}")
                break
        time.sleep(2)


def return_to_launch(vehicle, mission_id=""):
    """Set RTL mode and wait for landing."""
    print(f"  {YELLOW}[RTL] Returning to launch...{RESET}")
    vehicle.mode = VehicleMode("RTL")

    while True:
        alt = vehicle.location.global_relative_frame.alt
        loc = vehicle.location.global_relative_frame

        if loc.lat and loc.lon:
            push_drone_track(loc.lat, loc.lon, alt or 0, "RTL", mission_id)

        if alt is not None and alt < 1.0:
            print(f"  {GREEN}[RTL] ✓ Landed safely at base{RESET}")
            break
        time.sleep(2)

    # Wait for disarm
    timeout = 30
    while vehicle.armed and timeout > 0:
        time.sleep(1)
        timeout -= 1


# ═══════════════════════════════════════════════════════════════
# MISSION QUEUE PROCESSOR
# ═══════════════════════════════════════════════════════════════

class MissionProcessor:
    """Processes missions from Firebase queue via MAVLink SITL."""

    def __init__(self, vehicle):
        self.vehicle = vehicle
        self.processed_keys = set()
        self.running = True

    def fetch_queued_missions(self):
        """Fetch QUEUED missions from Firebase, sorted by priority."""
        data = firebase_get(MISSIONS_URL)
        if not data:
            return []
        missions = []
        for key, m in data.items():
            status = m.get("status", "QUEUED")
            if status in ["QUEUED", "TRANSMITTED"] and key not in self.processed_keys:
                m["_firebase_key"] = key
                missions.append(m)
        missions.sort(key=lambda m: (m.get("priority", 3), m.get("timestamp", "")))
        return missions

    def auto_assign_priority(self, mission, firebase_key):
        """Use AI to auto-detect priority if not already set."""
        payload = mission.get("request_details", "")
        if mission.get("priority") is None:
            pri, label, reason = ai_detect_priority(payload)
            mission["priority"] = pri
            mission["priority_label"] = label
            firebase_patch(f"{FIREBASE_URL}/missions/{firebase_key}.json", {
                "priority": pri,
                "priority_label": label,
                "ai_priority_reason": reason
            })
            print(f"  {MAGENTA}[AI] Auto-assigned: {label} — {reason}{RESET}")

    def execute_mission(self, mission):
        """Execute a single mission via MAVLink: arm→takeoff→navigate→deliver→RTL."""
        fb_key = mission["_firebase_key"]
        mission_id = mission.get("request_id", fb_key[:8])
        target_lat = float(mission.get("latitude", BASE_LAT))
        target_lng = float(mission.get("longitude", BASE_LNG))
        priority = mission.get("priority", 3)
        pri_labels = {1: "P1-CRITICAL", 2: "P2-URGENT", 3: "P3-STANDARD", 4: "P4-LOW"}
        pri_colors = {1: RED, 2: YELLOW, 3: GREEN, 4: CYAN}

        dist = haversine_km(BASE_LAT, BASE_LNG, target_lat, target_lng)

        print(f"\n{'▓' * 65}")
        print(f" {pri_colors.get(priority, GREEN)}⚡ EXECUTING: {mission_id} — {pri_labels.get(priority, 'P3')}{RESET}")
        print(f"{'▓' * 65}")
        print(f" Target:   [{target_lat:.6f}, {target_lng:.6f}]")
        print(f" Branch:   {mission.get('branch_name', 'N/A')}")
        print(f" Payload:  {mission.get('request_details', 'N/A')}")
        print(f" Distance: {dist:.2f} km")
        print(f"{'─' * 65}")

        # ── STEP 1: ARM + TAKEOFF ──
        print(f"\n{CYAN}[STEP 1/5] Arming + Takeoff{RESET}")
        update_mission_status(fb_key, "ARMING")
        send_ack(mission_id, "ARMING", "Pre-flight checks via MAVLink")

        arm_and_takeoff(self.vehicle, DEFAULT_ALTITUDE)

        update_mission_status(fb_key, "IN_FLIGHT")
        send_ack(mission_id, "IN_FLIGHT", f"Airborne at {DEFAULT_ALTITUDE}m, heading to target")
        push_uav_telemetry(self.vehicle)

        # ── STEP 2: NAVIGATE TO TARGET ──
        print(f"\n{CYAN}[STEP 2/5] En Route to target{RESET}")
        fly_to_target(self.vehicle, target_lat, target_lng, DEFAULT_ALTITUDE, mission_id)

        update_mission_status(fb_key, "AT_TARGET")
        send_ack(mission_id, "AT_TARGET", "Arrived at delivery zone")
        push_uav_telemetry(self.vehicle)

        # ── STEP 3: DELIVER PAYLOAD ──
        print(f"\n{CYAN}[STEP 3/5] Delivering Payload{RESET}")
        print(f"  {GREEN}Hovering... deploying payload...{RESET}")
        time.sleep(3)
        update_mission_status(fb_key, "DELIVERED")
        send_ack(mission_id, "DELIVERED", "Payload dropped successfully")
        print(f"  {GREEN}✓ DELIVERED SUCCESSFULLY!{RESET}")

        # ── STEP 4: RETURN TO BASE ──
        print(f"\n{CYAN}[STEP 4/5] Return to Base (RTL){RESET}")
        return_to_launch(self.vehicle, mission_id)
        push_uav_telemetry(self.vehicle)

        # ── STEP 5: MISSION COMPLETE ──
        print(f"\n{CYAN}[STEP 5/5] Mission Complete{RESET}")
        update_mission_status(fb_key, "COMPLETED")
        send_ack(mission_id, "COMPLETED", "✅ Delivered Successfully — Drone at base")

        print(f"\n{'═' * 65}")
        print(f" {GREEN}✅ MISSION {mission_id} — DELIVERED SUCCESSFULLY{RESET}")
        print(f"{'═' * 65}")

        # Remove from Firebase queue after a brief display
        time.sleep(3)
        remove_completed_mission(fb_key)
        print(f"  {DIM}[CLEANUP] Mission {mission_id} removed from queue — DONE{RESET}")

        self.processed_keys.add(fb_key)
        push_drone_track(BASE_LAT, BASE_LNG, 0, "IDLE")

    def run(self):
        """Main loop: poll Firebase, process queued missions by priority."""
        print(f"\n{GREEN}[+] Mission processor started — Waiting for missions from web app...{RESET}")
        print(f"  {DIM}Dispatch missions from: https://lifefly.web.app (or your Firebase hosted URL){RESET}\n")

        push_drone_track(BASE_LAT, BASE_LNG, 0, "IDLE")
        push_uav_telemetry(self.vehicle)

        # Pre-load existing completed missions to skip them
        data = firebase_get(MISSIONS_URL)
        if data:
            for key, m in data.items():
                status = m.get("status", "QUEUED")
                if status in ["COMPLETED", "DELIVERED", "FAILED"]:
                    self.processed_keys.add(key)
                self.auto_assign_priority(m, key)

        while self.running:
            try:
                missions = self.fetch_queued_missions()

                if missions:
                    # Auto-assign priority via AI
                    for m in missions:
                        self.auto_assign_priority(m, m["_firebase_key"])

                    # Re-sort by priority
                    missions.sort(key=lambda m: (m.get("priority", 3), m.get("timestamp", "")))
                    mission = missions[0]

                    # Show queue status
                    print(f"\n{CYAN}[QUEUE] {len(missions)} mission(s) pending:{RESET}")
                    for i, m in enumerate(missions[:5]):
                        pri = m.get("priority", 3)
                        plabel = {1:"P1-CRIT",2:"P2-URG",3:"P3-STD",4:"P4-LOW"}.get(pri,"P3")
                        print(f"  {i+1}. {plabel} — {m.get('request_id','?')} → {m.get('branch_name','?')}")

                    # Execute highest-priority mission via MAVLink
                    self.execute_mission(mission)
                    time.sleep(3)  # Cool-down between missions
                else:
                    time.sleep(3)  # Poll interval

            except KeyboardInterrupt:
                print(f"\n{RED}[×] Mission processor stopped.{RESET}")
                self.running = False
                break
            except Exception as e:
                print(f"  {RED}[ERROR] {e}{RESET}")
                import traceback
                traceback.print_exc()
                time.sleep(5)


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═══════════════════════════════════════════════════════════════

def main():
    os.system('cls' if os.name == 'nt' else 'clear')

    print(f"""
{CYAN}╔══════════════════════════════════════════════════════════════════════╗
║                                                                      ║
║   ██╗     ██╗███████╗███████╗███████╗██╗  ██╗   ██╗                 ║
║   ██║     ██║██╔════╝██╔════╝██╔════╝██║  ╚██╗ ██╔╝                ║
║   ██║     ██║█████╗  █████╗  █████╗  ██║   ╚████╔╝                 ║
║   ██║     ██║██╔══╝  ██╔══╝  ██╔══╝  ██║    ╚██╔╝                  ║
║   ███████╗██║██║     ███████╗██║     ███████╗ ██║                   ║
║   ╚══════╝╚═╝╚═╝     ╚══════╝╚═╝     ╚══════╝ ╚═╝                   ║
║                                                                      ║
║   {WHITE}MAVLINK SITL MISSION CONTROLLER{CYAN}                                    ║
║   {DIM}AI Priority Queue • MAVLink SITL • Firebase Cloud Sync{CYAN}             ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
    """)

    # ── Step 1: Start SITL ──
    print(f"\n{CYAN}[1/3] Starting copter simulator (SITL){RESET}")
    sitl_args = ['--model', 'quad', '--home=17.3850,78.4867,0,0', '--out=127.0.0.1:14550']
    sitl = dronekit_sitl.SITL()
    sitl.download('copter', '3.3', verbose=True)
    try:
        sitl.launch(sitl_args, await_ready=True)
        sitl.block_until_ready(verbose=True)
    except Exception as e:
        print(f"\n{RED}[!] SITL Launch Failed: {e}{RESET}")
        print(f"    {YELLOW}Action: Make sure all old 'arducopter.exe' instances are killed.{RESET}")
        sys.exit(1)
        
    connection_string = sitl.connection_string()
    print(f"  {GREEN}✓ SITL started at: {WHITE}{connection_string}{RESET}")
    print(f"  {DIM}Mission Planner: Connect to UDP port 14550 to view the live simulation{RESET}")

    # ── Step 2: Connect to vehicle ──
    print(f"\n{CYAN}[2/3] Connecting to simulated vehicle via MAVLink...{RESET}")
    try:
        vehicle = connect(connection_string, wait_ready=True, timeout=120, heartbeat_timeout=30)
    except Exception as e:
        print(f"\n{RED}[!] SITL Timeout: Windows Firewall or ghost processes may be blocking TCP 5760.{RESET}")
        print(f"    {YELLOW}Action: Run 'taskkill /f /im arducopter.exe' and try again.{RESET}")
        sys.exit(1)
    
    print(f"  {GREEN}✓ Vehicle connected{RESET}")
    print(f"  {DIM}Firmware:  {vehicle.version}{RESET}")
    print(f"  {DIM}Mode:      {vehicle.mode.name}{RESET}")
    print(f"  {DIM}GPS:       {vehicle.gps_0}{RESET}")
    print(f"  {DIM}Battery:   {vehicle.battery}{RESET}")

    # ── Step 3: Start telemetry reporter ──
    print(f"\n{CYAN}[3/3] Starting background telemetry reporter...{RESET}")
    telem_thread = threading.Thread(target=telemetry_reporter_thread, args=(vehicle,), daemon=True)
    telem_thread.start()
    print(f"  {GREEN}✓ Telemetry reporting to Firebase every 2s{RESET}")

    print(f"""
{'═' * 65}
 {GREEN}✓ ALL SYSTEMS ONLINE{RESET}

 {WHITE}MAVLink SITL:{RESET}    {connection_string}
 {WHITE}Firebase:{RESET}        {FIREBASE_URL}
 {WHITE}AI Priority:{RESET}     Active
 {WHITE}Drone Mode:{RESET}      {vehicle.mode.name}
 {WHITE}Web App:{RESET}         Dispatch missions from the hosted Firebase web app
                  (index.html deployed to Firebase Hosting)

 {YELLOW}HOW IT WORKS:{RESET}
  1. Open the web app (Firebase hosted index.html) and dispatch a mission
  2. AI auto-detects priority from payload description
  3. This script picks up the mission from Firebase queue
  4. Drone executes the mission via MAVLink SITL
  5. View the flight in Mission Planner (connect to {connection_string})
  6. Web app shows real-time status: QUEUED → IN_FLIGHT → DELIVERED → DONE
  7. After delivery, drone RTLs to base and picks up next task

 {DIM}Press Ctrl+C to stop.{RESET}
{'═' * 65}
    """)

    # ── Run mission processor ──
    processor = MissionProcessor(vehicle)
    try:
        processor.run()
    except KeyboardInterrupt:
        pass
    finally:
        print(f"\n{YELLOW}[SHUTDOWN] Closing vehicle connection...{RESET}")
        vehicle.close()
        print(f"{YELLOW}[SHUTDOWN] Stopping SITL server...{RESET}")
        sitl.stop()
        push_drone_track(BASE_LAT, BASE_LNG, 0, "OFFLINE")
        print(f"{RED}[×] LifeFly SITL Controller offline.{RESET}")


if __name__ == "__main__":
    main()
