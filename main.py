#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════╗
║  LIFEFLY GCS — FIREBASE CLOUD LISTENER                              ║
║  Priority-Based UAV Medical Delivery Network                         ║
║  Monitors Firebase for incoming dispatches with AI priority          ║
╚══════════════════════════════════════════════════════════════════════╝

This script listens to Firebase RTDB for new mission dispatches and
displays them in the terminal with AI-detected priority levels.
Run this alongside run_simulation.py for the full system.
"""

import time
import requests
import logging

from priority_detector import detect_priority, get_priority_description

# Suppress noisy logs
logging.getLogger("urllib3").setLevel(logging.WARNING)

API_KEY = "AIzaSyCgHXLUhpMhw0X2XMfoh6WYGey0Y1bFmWI"
FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com/missions.json"

try:
    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    res = requests.post(auth_url, json={"returnSecureToken": True}, timeout=3)
    AUTH_TOKEN = "?auth=" + res.json().get("idToken")
    FIREBASE_URL += AUTH_TOKEN
except:
    pass

RESET  = "\033[0m"
CYAN   = "\033[1;96m"
GREEN  = "\033[1;92m"
RED    = "\033[1;91m"
YELLOW = "\033[1;93m"
WHITE  = "\033[1;97m"
DIM    = "\033[2m"

print("\n" + "═" * 70)
print(f"{CYAN}[+] LIFEFLY GCS TACTICAL SERVER ONLINE{RESET}")
print(f"{GREEN}[+] Connected to Global Firebase IoT Cloud (Data Link Active){RESET}")
print(f"{GREEN}[+] AI Priority Detection Engine Loaded{RESET}")
print("[+] Listening for incoming drone dispatches from the web array...\n")
print("═" * 70 + "\n")

processed_ids = set()

def listen_to_firebase():
    global processed_ids

    # Pre-fetch existing missions
    try:
        response = requests.get(FIREBASE_URL)
        if response.status_code == 200 and response.json():
            data = response.json()
            for key in data:
                processed_ids.add(key)
    except:
        pass

    while True:
        try:
            response = requests.get(FIREBASE_URL)
            if response.status_code == 200:
                data = response.json()
                if data:
                    for key, mission in data.items():
                        if key not in processed_ids:
                            processed_ids.add(key)

                            req_id = mission.get('request_id', key)
                            payload = mission.get('request_details', '')

                            # AI Priority Detection
                            pri_result = detect_priority(payload)
                            pri_label = mission.get('priority_label', pri_result['label'])
                            ai_reason = mission.get('ai_priority_reason', pri_result['reason'])

                            pri_colors = {1: RED, 2: YELLOW, 3: GREEN, 4: CYAN}
                            pri_num = mission.get('priority', pri_result['priority'])
                            color = pri_colors.get(pri_num, GREEN)

                            print("═" * 65)
                            print(f" 🚀 NEW UAV MISSION: {CYAN}{req_id}{RESET}")
                            print(f" {color}⚡ {pri_label}{RESET}")
                            print("═" * 65)
                            print(f" 📍 Branch:      {YELLOW}{mission.get('branch_name')}{RESET}")
                            print(f" 🌐 Coordinates: [{GREEN}{mission.get('latitude', 0.0):.6f}, {mission.get('longitude', 0.0):.6f}{RESET}]")
                            print(f" 📦 Payload:     {WHITE}{payload}{RESET}")
                            print(f" 🤖 AI Reason:   {DIM}{ai_reason}{RESET}")
                            print(f" 🕒 Timestamp:   {DIM}{mission.get('timestamp')}{RESET}")
                            print(f" 🚦 Status:      {YELLOW}{mission.get('status')}{RESET}")
                            print("═" * 65 + "\n")

        except Exception as e:
            print(f"{RED}[!] Firebase connection drift: {e}{RESET}")

        time.sleep(2)

if __name__ == "__main__":
    try:
        listen_to_firebase()
    except KeyboardInterrupt:
        print(f"\n{RED}[+] System Offline. Comm link severed.{RESET}")
