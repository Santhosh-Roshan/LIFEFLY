import matplotlib.pyplot as plt
import matplotlib.animation as animation
import requests
import json

FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"
TRACK_URL = f"{FIREBASE_URL}/drone_track.json"
MISSIONS_URL = f"{FIREBASE_URL}/missions.json"

# Base station
BASE_LAT = 17.397210
BASE_LNG = 78.489888

# Setup Plot
plt.style.use('dark_background')
fig, ax = plt.subplots(figsize=(8, 6))
fig.canvas.manager.set_window_title("Tactical MAVLink Map Simulation")

path_lons = []
path_lats = []

line, = ax.plot([], [], 'o-', color='cyan', markersize=4, label="UAV Flight Path")
drone_marker, = ax.plot([], [], 'X', color='lime', markersize=10, label="Live UAV Position")
base_marker, = ax.plot([BASE_LNG], [BASE_LAT], '^', color='magenta', markersize=12, label="GCS Base Station")
target_scatter = ax.scatter([], [], color='red', marker='s', s=80, label="Queued Targets", zorder=3)

# Base layout setup
ax.set_title("MAVLink Real-Time Simulation Tracking", color="cyan", fontsize=14, fontweight='bold')
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.grid(color='#333333', linestyle='--', linewidth=0.5)
ax.legend(loc='upper right')

def get_data():
    try:
        t_res = requests.get(TRACK_URL, timeout=3)
        m_res = requests.get(MISSIONS_URL, timeout=3)
        track = t_res.json() if t_res.status_code == 200 else None
        missions = m_res.json() if m_res.status_code == 200 else None
        return track, missions
    except:
        return None, None

def update(frame):
    track, missions = get_data()

    if track and 'lat' in track and 'lng' in track:
        # UAV
        current_lat, current_lng = track['lat'], track['lng']
        
        # Keep path history, start over if we returned to base (idle)
        if track.get('status') == 'IDLE' or len(path_lats) == 0:
            path_lats.clear()
            path_lons.clear()
            path_lats.append(current_lat)
            path_lons.append(current_lng)
        else:
            path_lats.append(current_lat)
            path_lons.append(current_lng)

        line.set_data(path_lons, path_lats)
        drone_marker.set_data([current_lng], [current_lat])
        
        # Display status overlay
        ax.set_title(f"MAVLink Real-Time Tracking | Status: {track.get('status', 'RUNNING')} | Alt: {track.get('alt', 0)}m", color="cyan")

    if missions:
        # Show all active targets
        t_lats, t_lons = [], []
        for v in missions.values():
            if v.get('status') not in ['COMPLETED', 'DELIVERED']:
                if 'latitude' in v and 'longitude' in v:
                    t_lats.append(float(v['latitude']))
                    t_lons.append(float(v['longitude']))
        
        target_scatter.set_offsets(list(zip(t_lons, t_lats)))
        
        # Dynamic bounds
        all_lats = [BASE_LAT] + t_lats + path_lats[-1:]
        all_lons = [BASE_LNG] + t_lons + path_lons[-1:]
        
        if all_lats:
            ax.set_xlim(min(all_lons) - 0.005, max(all_lons) + 0.005)
            ax.set_ylim(min(all_lats) - 0.005, max(all_lats) + 0.005)

    return line, drone_marker, target_scatter

ani = animation.FuncAnimation(fig, update, interval=1000, cache_frame_data=False)
plt.show()
