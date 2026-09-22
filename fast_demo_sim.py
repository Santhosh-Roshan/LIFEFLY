import time
import math
import requests
import os
from pymavlink import mavutil

print("[+] Bypassing SITL and initializing direct PyMAVLink link to Mission Planner...")

API_KEY = "AIzaSyCgHXLUhpMhw0X2XMfoh6WYGey0Y1bFmWI"
FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"

BASE_LAT = 17.397210
BASE_LNG = 78.489888
SPEED = 0.0003  # Roughly 20m/s in lat/lng degrees

print("[+] Authenticating with Firebase Anonymous Auth...")
auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
res = requests.post(auth_url, json={"returnSecureToken": True})
token = res.json().get("idToken")

def get_url(path):
    return f"{FIREBASE_URL}{path}.json?auth={token}"

# Connect directly to Mission Planner via UDP
mp_conn = mavutil.mavlink_connection('udpout:127.0.0.1:14550', source_system=1)

def push_track(lat, lng, status, alt=25):
    requests.put(get_url("/drone_track"), json={"lat": lat, "lng": lng, "alt": alt, "status": status})
    # Beam real-time MAVLink packets directly to Mission Planner
    try:
        mp_conn.mav.heartbeat_send(mavutil.mavlink.MAV_TYPE_QUADROTOR, mavutil.mavlink.MAV_AUTOPILOT_ARDUPILOTMEGA, 128, 0, mavutil.mavlink.MAV_STATE_ACTIVE)
        mp_conn.mav.global_position_int_send(
            int(time.time()*1000) % 4294967295,
            int(lat * 1e7), int(lng * 1e7),
            int(alt * 1000), int(alt * 1000),
            0, 0, 0, 0
        )
    except:
        pass

def delete_mission(key):
    requests.delete(get_url(f"/missions/{key}"))

def update_mission(key, status):
    requests.patch(get_url(f"/missions/{key}"), json={"status": status})

print("[+] DEMO Simulator Online! Bypassing SITL hardware blocks for review...")

while True:
    try:
        r = requests.get(get_url("/missions"))
        data = r.json()
        
        if isinstance(data, dict):
            # Check for error dicts bypassing auth somehow
            if "error" in data:
                print("Auth Error:", data["error"])
                time.sleep(2)
                continue
                
            # Filter queued missions and SORT by priority! (1 = Critical, 4 = Low)
            active_missions = []
            for key, m in data.items():
                if isinstance(m, dict) and m.get("status") in ["QUEUED", "TRANSMITTED"]:
                    m["_firebase_key"] = key
                    active_missions.append(m)
            
            active_missions.sort(key=lambda x: x.get("priority", 3))
            
            for m in active_missions:
                key = m["_firebase_key"]
                t_lat = float(m["latitude"])
                t_lng = float(m["longitude"])
                
                print(f"\n🚀 Launching Mission (Priority {m.get('priority', 3)}): {m.get('request_details')}", flush=True)
                update_mission(key, "IN_FLIGHT")
                
                # Ensure the GUI clears previous flight paths
                push_track(BASE_LAT, BASE_LNG, "CLEAR_PATH", alt=0)
                time.sleep(2)
                
                # Simulated Takeoff (Altitude 0 -> 25)
                for h in range(0, 26, 5):
                    push_track(BASE_LAT, BASE_LNG, "TAKEOFF", alt=h)
                    time.sleep(0.2)

                # Fly to target
                steps = 30
                d_lat = (t_lat - BASE_LAT) / steps
                d_lng = (t_lng - BASE_LNG) / steps
                
                print("  -> Flying to Target...")
                for i in range(steps):
                    push_track(BASE_LAT + (d_lat * i), BASE_LNG + (d_lng * i), "IN_FLIGHT", alt=25)
                    time.sleep(0.15)
                
                print("  -> Hovering & Payload Delivery...", flush=True)
                update_mission(key, "DELIVERED")
                push_track(t_lat, t_lng, "HOVER_DROP", alt=25)
                time.sleep(1)

                print("  -> Return To Base (RTL)...", flush=True)
                for i in range(steps, -1, -1):
                    push_track(BASE_LAT + (d_lat * i), BASE_LNG + (d_lng * i), "RTL", alt=25)
                    time.sleep(0.1)
                    
                print("  -> Landing (Altitude 25 -> 0)...", flush=True)
                for h in range(25, -1, -5):
                    push_track(BASE_LAT, BASE_LNG, "LANDING", alt=h)
                    time.sleep(0.1)

                print(f"  -> Mission Complete. Deleting...", flush=True)
                delete_mission(key)
                push_track(BASE_LAT, BASE_LNG, "IDLE", alt=0)
                time.sleep(2)
    except Exception as e:
        print("Error:", e)
    
    push_track(BASE_LAT, BASE_LNG, "IDLE", alt=0)
    time.sleep(3)
