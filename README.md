# LifeFly - Priority UAV Medical Delivery System

## 🚀 Quick Start Guide

### What's New
- ✅ **Automatic Priority Detection** - AI analyzes payload text and assigns priority automatically
- ✅ **Enhanced Professional UI** - Medical-grade interface with real-time updates
- ✅ **Raspberry Pi Deployment** - One-click deployment script for Pi at `192.168.137.62`

### Priority System

The system automatically detects priority from your payload description:

- **P1-CRITICAL** ⚡ - Blood packets, organs (lung, kidney, heart), defibrillators, anti-venom, trauma emergencies
- **P2-URGENT** 🔥 - Insulin, surgical instruments, oxygen cylinders, urgent medications
- **P3-STANDARD** 📦 - Lab samples, medication refills, routine supplies
- **P4-LOW** 📋 - PPE, medical records, non-urgent batch deliveries

**Examples:**
- "Blood Pack O-Negative Emergency" → P1-CRITICAL
- "Kidney transplant organ transport" → P1-CRITICAL
- "Lung tissue emergency surgery" → P1-CRITICAL
- "Insulin emergency kit" → P2-URGENT
- "Lab samples pathology" → P3-STANDARD
- "PPE supply bundle" → P4-LOW

### File Structure

```
lifefly/
├── index_enhanced.html          # Enhanced web interface with auto-priority
├── rpi_receiver.py              # Raspberry Pi UAV receiver daemon
├── priority_detector.py         # Automatic priority detection engine
├── deploy_to_pi.sh              # Linux/Mac deployment script
├── deploy_to_pi.bat             # Windows deployment script
├── rpi_controller.py            # Laptop command bridge
└── main.py                      # Firebase listener
```

### Setup Instructions

#### 1. Test Priority Detection

```bash
python priority_detector.py
```

This will run test cases showing how different medical payloads are automatically prioritized.

#### 2. Deploy to Raspberry Pi

**Windows:**
```cmd
deploy_to_pi.bat
```

**Linux/Mac:**
```bash
chmod +x deploy_to_pi.sh
./deploy_to_pi.sh
```

The script will:
- Check SSH connectivity to `uav@192.168.137.62`
- Create `/home/uav/lifefly` directory
- Copy Python files to Pi
- Install dependencies (requests, dronekit)
- Start the receiver daemon in background

#### 3. Open Web Interface

Open `index_enhanced.html` in your browser.

Features:
- Real-time Firebase sync
- Automatic priority detection as you type
- GPS lock acquisition
- Live mission queue sorted by priority
- Financial tracking
- UAV telemetry display

#### 4. Monitor Raspberry Pi

```bash
# Check if daemon is running
ssh uav@192.168.137.62 "pgrep -f rpi_receiver.py"

# View live logs
ssh uav@192.168.137.62 "tail -f /home/uav/lifefly/lifefly.log"

# Check UAV status
ssh uav@192.168.137.62 "cd /home/uav/lifefly && python3 rpi_receiver.py --status"

# Stop daemon
ssh uav@192.168.137.62 "pkill -f rpi_receiver.py"
```

### How It Works

1. **Web Interface** → User enters payload details
2. **Auto-Detection** → JavaScript detects priority from keywords in real-time
3. **Firebase** → Mission pushed to Firebase RTDB with auto-assigned priority
4. **Raspberry Pi** → Daemon listens to Firebase, pulls missions into priority queue
5. **Priority Queue** → Missions sorted (P1 > P2 > P3 > P4)
6. **UAV Execution** → Pi sends MAVLink commands to flight controller
7. **Telemetry** → Pi reports status back to Firebase → Web displays updates

### Priority Detection Keywords

**P1-CRITICAL:**
- Organs: lung, kidney, heart, liver, transplant
- Blood: blood, plasma, transfusion, o-negative
- Emergency: defibrillator, ventilator, crash cart
- Critical meds: anti-venom, epinephrine, naloxone
- Trauma: hemorrhage, cardiac arrest, stroke

**P2-URGENT:**
- insulin, diabetic, antibiotic, chemotherapy
- surgical instruments, oxygen, iv fluid
- burn, fracture, seizure, asthma

**P3-STANDARD:**
- lab samples, pathology, routine medication
- bandages, syringes, vaccination

**P4-LOW:**
- PPE, medical records, paperwork
- non-urgent supplies, inventory

### Configuration

**Firebase** (in index_enhanced.html):
```javascript
const firebaseConfig = {
    databaseURL: "https://lifefly-default-rtdb.firebaseio.com",
    // ... other config
};
```

**Raspberry Pi** (in rpi_receiver.py):
```python
RPI_HOST = "192.168.137.62"
RPI_USER = "uav"
FIREBASE_URL = "https://lifefly-default-rtdb.firebaseio.com"
FC_CONNECTION_STRING = "/dev/ttyACM0"  # or tcp:127.0.0.1:5760 for SITL
```

### Troubleshooting

**Can't connect to Pi:**
- Check if Pi is on same network: `ping 192.168.137.62`
- Verify SSH is enabled: `sudo systemctl status ssh`
- Test SSH manually: `ssh uav@192.168.137.62`

**Priority not detecting:**
- Make sure payload text includes medical keywords
- Check browser console for JavaScript errors
- Test with priority_detector.py

**UAV not responding:**
- Check if rpi_receiver.py is running: `pgrep -f rpi_receiver`
- View logs: `tail -f /home/uav/lifefly/lifefly.log`
- Verify DroneKit connection string matches your hardware

**Firebase not syncing:**
- Check browser console for Firebase errors
- Verify Firebase config in index_enhanced.html
- Check internet connection

### Manual Priority Override

While the system auto-detects, you can force priority by including these in payload text:
- "P1" or "critical" or "emergency" → P1-CRITICAL
- "P2" or "urgent" or "asap" → P2-URGENT
- "P4" or "low priority" or "routine" → P4-LOW

### Support

- Check logs on Pi: `/home/uav/lifefly/lifefly.log`
- Firebase console: https://console.firebase.google.com/project/lifefly
- Mission queue visible in web interface

---

**LifeFly** - Autonomous Priority-Based Medical UAV Delivery Network
