import time
import requests
import logging

# Suppress noisy logs
logging.getLogger("urllib3").setLevel(logging.WARNING)

# The global Firebase URL for LifeFly
FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com/missions.json"

print("\n" + "═" * 70)
print("\033[1;36m[+] LIFEFLY GCS TACTICAL SERVER ONLINE\033[0m")
print("\033[1;32m[+] Connected to Global Firebase IoT Cloud (Data Link Active)\033[0m")
print("[+] Listening for incoming drone dispatches from the web array...\n")
print("═" * 70 + "\n")

processed_ids = set()

def listen_to_firebase():
    global processed_ids
    
    # Pre-fetch existing missions so we don't spam the terminal with old history
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
                            
                            # Beautiful Terminal UI
                            print("═" * 65)
                            print(f" 🚀 NEW UAV MISSION AUTHORIZED: \033[96m{req_id}\033[0m")
                            print("═" * 65)
                            print(f" 📍 Branch:      \033[93m{mission.get('branch_name')}\033[0m")
                            print(f" 🌐 Coordinates: [\033[92m{mission.get('latitude', 0.0):.6f}, {mission.get('longitude', 0.0):.6f}\033[0m]")
                            print(f" 📦 Payload:     \033[97m{mission.get('request_details')}\033[0m")
                            print(f" 🕒 Timestamp:   \033[90m{mission.get('timestamp')}\033[0m")
                            print(f" 🚦 Status:      \033[1;33m{mission.get('status')}\033[0m")
                            print("═" * 65 + "\n")
                            
        except Exception as e:
            print(f"\033[91m[!] Firebase connection drift: {e}\033[0m")
            
        # Poll every 2 seconds efficiently
        time.sleep(2)

if __name__ == "__main__":
    try:
        listen_to_firebase()
    except KeyboardInterrupt:
        print("\n\033[91m[+] System Offline. Comm link severed.\033[0m")
