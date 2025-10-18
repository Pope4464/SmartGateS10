#!/usr/bin/env python3
"""
S10 MQTT Client for Jetson Nano
Minimal MQTT client for S10 integration
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class JetsonMQTTClient:
    def __init__(self, broker_host="54.252.172.171", broker_port=1883, gate_id="1"):
        self.gate_id = gate_id
        self.client = mqtt.Client(f"jetson_gate_{gate_id}")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.connected = False
        
        # Start connection in background thread
        def connect():
            try:
                self.client.connect(broker_host, broker_port, 60)
                self.client.loop_forever()
            except Exception as e:
                logger.error(f"MQTT connection failed: {e}")
        
        mqtt_thread = threading.Thread(target=connect, daemon=True)
        mqtt_thread.start()
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self.connected = True
            # Subscribe to per-gate command topic
            client.subscribe(f"jetson/{self.gate_id}/commands")
            logger.info(f"Connected to MQTT broker as gate {self.gate_id}")
            
            # Start heartbeat
            self.start_heartbeat()
    
    def on_message(self, client, userdata, msg):
        if msg.topic == f"jetson/{self.gate_id}/commands":
            try:
                command = json.loads(msg.payload.decode())
                action = command.get("action")
                if action in ["OPEN_DOOR", "CLOSE_DOOR"]:
                    # Import here to avoid circular imports
                    from main.door_control import DoorControl
                    door = DoorControl()
                    if action == "OPEN_DOOR":
                        door.open_door()
                    elif action == "CLOSE_DOOR":
                        door.close_door()
                # Note: Stream commands (start_stream, stop_stream) are handled via reverse tunnel HTTP
            except Exception as e:
                logger.error(f"Error handling command: {e}")
    
    def publish_detection(self, objects):
        if self.connected:
            data = {"objects": objects, "timestamp": time.time()}
            self.client.publish(f"jetson/{self.gate_id}/detection", json.dumps(data))
    
    def publish_status(self, status):
        if self.connected:
            data = {"status": status, "timestamp": time.time()}
            self.client.publish(f"jetson/{self.gate_id}/status", json.dumps(data))
    
    def start_heartbeat(self):
        """Start heartbeat thread to send periodic status updates"""
        def heartbeat():
            while self.connected:
                try:
                    heartbeat_data = {"gate_id": self.gate_id, "timestamp": time.time()}
                    self.client.publish(f"jetson/{self.gate_id}/heartbeat", json.dumps(heartbeat_data))
                    time.sleep(10)  # Send heartbeat every 10 seconds
                except Exception as e:
                    logger.error(f"Heartbeat error: {e}")
                    break
        
        heartbeat_thread = threading.Thread(target=heartbeat, daemon=True)
        heartbeat_thread.start()

# Global instance - Gate ID should be configured per deployment
# For now, default to gate 1, but this should be configurable
import os
gate_id = os.environ.get("GATE_ID", "1")
mqtt_client = JetsonMQTTClient(gate_id=gate_id)
