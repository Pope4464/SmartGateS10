#!/usr/bin/env python3
"""
MQTT Client for Web Application
Handles MQTT communication with Jetson Nano
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class WebAppMQTTClient:
    def __init__(self, broker_host="localhost", broker_port=1883, client_id="web_app"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.client = mqtt.Client(client_id)
        self.connected = False
        self.alerts = []
        
        # --------------S10 GATE DISCOVERY--------------
        self.discovered_gates = {}  # {gate_id: {"status": "online/offline", "last_seen": timestamp, "gate_status": "open/closed"}}
        self.gate_timeout = 30  # seconds - gate considered offline if no heartbeat for 30s
        # --------------S10 GATE DISCOVERY END--------------
        
        # Setup MQTT callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        
        # MQTT client only - no FastAPI endpoints
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            # --------------S10 GATE DISCOVERY--------------
            # Subscribe to per-gate topics only
            client.subscribe("jetson/+/status")  # Per-gate status topics
            client.subscribe("jetson/+/detection")  # Per-gate detection topics
            client.subscribe("jetson/+/heartbeat")  # Per-gate heartbeat topics
            # --------------S10 GATE DISCOVERY END--------------
            
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            
    def on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker. Return code: {rc}")
        
    def on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"Received message on topic {msg.topic}: {payload}")
            
            # --------------S10 GATE DISCOVERY--------------
            # Handle per-gate message types only
            if msg.topic.startswith("jetson/") and msg.topic.endswith("/status"):
                gate_id = msg.topic.split("/")[1]
                self.handle_per_gate_status(gate_id, payload)
            elif msg.topic.startswith("jetson/") and msg.topic.endswith("/detection"):
                gate_id = msg.topic.split("/")[1]
                self.handle_per_gate_detection(gate_id, payload)
            elif msg.topic.startswith("jetson/") and msg.topic.endswith("/heartbeat"):
                gate_id = msg.topic.split("/")[1]
                self.handle_gate_heartbeat(gate_id, payload)
            # --------------S10 GATE DISCOVERY END--------------
                
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message on topic {msg.topic}: {msg.payload.decode()}")
            
    
    # --------------S10 GATE DISCOVERY--------------
    def handle_per_gate_status(self, gate_id, status):
        """Handle per-gate status updates"""
        current_time = time.time()
        
        # Update discovered gates
        if gate_id not in self.discovered_gates:
            self.discovered_gates[gate_id] = {"status": "online", "last_seen": current_time, "gate_status": "unknown"}
        
        self.discovered_gates[gate_id]["status"] = "online"
        self.discovered_gates[gate_id]["last_seen"] = current_time
        self.discovered_gates[gate_id]["gate_status"] = status.get("status", "unknown")
        
        # Add status alert
        try:
            from controllers.db_controller import add_alert
            add_alert(f"Gate {gate_id} status: {status.get('status', 'unknown')}", "info")
        except Exception as e:
            logger.error(f"Error adding gate status alert to database: {e}")
            self.add_alert(f"Gate {gate_id} status: {status.get('status', 'unknown')}", "info")
    
    def handle_per_gate_detection(self, gate_id, detection):
        """Handle per-gate detection updates"""
        objects = detection.get("objects", [])
        if objects:
            try:
                from controllers.db_controller import add_alert
                add_alert(f"Gate {gate_id}: Animal detected: {', '.join(objects)}", "warning")
            except Exception as e:
                logger.error(f"Error adding detection alert to database: {e}")
                self.add_alert(f"Gate {gate_id}: Animal detected: {', '.join(objects)}", "warning")
    
    def handle_gate_heartbeat(self, gate_id, heartbeat):
        """Handle gate heartbeat to track online/offline status"""
        current_time = time.time()
        
        if gate_id not in self.discovered_gates:
            self.discovered_gates[gate_id] = {"status": "online", "last_seen": current_time, "gate_status": "unknown"}
        
        self.discovered_gates[gate_id]["status"] = "online"
        self.discovered_gates[gate_id]["last_seen"] = current_time
    
    def get_discovered_gates(self):
        """Get list of discovered gates with their current status"""
        current_time = time.time()
        
        # Check for offline gates
        for gate_id, gate_info in self.discovered_gates.items():
            if current_time - gate_info["last_seen"] > self.gate_timeout:
                gate_info["status"] = "offline"
        
        return self.discovered_gates
    # --------------S10 GATE DISCOVERY END--------------
        
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
        logger.info(f"Alert added: {message}")
        
            
    def start_mqtt(self):
        """Start MQTT client connection"""
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")
            
        
    def stop(self):
        """Stop MQTT client and cleanup"""
        logger.info("Stopping MQTT client...")
        self.client.loop_stop()
        self.client.disconnect()

# Global instance
mqtt_client = None

def get_mqtt_client():
    """Get the global MQTT client instance"""
    global mqtt_client
    if mqtt_client is None:
        mqtt_client = WebAppMQTTClient()
    return mqtt_client

def main():
    """Main function to run the Web App MQTT client"""
    # Create and start MQTT client
    client = get_mqtt_client()
    
    try:
        # Start MQTT connection
        client.start_mqtt()
        
        # Keep running
        while True:
            time.sleep(1)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        client.stop()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        client.stop()

if __name__ == "__main__":
    main()