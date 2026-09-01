#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LIFEFLY GCS — LAPTOP COMMAND BRIDGE                                ║
║  Priority-Based Intra-Hospital UAV Medical Delivery Network          ║
║  SSH Control Interface for Raspberry Pi @ 192.168.137.62             ║
╚══════════════════════════════════════════════════════════════════════╝

This script runs on your LAPTOP and:
  1. Pushes mission requests with priority to Firebase RTDB
  2. Sends SSH commands to Raspberry Pi for UAV arm/takeoff/navigate
  3. Listens for mission status updates from the Pi
  4. Manages priority queue (P1-CRITICAL > P2-URGENT > P3-STANDARD)
"""

import json
import time
import random
import datetime
import requests
import subprocess
import threading
import sys
import os

# ═══════════════════════════════════════════════════════════════
# CONFIGURATION
# ═══════════════════════════════════════════════════════════════

FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"
MISSIONS_URL = f"{FIREBASE_URL}/missions.json"
STATUS_URL   = f"{FIREBASE_URL}/uav_status.json"
FINANCIAL_URL = f"{FIREBASE_URL}/financial_log.json"

# Raspberry Pi SSH Configuration
RPI_HOST = "192.168.137.62"
RPI_USER = "uav"
RPI_SSH  = f"{RPI_USER}@{RPI_HOST}"  # ssh uav@192.168.137.62

# Priority Levels
PRIORITY_LEVELS = {
    1: {"label": "P1-CRITICAL",  "color": "\033[1;91m", "desc": "Life-threatening — Immediate dispatch"},
    2: {"label": "P2-URGENT",    "color": "\033[1;93m", "desc": "Time-sensitive — Within 10 minutes"},
    3: {"label": "P3-STANDARD",  "color": "\033[1;92m", "desc": "Routine — Scheduled delivery"},
    4: {"label": "P4-LOW",       "color": "\033[1;94m", "desc": "Non-urgent — Batch delivery"},
}

# Medical Payload Categories (for random priority simulation)
MEDICAL_PAYLOADS = [
    {"item": "Blood Pack O-Negative",       "default_priority": 1, "cost_per_km": 45.00},
    {"item": "Defibrillator Unit",           "default_priority": 1, "cost_per_km": 62.00},
    {"item": "Anti-Venom Serum",             "default_priority": 1, "cost_per_km": 55.00},
    {"item": "Insulin Emergency Kit",        "default_priority": 2, "cost_per_km": 30.00},
    {"item": "Surgical Instruments Kit",     "default_priority": 2, "cost_per_km": 38.00},
    {"item": "Oxygen Cylinder (Portable)",   "default_priority": 2, "cost_per_km": 42.00},
    {"item": "Lab Samples (Pathology)",      "default_priority": 3, "cost_per_km": 18.00},
    {"item": "Medication Refill Pack",       "default_priority": 3, "cost_per_km": 15.00},
    {"item": "PPE Supply Bundle",            "default_priority": 4, "cost_per_km": 12.00},
    {"item": "Medical Records (Physical)",   "default_priority": 4, "cost_per_km": 10.00},
]

# Hospital Branches (Hyderabad network)
HOSPITAL_BRANCHES = [
    {"name": "Apollo Main Campus",          "lat": 17.4122, "lng": 78.4343},
    {"name": "NIMS Emergency Wing",         "lat": 17.3950, "lng": 78.3910},
    {"name": "Yashoda Somajiguda",          "lat": 17.4280, "lng": 78.4520},
    {"name": "Care Hospitals Banjara",      "lat": 17.4260, "lng": 78.4480},
    {"name": "Gandhi Hospital Trauma",      "lat": 17.3880, "lng": 78.4700},
    {"name": "Osmania General ER",          "lat": 17.3720, "lng": 78.4780},
    {"name": "KIMS Secunderabad",           "lat": 17.4450, "lng": 78.5020},
    {"name": "Star Hospitals Banjara",      "lat": 17.4310, "lng": 78.4410},
    {"name": "Continental ICU Wing",        "lat": 17.4380, "lng": 78.4560},
    {"name": "Sunshine Cardiology Unit",    "lat": 17.4490, "lng": 78.3780},
]

RESET = "\033[0m"
CYAN  = "\033[1;96m"
GREEN = "\033[1;92m"
RED   = "\033[1;91m"
YELLOW = "\033[1;93m"
WHITE = "\033[1;97m"
DIM   = "\033[2m"
BOLD  = "\033[1m"

mission_counter = 1000
processed_ids = set()

# ═══════════════════════════════════════════════════════════════
# SSH COMMAND EXECUTION
# ═══════════════════════════════════════════════════════════════

def ssh_execute(command, timeout=30):
    """Execute a command on Raspberry Pi via SSH."""
    ssh_cmd = [
        "ssh",
        "-o", "StrictHostKeyChecking=no",
        "-o", "ConnectTimeout=10",
        "-o", "BatchMode=yes",
        RPI_SSH,
        command
    ]
    try:
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=timeout
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip()
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "stdout": "", "stderr": "SSH timeout"}
    except Exception as e:
        return {"success": False, "stdout": "", "stderr": str(e)}


def check_rpi_connection():
    """Check if Raspberry Pi is reachable via SSH."""
    print(f"\n{CYAN}[SSH] Pinging Raspberry Pi @ {RPI_HOST}...{RESET}")
    result = ssh_execute("echo 'LIFEFLY_HEARTBEAT'")
    if result["success"] and "LIFEFLY_HEARTBEAT" in result["stdout"]:
        print(f"{GREEN}[SSH] ✓ Raspberry Pi ONLINE — Link Established{RESET}")
        return True
    else:
        print(f"{YELLOW}[SSH] ⚠ Raspberry Pi OFFLINE — Running in CLOUD-ONLY mode{RESET}")
        print(f"{DIM}      Error: {result['stderr']}{RESET}")
        return False


def send_mission_to_rpi(mission_data):
    """Send mission instructions to Raspberry Pi via SSH."""
    mission_json = json.dumps(mission_data).replace('"', '\\"')
    
    # Write mission file on Pi
    cmd_write = f'echo "{mission_json}" > /home/uav/lifefly/active_mission.json'
    result = ssh_execute(cmd_write)
    
    if result["success"]:
        print(f"{GREEN}  [SSH→Pi] Mission file written successfully{RESET}")
    else:
        print(f"{RED}  [SSH→Pi] Failed to write: {result['stderr']}{RESET}")
    
    # Trigger the mission receiver script on Pi
    cmd_trigger = "python3 /home/uav/lifefly/rpi_receiver.py --execute-mission &"
    ssh_execute(cmd_trigger, timeout=5)
    
    return result["success"]


def send_arm_command():
    """Send ARM command to UAV via Raspberry Pi."""
    print(f"{YELLOW}  [SSH→Pi] Sending ARM command...{RESET}")
    result = ssh_execute("python3 /home/uav/lifefly/rpi_receiver.py --arm")
    return result["success"]


def send_takeoff_command(altitude=25):
    """Send TAKEOFF command to UAV via Raspberry Pi."""
    print(f"{YELLOW}  [SSH→Pi] Sending TAKEOFF to {altitude}m...{RESET}")
    result = ssh_execute(f"python3 /home/uav/lifefly/rpi_receiver.py --takeoff {altitude}")
    return result["success"]


def send_navigate_command(lat, lng, alt=25):
    """Send NAVIGATE command to UAV via Raspberry Pi."""
    print(f"{YELLOW}  [SSH→Pi] Sending NAV to [{lat}, {lng}]...{RESET}")
    result = ssh_execute(f"python3 /home/uav/lifefly/rpi_receiver.py --navigate {lat} {lng} {alt}")
    return result["success"]


# ═══════════════════════════════════════════════════════════════
# FIREBASE OPERATIONS
# ═══════════════════════════════════════════════════════════════

def push_mission_to_firebase(mission_data):
    """Push a new mission to Firebase RTDB."""
    try:
        response = requests.post(MISSIONS_URL, json=mission_data, timeout=10)
        if response.status_code == 200:
            firebase_key = response.json().get("name", "unknown")
            return True, firebase_key
        return False, None
    except Exception as e:
        return False, str(e)


def update_mission_status(firebase_key, new_status):
    """Update mission status in Firebase."""
    url = f"{FIREBASE_URL}/missions/{firebase_key}.json"
    try:
        requests.patch(url, json={"status": new_status}, timeout=10)
    except:
        pass


def push_financial_record(record):
    """Push a financial record to Firebase."""
    try:
        requests.post(FINANCIAL_URL, json=record, timeout=10)
    except:
        pass


def update_uav_status(status_data):
    """Update UAV telemetry status in Firebase (Pi reports back)."""
    try:
        requests.put(STATUS_URL, json=status_data, timeout=10)
    except:
        pass


def fetch_all_missions():
    """Fetch all missions from Firebase."""
    try:
        response = requests.get(MISSIONS_URL, timeout=10)
        if response.status_code == 200 and response.json():
            return response.json()
    except:
        pass
    return {}


# ═══════════════════════════════════════════════════════════════
# PRIORITY QUEUE ENGINE
# ═══════════════════════════════════════════════════════════════

def calculate_distance_km(lat1, lng1, lat2, lng2):
    """Haversine distance calculation."""
    import math
    R = 6371  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2 +
         math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) *
         math.sin(dlng / 2) ** 2)
    c = 2 * math.asin(math.sqrt(a))
    return R * c


def generate_random_priority():
    """Generate weighted random priority (more critical = less frequent)."""
    weights = [15, 25, 40, 20]  # P1=15%, P2=25%, P3=40%, P4=20%
    return random.choices([1, 2, 3, 4], weights=weights, k=1)[0]


def sort_missions_by_priority(missions_dict):
    """Sort missions by priority (P1 first), then by timestamp."""
    missions_list = []
    for key, val in missions_dict.items():
        val["_key"] = key
        missions_list.append(val)
    
    missions_list.sort(key=lambda m: (
        m.get("priority", 3),
        m.get("timestamp", "")
    ))
    return missions_list


# ═══════════════════════════════════════════════════════════════
# FINANCIAL MARKER
# ═══════════════════════════════════════════════════════════════

def calculate_delivery_cost(distance_km, priority, payload_type):
    """Calculate financial cost of a delivery mission."""
    # Base cost per km from payload type
    base_cost = 20.0  # default
    for p in MEDICAL_PAYLOADS:
        if p["item"].lower() in payload_type.lower():
            base_cost = p["cost_per_km"]
            break
    
    # Priority multiplier
    priority_multipliers = {1: 2.5, 2: 1.8, 3: 1.0, 4: 0.7}
    multiplier = priority_multipliers.get(priority, 1.0)
    
    # Calculate costs
    flight_cost = distance_km * base_cost * multiplier
    fuel_cost = distance_km * 8.50  # ₹8.50 per km battery cost
    insurance = flight_cost * 0.05   # 5% insurance
    platform_fee = 150.00            # Fixed platform fee
    
    total = flight_cost + fuel_cost + insurance + platform_fee
    
    return {
        "flight_cost": round(flight_cost, 2),
        "fuel_cost": round(fuel_cost, 2),
        "insurance": round(insurance, 2),
        "platform_fee": platform_fee,
        "total_cost": round(total, 2),
        "currency": "INR",
        "cost_per_km": round(base_cost * multiplier, 2),
        "distance_km": round(distance_km, 2),
        "priority_multiplier": multiplier
    }


# ═══════════════════════════════════════════════════════════════
# MISSION DISPATCH ENGINE
# ═══════════════════════════════════════════════════════════════

def dispatch_mission(branch_name, lat, lng, payload_details, priority=None):
    """Full mission dispatch: Firebase → SSH → Pi → UAV."""
    global mission_counter
    mission_counter += 1
    
    if priority is None:
        priority = generate_random_priority()
    
    pri_info = PRIORITY_LEVELS[priority]
    request_id = f"UAV-{mission_counter:04d}"
    
    # Base station coordinates (main hospital hub)
    base_lat, base_lng = 17.3850, 78.4867
    distance = calculate_distance_km(base_lat, base_lng, lat, lng)
    
    # Financial calculation
    cost_data = calculate_delivery_cost(distance, priority, payload_details)
    
    # Build mission payload
    mission_data = {
        "request_id": request_id,
        "branch_name": branch_name,
        "latitude": lat,
        "longitude": lng,
        "request_details": payload_details,
        "priority": priority,
        "priority_label": pri_info["label"],
        "status": "QUEUED",
        "distance_km": round(distance, 2),
        "estimated_flight_time_min": round(distance / 0.8, 1),  # ~48 km/h speed
        "financial": cost_data,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "dispatched_from": "LAPTOP_GCS",
        "rpi_target": RPI_SSH
    }
    
    # ── Display Mission Card ──
    print(f"\n{'═' * 70}")
    print(f" {pri_info['color']}⚡ {pri_info['label']}{RESET} — NEW MISSION DISPATCH")
    print(f"{'═' * 70}")
    print(f" {CYAN}Mission ID:{RESET}    {WHITE}{request_id}{RESET}")
    print(f" {CYAN}Branch:{RESET}        {YELLOW}{branch_name}{RESET}")
    print(f" {CYAN}Coordinates:{RESET}   {GREEN}[{lat:.6f}, {lng:.6f}]{RESET}")
    print(f" {CYAN}Payload:{RESET}       {WHITE}{payload_details}{RESET}")
    print(f" {CYAN}Distance:{RESET}      {WHITE}{distance:.2f} km{RESET}")
    print(f" {CYAN}Est. Flight:{RESET}   {WHITE}{mission_data['estimated_flight_time_min']:.1f} min{RESET}")
    print(f" {CYAN}Total Cost:{RESET}    {GREEN}₹{cost_data['total_cost']:,.2f}{RESET}")
    print(f"{'─' * 70}")
    
    # Step 1: Push to Firebase
    print(f" {DIM}[1/4]{RESET} Pushing to Firebase Cloud...")
    success, fb_key = push_mission_to_firebase(mission_data)
    if success:
        print(f" {GREEN}  ✓ Firebase: Mission registered (key: {fb_key[:12]}...){RESET}")
    else:
        print(f" {RED}  ✗ Firebase push failed: {fb_key}{RESET}")
        return False
    
    # Step 2: Push Financial Record
    print(f" {DIM}[2/4]{RESET} Logging financial markers...")
    financial_record = {
        "mission_id": request_id,
        "timestamp": mission_data["timestamp"],
        "priority": pri_info["label"],
        **cost_data,
        "branch": branch_name
    }
    push_financial_record(financial_record)
    print(f" {GREEN}  ✓ Financial record logged{RESET}")
    
    # Step 3: Send to Raspberry Pi via SSH
    print(f" {DIM}[3/4]{RESET} Transmitting to Pi @ {RPI_HOST}...")
    rpi_success = send_mission_to_rpi(mission_data)
    if rpi_success:
        update_mission_status(fb_key, "TRANSMITTED")
        print(f" {GREEN}  ✓ Mission transmitted to Raspberry Pi{RESET}")
    else:
        print(f" {YELLOW}  ⚠ Pi offline — Mission queued in cloud{RESET}")
    
    # Step 4: Send flight commands
    print(f" {DIM}[4/4]{RESET} Issuing flight commands...")
    if rpi_success:
        send_arm_command()
        send_takeoff_command()
        send_navigate_command(lat, lng)
        update_mission_status(fb_key, "IN_FLIGHT")
        print(f" {GREEN}  ✓ UAV armed, launched, navigating{RESET}")
    else:
        print(f" {YELLOW}  ⚠ Flight commands deferred — awaiting Pi link{RESET}")
    
    print(f"{'═' * 70}\n")
    return True


# ═══════════════════════════════════════════════════════════════
# FIREBASE LISTENER (Background Thread)
# ═══════════════════════════════════════════════════════════════

def firebase_listener_thread():
    """Background thread that listens for new missions from the website."""
    global processed_ids
    
    # Pre-load existing missions
    try:
        existing = fetch_all_missions()
        if existing:
            for key in existing:
                processed_ids.add(key)
    except:
        pass
    
    while True:
        try:
            missions = fetch_all_missions()
            if missions:
                for key, mission in missions.items():
                    if key not in processed_ids:
                        processed_ids.add(key)
                        
                        # Auto-assign priority if not set
                        if "priority" not in mission:
                            mission["priority"] = generate_random_priority()
                            pri_info = PRIORITY_LEVELS[mission["priority"]]
                            
                            # Update Firebase with assigned priority
                            url = f"{FIREBASE_URL}/missions/{key}.json"
                            requests.patch(url, json={
                                "priority": mission["priority"],
                                "priority_label": pri_info["label"]
                            }, timeout=10)
                        
                        pri = mission.get("priority", 3)
                        pri_info = PRIORITY_LEVELS.get(pri, PRIORITY_LEVELS[3])
                        
                        print(f"\n{'▓' * 70}")
                        print(f" {pri_info['color']}📡 INCOMING WEB DISPATCH — {pri_info['label']}{RESET}")
                        print(f"{'▓' * 70}")
                        print(f" {CYAN}ID:{RESET}       {mission.get('request_id', key)}")
                        print(f" {CYAN}Branch:{RESET}   {mission.get('branch_name', 'N/A')}")
                        print(f" {CYAN}GPS:{RESET}      [{mission.get('latitude', 0):.6f}, {mission.get('longitude', 0):.6f}]")
                        print(f" {CYAN}Payload:{RESET}  {mission.get('request_details', 'N/A')}")
                        print(f"{'▓' * 70}")
                        
                        # Forward to Raspberry Pi
                        rpi_success = send_mission_to_rpi(mission)
                        if rpi_success:
                            update_mission_status(key, "TRANSMITTED")
                            
                        # Log financial data
                        base_lat, base_lng = 17.3850, 78.4867
                        dist = calculate_distance_km(
                            base_lat, base_lng,
                            float(mission.get("latitude", base_lat)),
                            float(mission.get("longitude", base_lng))
                        )
                        cost = calculate_delivery_cost(dist, pri, mission.get("request_details", ""))
                        push_financial_record({
                            "mission_id": mission.get("request_id", key),
                            "timestamp": mission.get("timestamp", datetime.datetime.now(datetime.timezone.utc).isoformat()),
                            "priority": pri_info["label"],
                            **cost,
                            "branch": mission.get("branch_name", "N/A")
                        })
                        
        except Exception as e:
            pass  # Silently retry
        
        time.sleep(3)


# ═══════════════════════════════════════════════════════════════
# INTERACTIVE CLI
# ═══════════════════════════════════════════════════════════════

def print_banner():
    """Print the startup banner."""
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
║   {WHITE}UAV GROUND CONTROL STATION — PRIORITY MEDICAL DELIVERY{CYAN}            ║
║   {DIM}Intra-Hospital Drone Network Command Bridge{CYAN}                       ║
║                                                                      ║
╚══════════════════════════════════════════════════════════════════════╝{RESET}
    """)
    print(f" {DIM}Firebase:{RESET}  {GREEN}https://lifefly-default-rtdb.firebaseio.com{RESET}")
    print(f" {DIM}Target Pi:{RESET} {CYAN}ssh {RPI_SSH}{RESET}")
    print(f" {DIM}Time:{RESET}      {WHITE}{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{RESET}")
    print()


def show_help():
    """Show available commands."""
    print(f"""
{CYAN}{'═' * 60}
 COMMAND REFERENCE
{'═' * 60}{RESET}
  {GREEN}1{RESET} / {GREEN}dispatch{RESET}     — Manually dispatch a new mission
  {GREEN}2{RESET} / {GREEN}random{RESET}       — Auto-dispatch random priority mission
  {GREEN}3{RESET} / {GREEN}batch{RESET}        — Dispatch 5 random missions (demo mode)
  {GREEN}4{RESET} / {GREEN}queue{RESET}        — View priority-sorted mission queue
  {GREEN}5{RESET} / {GREEN}financial{RESET}    — View financial summary
  {GREEN}6{RESET} / {GREEN}ssh-check{RESET}    — Test SSH link to Raspberry Pi
  {GREEN}7{RESET} / {GREEN}ssh-cmd{RESET}      — Send custom SSH command to Pi
  {GREEN}8{RESET} / {GREEN}status{RESET}       — View UAV telemetry status
  {GREEN}9{RESET} / {GREEN}help{RESET}         — Show this menu
  {GREEN}0{RESET} / {GREEN}exit{RESET}         — Shutdown GCS
{CYAN}{'═' * 60}{RESET}
    """)


def manual_dispatch():
    """Manually enter a mission dispatch."""
    print(f"\n{CYAN}─── MANUAL MISSION DISPATCH ───{RESET}\n")
    
    branch = input(f"  {WHITE}Hospital Branch: {RESET}").strip()
    if not branch:
        print(f"  {RED}Cancelled.{RESET}")
        return
    
    try:
        lat = float(input(f"  {WHITE}Latitude:  {RESET}").strip())
        lng = float(input(f"  {WHITE}Longitude: {RESET}").strip())
    except ValueError:
        print(f"  {RED}Invalid coordinates.{RESET}")
        return
    
    payload = input(f"  {WHITE}Payload Details: {RESET}").strip()
    
    print(f"\n  {CYAN}Priority: {RESET}[1] P1-CRITICAL  [2] P2-URGENT  [3] P3-STANDARD  [4] P4-LOW  [R] Random")
    pri_input = input(f"  {WHITE}Select: {RESET}").strip().upper()
    
    if pri_input == "R" or pri_input == "":
        priority = generate_random_priority()
        print(f"  {YELLOW}→ Randomly assigned: {PRIORITY_LEVELS[priority]['label']}{RESET}")
    elif pri_input in ["1", "2", "3", "4"]:
        priority = int(pri_input)
    else:
        priority = generate_random_priority()
    
    dispatch_mission(branch, lat, lng, payload, priority)


def random_dispatch():
    """Dispatch a random mission for demonstration."""
    branch = random.choice(HOSPITAL_BRANCHES)
    payload = random.choice(MEDICAL_PAYLOADS)
    priority = generate_random_priority()
    
    # Add small random offset to coordinates
    lat = branch["lat"] + random.uniform(-0.01, 0.01)
    lng = branch["lng"] + random.uniform(-0.01, 0.01)
    
    dispatch_mission(branch["name"], lat, lng, payload["item"], priority)


def batch_dispatch():
    """Dispatch multiple random missions."""
    count = 5
    print(f"\n{CYAN}[BATCH] Dispatching {count} random priority missions...{RESET}\n")
    
    for i in range(count):
        print(f"{DIM}─── Mission {i+1}/{count} ───{RESET}")
        random_dispatch()
        time.sleep(1)
    
    print(f"\n{GREEN}[BATCH] All {count} missions dispatched!{RESET}")


def view_queue():
    """View all missions sorted by priority."""
    print(f"\n{CYAN}─── PRIORITY MISSION QUEUE ───{RESET}\n")
    
    missions = fetch_all_missions()
    if not missions:
        print(f"  {DIM}No active missions.{RESET}")
        return
    
    sorted_missions = sort_missions_by_priority(missions)
    
    print(f"  {'#':<4} {'PRIORITY':<16} {'REQUEST ID':<12} {'BRANCH':<28} {'STATUS':<14} {'COST (₹)':<12}")
    print(f"  {'─' * 90}")
    
    for i, m in enumerate(sorted_missions, 1):
        pri = m.get("priority", 3)
        pri_info = PRIORITY_LEVELS.get(pri, PRIORITY_LEVELS[3])
        cost = m.get("financial", {}).get("total_cost", 0)
        
        print(f"  {pri_info['color']}{i:<4} {pri_info['label']:<16}{RESET} "
              f"{m.get('request_id', 'N/A'):<12} "
              f"{m.get('branch_name', 'N/A')[:26]:<28} "
              f"{m.get('status', 'QUEUED'):<14} "
              f"{GREEN}₹{cost:>10,.2f}{RESET}")
    
    print(f"\n  {DIM}Total: {len(sorted_missions)} missions{RESET}")


def view_financial_summary():
    """View financial summary of all operations."""
    print(f"\n{CYAN}─── FINANCIAL OPERATIONS SUMMARY ───{RESET}\n")
    
    try:
        response = requests.get(FINANCIAL_URL, timeout=10)
        if response.status_code == 200 and response.json():
            records = response.json()
            
            total_cost = 0
            total_distance = 0
            priority_costs = {1: 0, 2: 0, 3: 0, 4: 0}
            mission_count = 0
            
            for key, rec in records.items():
                cost = rec.get("total_cost", 0)
                dist = rec.get("distance_km", 0)
                pri = int(rec.get("priority", "P3-STANDARD")[1]) if isinstance(rec.get("priority"), str) else rec.get("priority", 3)
                
                total_cost += cost
                total_distance += dist
                if pri in priority_costs:
                    priority_costs[pri] += cost
                mission_count += 1
            
            print(f"  {WHITE}Total Missions:{RESET}        {GREEN}{mission_count}{RESET}")
            print(f"  {WHITE}Total Distance:{RESET}        {GREEN}{total_distance:,.1f} km{RESET}")
            print(f"  {WHITE}Total Revenue:{RESET}         {GREEN}₹{total_cost:,.2f}{RESET}")
            print(f"  {WHITE}Avg Cost/Mission:{RESET}      {GREEN}₹{total_cost/max(mission_count,1):,.2f}{RESET}")
            print()
            print(f"  {CYAN}Cost by Priority:{RESET}")
            for pri, cost in priority_costs.items():
                pri_info = PRIORITY_LEVELS[pri]
                bar = '█' * int(cost / max(total_cost, 1) * 30)
                print(f"    {pri_info['color']}{pri_info['label']:<16}{RESET} ₹{cost:>10,.2f}  {GREEN}{bar}{RESET}")
        else:
            print(f"  {DIM}No financial records yet.{RESET}")
    except Exception as e:
        print(f"  {RED}Error fetching financial data: {e}{RESET}")


def custom_ssh_command():
    """Send a custom SSH command to Raspberry Pi."""
    print(f"\n{CYAN}─── SSH COMMAND TO Pi @ {RPI_HOST} ───{RESET}")
    cmd = input(f"  {WHITE}Command: {RESET}").strip()
    if not cmd:
        return
    
    print(f"  {DIM}Executing...{RESET}")
    result = ssh_execute(cmd)
    
    if result["success"]:
        print(f"  {GREEN}✓ Success:{RESET}")
        if result["stdout"]:
            for line in result["stdout"].split("\n"):
                print(f"    {line}")
    else:
        print(f"  {RED}✗ Error: {result['stderr']}{RESET}")


def view_uav_status():
    """View current UAV telemetry status."""
    print(f"\n{CYAN}─── UAV TELEMETRY STATUS ───{RESET}\n")
    
    try:
        response = requests.get(STATUS_URL, timeout=10)
        if response.status_code == 200 and response.json():
            status = response.json()
            print(f"  {WHITE}Mode:{RESET}         {status.get('mode', 'N/A')}")
            print(f"  {WHITE}Armed:{RESET}        {status.get('armed', 'N/A')}")
            print(f"  {WHITE}Battery:{RESET}      {status.get('battery_pct', 'N/A')}%")
            print(f"  {WHITE}Altitude:{RESET}     {status.get('altitude_m', 'N/A')} m")
            print(f"  {WHITE}Speed:{RESET}        {status.get('ground_speed_ms', 'N/A')} m/s")
            print(f"  {WHITE}GPS Sats:{RESET}     {status.get('gps_satellites', 'N/A')}")
            print(f"  {WHITE}Position:{RESET}     [{status.get('lat', 'N/A')}, {status.get('lng', 'N/A')}]")
            print(f"  {WHITE}Last Update:{RESET}  {status.get('last_heartbeat', 'N/A')}")
        else:
            print(f"  {DIM}No UAV status data available. Ensure rpi_receiver.py is running on Pi.{RESET}")
    except Exception as e:
        print(f"  {RED}Error: {e}{RESET}")


# ═══════════════════════════════════════════════════════════════
# MAIN ENTRY
# ═══════════════════════════════════════════════════════════════

def main():
    print_banner()
    
    # Check Pi connection
    rpi_online = check_rpi_connection()
    
    # Start Firebase listener in background
    listener = threading.Thread(target=firebase_listener_thread, daemon=True)
    listener.start()
    print(f"\n{GREEN}[+] Firebase listener active — monitoring for web dispatches{RESET}")
    
    show_help()
    
    while True:
        try:
            cmd = input(f"\n{CYAN}LifeFly GCS ▸ {RESET}").strip().lower()
            
            if cmd in ["1", "dispatch"]:
                manual_dispatch()
            elif cmd in ["2", "random"]:
                random_dispatch()
            elif cmd in ["3", "batch"]:
                batch_dispatch()
            elif cmd in ["4", "queue"]:
                view_queue()
            elif cmd in ["5", "financial"]:
                view_financial_summary()
            elif cmd in ["6", "ssh-check"]:
                check_rpi_connection()
            elif cmd in ["7", "ssh-cmd"]:
                custom_ssh_command()
            elif cmd in ["8", "status"]:
                view_uav_status()
            elif cmd in ["9", "help"]:
                show_help()
            elif cmd in ["0", "exit", "quit"]:
                print(f"\n{RED}[×] LifeFly GCS shutting down...{RESET}")
                break
            else:
                print(f"  {DIM}Unknown command. Type 'help' for options.{RESET}")
                
        except KeyboardInterrupt:
            print(f"\n{RED}[×] Interrupted. GCS offline.{RESET}")
            break
        except EOFError:
            break

if __name__ == "__main__":
    main()
