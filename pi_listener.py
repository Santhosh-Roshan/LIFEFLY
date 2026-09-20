#!/usr/bin/env python3
"""
LIFEFLY — Raspberry Pi Mission Listener
Runs on the Pi. Connects to Firebase, fetches missions,
sorts by priority, and displays them in the terminal.

Install:  pip3 install requests
Run:      python3 pi_listener.py
"""

import time
import requests
import datetime
import os

FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com/missions.json"

PRIORITY_LABELS = {
    1: "\033[1;91m[P1-CRITICAL]\033[0m",
    2: "\033[1;93m[P2-URGENT]\033[0m",
    3: "\033[1;92m[P3-STANDARD]\033[0m",
    4: "\033[1;94m[P4-LOW]\033[0m",
}

seen_keys = set()

def clear():
    os.system('clear' if os.name != 'nt' else 'cls')

def fetch_missions():
    """Fetch all missions from Firebase."""
    try:
        r = requests.get(FIREBASE_URL, timeout=10)
        if r.status_code == 200 and r.json():
            return r.json()
    except Exception as e:
        print(f"\033[91m[!] Firebase error: {e}\033[0m")
    return {}

def update_status(key, status):
    """Update a mission's status in Firebase."""
    url = f"https://lifefly-default-rtdb.firebaseio.com/missions/{key}.json"
    try:
        requests.patch(url, json={"status": status}, timeout=5)
    except:
        pass

def sort_by_priority(missions):
    """Sort missions: P1 first, then P2, P3, P4. Within same priority, oldest first."""
    items = []
    for key, m in missions.items():
        m["_key"] = key
        items.append(m)
    items.sort(key=lambda m: (m.get("priority", 3), m.get("timestamp", "")))
    return items

def display_queue(sorted_missions):
    """Display the priority-sorted mission queue."""
    print("\033[1;96m" + "=" * 65)
    print("  LIFEFLY RASPBERRY Pi — MISSION QUEUE (Priority Sorted)")
    print("=" * 65 + "\033[0m")
    print(f"  Time: {datetime.datetime.now().strftime('%H:%M:%S')}  |  Missions: {len(sorted_missions)}")
    print("-" * 65)

    if not sorted_missions:
        print("\n  \033[2mNo missions in queue. Waiting for dispatches...\033[0m\n")
        return

    print(f"  {'#':<4} {'PRIORITY':<18} {'MISSION ID':<12} {'BRANCH':<22} {'STATUS'}")
    print("  " + "-" * 61)

    for i, m in enumerate(sorted_missions, 1):
        pri = m.get("priority", 3)
        label = PRIORITY_LABELS.get(pri, PRIORITY_LABELS[3])
        mid = m.get("request_id", "N/A")
        branch = m.get("branch_name", "Unknown")[:20]
        status = m.get("status", "QUEUED")

        print(f"  {i:<4} {label:<30} {mid:<12} {branch:<22} {status}")

    print("-" * 65)

def display_new_mission(mission, key):
    """Display a new incoming mission alert."""
    pri = mission.get("priority", 3)
    label = PRIORITY_LABELS.get(pri, PRIORITY_LABELS[3])

    print()
    print("\033[1;96m" + "=" * 60)
    print(f"  >>> NEW MISSION RECEIVED <<<")
    print("=" * 60 + "\033[0m")
    print(f"  Priority:    {label}")
    print(f"  Mission ID:  \033[1;97m{mission.get('request_id', key)}\033[0m")
    print(f"  Branch:      \033[1;93m{mission.get('branch_name', 'N/A')}\033[0m")
    print(f"  Coordinates: \033[1;92m[{mission.get('latitude', 0):.6f}, {mission.get('longitude', 0):.6f}]\033[0m")
    print(f"  Payload:     \033[1;97m{mission.get('request_details', 'N/A')}\033[0m")
    print(f"  Time:        \033[2m{mission.get('timestamp', 'N/A')}\033[0m")

    if mission.get("financial"):
        cost = mission["financial"].get("total_cost", 0)
        dist = mission["financial"].get("distance_km", 0)
        print(f"  Cost:        \033[1;92m₹{cost:,.2f}\033[0m")
        print(f"  Distance:    {dist:.2f} km")

    print("=" * 60)

    # Mark as RECEIVED on Firebase
    update_status(key, "RECEIVED_BY_PI")

def main():
    clear()
    print("\033[1;96m")
    print("╔═══════════════════════════════════════════════════╗")
    print("║  LIFEFLY — RASPBERRY Pi MISSION LISTENER         ║")
    print("║  Priority-Based UAV Medical Delivery              ║")
    print("╚═══════════════════════════════════════════════════╝")
    print("\033[0m")
    print(f"  Firebase: \033[1;92mCONNECTED\033[0m")
    print(f"  Polling:  Every 3 seconds")
    print(f"  Started:  {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    global seen_keys

    # Load existing missions so we don't re-alert old ones
    print("\033[2m  Loading existing missions...\033[0m")
    existing = fetch_missions()
    if existing:
        for key in existing:
            seen_keys.add(key)
        print(f"\033[2m  Found {len(existing)} existing missions.\033[0m")
    else:
        print("\033[2m  No existing missions.\033[0m")

    print("\n\033[1;92m[+] Listening for new missions from Firebase...\033[0m\n")

    while True:
        try:
            missions = fetch_missions()

            if missions:
                # Check for NEW missions
                for key, mission in missions.items():
                    if key not in seen_keys:
                        seen_keys.add(key)
                        display_new_mission(mission, key)

                # Display current priority queue
                sorted_list = sort_by_priority(missions)
                print()
                display_queue(sorted_list)
            else:
                display_queue([])

        except Exception as e:
            print(f"\033[91m[!] Error: {e}\033[0m")

        time.sleep(3)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\033[91m[x] LifeFly Pi Listener stopped.\033[0m")
