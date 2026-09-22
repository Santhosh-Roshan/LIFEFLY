import tkinter as tk
import tkintermapview
import requests
import time
import threading

API_KEY = "AIzaSyCgHXLUhpMhw0X2XMfoh6WYGey0Y1bFmWI"
FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"

# Fetch Firebase auth token
try:
    auth_url = f"https://identitytoolkit.googleapis.com/v1/accounts:signUp?key={API_KEY}"
    res = requests.post(auth_url, json={"returnSecureToken": True}, timeout=3)
    token = res.json().get("idToken")
except:
    token = None

class MAVProxyMap(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("Map")
        self.geometry("800x600")
        
        # MAVProxy Map Widget
        self.map_widget = tkintermapview.TkinterMapView(self, width=800, height=600, corner_radius=0)
        self.map_widget.pack(fill="both", expand=True)
        # Google Satellite
        self.map_widget.set_tile_server("https://mt0.google.com/vt/lyrs=s&hl=en&x={x}&y={y}&z={z}&s=Ga", max_zoom=22)
        
        self.base_marker = None
        self.drone_marker = None
        self.path_layer = None
        self.path_coords = []
        
        # Start background polling
        self.running = True
        threading.Thread(target=self.poll_firebase, daemon=True).start()

    def poll_firebase(self):
        url = f"{FIREBASE_URL}/drone_track.json"
        if token:
            url += f"?auth={token}"
            
        while self.running:
            try:
                r = requests.get(url, timeout=2)
                data = r.json()
                if isinstance(data, dict) and "lat" in data:
                    lat = float(data["lat"])
                    lng = float(data["lng"])
                    status = data.get("status", "RUNNING")
                    self.update_map(lat, lng, status)
            except Exception as e:
                pass
            time.sleep(1)

    def update_map(self, lat, lng, status):
        # Update safely on main UI thread
        if self.base_marker is None:
            self.map_widget.set_position(lat, lng)
            self.map_widget.set_zoom(15)
            self.base_marker = self.map_widget.set_marker(17.397210, 78.489888, text="Base")
            
        if self.drone_marker is None:
            self.drone_marker = self.map_widget.set_marker(lat, lng, text="UAV")
        else:
            self.drone_marker.set_position(lat, lng)
            
        if status == "CLEAR_PATH" or status == "IDLE":
            # Clear old path exactly when we start a new mission or finish
            self.path_coords.clear()
            if self.path_layer:
                self.path_layer.delete()
                self.path_layer = None
            
        if status not in ["IDLE", "CLEAR_PATH"]:
            self.path_coords.append((lat, lng))
            if self.path_layer:
                self.path_layer.delete()
            if len(self.path_coords) > 1:
                self.path_layer = self.map_widget.set_path(self.path_coords, color="cyan", width=4)

if __name__ == "__main__":
    app = MAVProxyMap()
    app.mainloop()
