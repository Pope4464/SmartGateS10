# S10 SmartGate MQTT Integration - Complete System Documentation

## Overview
Complete cloud-based dashboard for monitoring and controlling Jetson Nano gate systems with real-time camera feeds, detection alerts, and remote gate control via MQTT communication.

## System Architecture
```
Internet User → AWS EC2 Dashboard → MQTT → Jetson Nano → Gate Control
     ↑                                                      ↓
     └─── Camera Stream ← Reverse SSH ← Camera Feed ←──────┘
```

## Configuration Files

### AWS EC2 & Jetson Config (`config.json`)
```json
{
  "ec2_ip": "54.252.172.171",
  "ec2_user": "admin", 
  "ssh_key_path": "./reverse_tunnel/aws_key",
  "mqtt_port": 1883,
  "ssh_port": 22,
  "tunnel_port": 2222
}
```

### Mosquitto MQTT Broker (`aws-ec2/mosquitto.conf`)
```conf
port 1883
listener 1883
allow_anonymous true
persistence true
persistence_location /var/lib/mosquitto/
log_dest file /var/log/mosquitto/mosquitto.log
```

## Docker Configuration

### Dockerfile (`web-app/Dockerfile`)
```dockerfile
# ----- S10 Group Added
# Expose all required ports for S10 integration
EXPOSE 8000 5432 5000 1883 8080 2222
```

### Docker Compose (`web-app/docker-compose.yml`)
```yaml
# ----- S10 Group Added
services:
  sgwebimage:
    ports:
      - "8000:8000"  # Web app
      - "5000:5000"  # MQTT client FastAPI
      - "1883:1883"  # MQTT broker
      - "8080:8080"  # Camera stream
      - "2222:2222"  # SSH tunnel
```

## Code Additions

### Jetson Nano Side (`src/main/`)

#### `live_detection.py`
```python
# ----- S10 Group Added
# --------------S10 MQTT DETECTION--------------
def send_detection_alert(objects_detected):
    """Send detection info to EC2 detection endpoint"""
    try:
        data = {"objects": objects_detected, "timestamp": time.time()}
        requests.post("http://54.252.172.171:5000/detection", json=data, timeout=2)
    except:
        pass  # Fail silently to not interrupt main loop
# --------------S10 MQTT DETECTION END--------------
```

#### `http_server.py`
```python
# ----- S10 Group Added
# --------------S10 CAMERA STREAM--------------
def start_reverse_stream():
    """Start camera stream accessible via reverse tunnel"""
    try:
        import subprocess
        subprocess.Popen(["ssh", "-i", "../reverse_tunnel/aws_key", "-R", "8080:localhost:8000", "admin@54.252.172.171", "-N"])
        print("[+] Reverse stream started on port 8080")
    except Exception as e:
        print(f"[-] Failed to start reverse stream: {e}")
# --------------S10 CAMERA STREAM END--------------
```

#### `door_control.py`
```python
# ----- S10 Group Added
# --------------S10 MQTT CONTROL--------------
def send_mqtt_command(command):
    """Send MQTT command to EC2"""
    try:
        data = {"command": command, "timestamp": time.time()}
        requests.post("http://54.252.172.171:5000/send_command", json=data, timeout=2)
    except:
        pass  # Fail silently

def mqtt_open_door(self):
    """Open door via MQTT command"""
    self.open_door()
    send_mqtt_command("door_opened")  # S10 CODE MQTT

def mqtt_close_door(self):
    """Close door via MQTT command"""
    self.close_door()
    send_mqtt_command("door_closed")  # S10 CODE MQTT
# --------------S10 MQTT CONTROL END--------------
```

### AWS EC2 Side (`aws-ec2/mqtt_client.py`)
```python
# ----- S10 Group Added
# --------------S10 MQTT ENDPOINTS--------------
def add_alert(self, message, level="info"):
    """Add alert to alerts list"""
    alert = {
        "id": len(self.alerts) + 1,
        "message": message,
        "level": level,
        "timestamp": datetime.now().strftime("%d/%m/%Y, %H:%M:%S")
    }
    self.alerts.insert(0, alert)
    if len(self.alerts) > 100:
        self.alerts = self.alerts[:100]

@self.app.post('/detection')
async def receive_detection(request: dict):
    """Receive detection data from Jetson"""
    objects = request.get("objects", [])
    if objects:
        self.add_alert(f"Animal detected: {', '.join(objects)}", "warning")
    return JSONResponse(content={"status": "received"})

@self.app.post('/send_command')
async def send_command(request: dict):
    """Send command to Jetson via MQTT"""
    command = request.get("command")
    if command:
        self.client.publish("jetson/commands", json.dumps({"action": command}))
        self.add_alert(f"Command sent: {command}", "info")
    return JSONResponse(content={"status": "sent"})
# --------------S10 MQTT ENDPOINTS END--------------
```

### Web Application (`web-app/frontend/`)

#### `streams.html` (NEW FILE)
```javascript
// ----- S10 Group Added
// --------------S10 CAMERA STREAM--------------
function toggleStream(gateNo) {
    const button = document.querySelector(`[data-gate-no="${gateNo}"] .btn`);
    
    if (button.textContent === 'START STREAM') {
        button.textContent = 'STOP STREAM';
        container.innerHTML = `<img src="http://54.252.172.171:8080/stream" alt="Live Stream">`;
        
        // S10 CODE CAMERA STREAM
        fetch('/send_command', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({command: 'start_stream', gate: gateNo})
        });
    } else {
        // Stop stream logic...
    }
}
// --------------S10 CAMERA STREAM END--------------
```

#### `gates.html`
```javascript
// ----- S10 Group Added
// --------------S10 GATE CONTROL--------------
function openGate(gateNo) {
    fetch('/send_command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command: 'OPEN_DOOR', gate: gateNo})
    }).then(() => {
        document.querySelector(`[data-gate-no="${gateNo}"] .status`).textContent = 'Status: Open';
    });
}

function closeGate(gateNo) {
    fetch('/send_command', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({command: 'CLOSE_DOOR', gate: gateNo})
    }).then(() => {
        document.querySelector(`[data-gate-no="${gateNo}"] .status`).textContent = 'Status: Closed';
    });
}
// --------------S10 GATE CONTROL END--------------
```

#### `stats.html`
```javascript
// ----- S10 Group Added
// --------------S10 LATEST CAPTURE--------------
function updateLatestCapture() {
    fetch('/latest-capture')
        .then(response => response.json())
        .then(data => {
            if (data.capture) {
                document.getElementById('latest-capture-img').src = data.capture.image_url;
                document.getElementById('capture-timestamp').textContent = data.capture.timestamp;
            }
        });
}
// --------------S10 LATEST CAPTURE END--------------
```

#### `alerts.html`
```javascript
// ----- S10 Group Added
// --------------S10 MQTT ALERTS--------------
function loadAlerts() {
    fetch('/alerts')
        .then(response => response.json())
        .then(data => {
            updateAlertsTable(data.alerts);
        });
}
// --------------S10 MQTT ALERTS END--------------
```

## System Flow

### 1. User Access Flow
```
Dummy User → Web Dashboard → AWS EC2 → MQTT → Jetson Nano
```

### 2. MQTT Communication
- **Jetson → AWS**: Detection data, status updates, health checks
- **AWS → Jetson**: Gate commands, stream control

### 3. Camera Streaming
```
Jetson Camera → HTTP Server → Reverse SSH → AWS EC2 → Web Dashboard
```

## Endpoints

### AWS EC2 MQTT Client
- `POST /detection` - Receive detection data from Jetson
- `POST /send_command` - Send commands to Jetson via MQTT
- `GET /latest-capture` - Get latest capture image
- `GET /alerts` - Get alerts list
- `GET /gate-status` - Get gate status
- `GET /gates` - Get all gates data

### Web Dashboard
- `GET /gates` - Dynamic gates page
- `GET /streams` - Camera streams page
- `GET /alerts` - Alerts monitoring page
- `GET /stats` - Statistics page

## Alert Types
- **info** - General information (gate connected, commands sent)
- **warning** - Animal detected
- **critical** - Gate disconnected, errors

## Port Configuration

### AWS EC2 (Docker Container)
- **Port 8000** - Web application dashboard
- **Port 5000** - MQTT client FastAPI
- **Port 1883** - MQTT broker
- **Port 8080** - Camera stream (reverse tunnel)
- **Port 2222** - SSH reverse tunnel
- **Port 5432** - PostgreSQL database

### Jetson Nano
- **Port 8000** - Local HTTP server
- **Port 22** - SSH access
- **Port 1883** - MQTT client connection

## Performance
- **Gate Status**: Updates every 5 seconds
- **Alerts**: Refresh every 5 seconds
- **Latest Capture**: Updates every 10 seconds
- **Detection**: Real-time (when detected)
- **Maximum 100 alerts** stored in memory

## Error Handling
All MQTT functions include silent error handling to prevent interruption of main system operations. Errors are logged to the alerts system for monitoring.

## Key Features
1. **Real-time Detection Alerts** - Animal detection sent to cloud dashboard
2. **Camera Streaming** - Live camera feeds via reverse SSH tunnel
3. **Remote Gate Control** - Open/close gates from web dashboard
4. **Status Monitoring** - Real-time gate status updates
5. **Alert System** - Comprehensive logging of all events
6. **Latest Capture Display** - Shows most recent detection images
