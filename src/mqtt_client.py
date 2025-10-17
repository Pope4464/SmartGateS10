#!/usr/bin/env python3
"""
MQTT Client for Jetson Nano
Connects to MQTT broker and provides health/status endpoints
"""

import paho.mqtt.client as mqtt
import json
import time
import threading
from datetime import datetime
import logging
from fastapi import FastAPI
from fastapi.responses import JSONResponse
import uvicorn
import os

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JetsonMQTTClient:
    def __init__(self, broker_host="localhost", broker_port=1883, client_id="jetson_nano"):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.client = mqtt.Client(client_id)
        self.connected = False
        self.last_message_time = None
        self.message_count = 0
        
        # Setup MQTT callbacks
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.on_message = self.on_message
        self.client.on_publish = self.on_publish
        
        # FastAPI app for health/status endpoints
        self.app = FastAPI(title="Jetson Nano MQTT Client", version="1.0.0")
        self.setup_fastapi_routes()
        
    def on_connect(self, client, userdata, flags, rc):
        """Callback for when the client connects to the broker"""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker_host}:{self.broker_port}")
            
            # Subscribe to topics
            client.subscribe("jetson/status")
            client.subscribe("jetson/commands")
            client.subscribe("system/heartbeat")
            
            # Publish initial status
            self.publish_status()
        else:
            logger.error(f"Failed to connect to MQTT broker. Return code: {rc}")
            
    def on_disconnect(self, client, userdata, rc):
        """Callback for when the client disconnects from the broker"""
        self.connected = False
        logger.warning(f"Disconnected from MQTT broker. Return code: {rc}")
        
    def on_message(self, client, userdata, msg):
        """Callback for when a message is received"""
        self.last_message_time = datetime.now()
        self.message_count += 1
        
        try:
            payload = json.loads(msg.payload.decode())
            logger.info(f"Received message on topic {msg.topic}: {payload}")
            
            # Handle different message types
            if msg.topic == "jetson/commands":
                self.handle_command(payload)
            elif msg.topic == "system/heartbeat":
                self.handle_heartbeat(payload)
                
        except json.JSONDecodeError:
            logger.warning(f"Received non-JSON message on topic {msg.topic}: {msg.payload.decode()}")
            
    def on_publish(self, client, userdata, mid):
        """Callback for when a message is published"""
        logger.debug(f"Message {mid} published successfully")
        
    def handle_command(self, command):
        """Handle incoming commands"""
        logger.info(f"Processing command: {command}")
        
        # Example command handling
        if command.get("action") == "status_request":
            self.publish_status()
        elif command.get("action") == "restart":
            logger.info("Restart command received")
            # Add restart logic here if needed
            
    def handle_heartbeat(self, heartbeat):
        """Handle heartbeat messages"""
        logger.debug(f"Heartbeat received: {heartbeat}")
        
    def publish_status(self):
        """Publish current status to MQTT"""
        status = {
            "client_id": self.client_id,
            "timestamp": datetime.now().isoformat(),
            "connected": self.connected,
            "message_count": self.message_count,
            "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
            "system_info": {
                "platform": "jetson_nano",
                "uptime": time.time()
            }
        }
        
        topic = f"jetson/status/{self.client_id}"
        self.client.publish(topic, json.dumps(status))
        logger.info(f"Published status to topic {topic}")
        
    def publish_health(self):
        """Publish health check to MQTT"""
        health = {
            "client_id": self.client_id,
            "timestamp": datetime.now().isoformat(),
            "status": "healthy" if self.connected else "unhealthy",
            "mqtt_connected": self.connected,
            "last_activity": self.last_message_time.isoformat() if self.last_message_time else None
        }
        
        topic = f"jetson/health/{self.client_id}"
        self.client.publish(topic, json.dumps(health))
        logger.info(f"Published health to topic {topic}")
        
    def setup_fastapi_routes(self):
        """Setup FastAPI routes for health and status endpoints"""
        
        @self.app.get('/health')
        async def health():
            """Health check endpoint"""
            health_status = {
                "status": "healthy" if self.connected else "unhealthy",
                "timestamp": datetime.now().isoformat(),
                "mqtt_connected": self.connected,
                "client_id": self.client_id,
                "message_count": self.message_count,
                "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None
            }
            return JSONResponse(content=health_status)
            
        @self.app.get('/status')
        async def status():
            """Status endpoint with detailed information"""
            status_info = {
                "client_id": self.client_id,
                "timestamp": datetime.now().isoformat(),
                "mqtt_connected": self.connected,
                "broker_host": self.broker_host,
                "broker_port": self.broker_port,
                "message_count": self.message_count,
                "last_message_time": self.last_message_time.isoformat() if self.last_message_time else None,
                "system_info": {
                    "platform": "jetson_nano",
                    "uptime": time.time()
                },
                "subscribed_topics": [
                    "jetson/status",
                    "jetson/commands", 
                    "system/heartbeat"
                ]
            }
            return JSONResponse(content=status_info)
            
    def start_mqtt(self):
        """Start MQTT client connection"""
        try:
            logger.info(f"Connecting to MQTT broker at {self.broker_host}:{self.broker_port}")
            self.client.connect(self.broker_host, self.broker_port, 60)
            self.client.loop_start()
            
            # Start periodic status publishing
            def periodic_status():
                while True:
                    time.sleep(30)  # Publish status every 30 seconds
                    if self.connected:
                        self.publish_status()
                        self.publish_health()
                        
            status_thread = threading.Thread(target=periodic_status, daemon=True)
            status_thread.start()
            
        except Exception as e:
            logger.error(f"Failed to start MQTT client: {e}")
            
    def start_fastapi(self, host='0.0.0.0', port=5000):
        """Start FastAPI web server"""
        logger.info(f"Starting FastAPI server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, log_level="info")
        
    def stop(self):
        """Stop MQTT client and cleanup"""
        logger.info("Stopping MQTT client...")
        self.client.loop_stop()
        self.client.disconnect()

def main():
    """Main function to run the Jetson MQTT client"""
    # Configuration - modify these values as needed
    BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
    BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", "1883"))
    CLIENT_ID = os.getenv("MQTT_CLIENT_ID", "jetson_nano")
    FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))
    
    # Create and start MQTT client
    mqtt_client = JetsonMQTTClient(
        broker_host=BROKER_HOST,
        broker_port=BROKER_PORT,
        client_id=CLIENT_ID
    )
    
    try:
        # Start MQTT connection
        mqtt_client.start_mqtt()
        
        # Start FastAPI server in main thread
        mqtt_client.start_fastapi(port=FLASK_PORT)
        
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        mqtt_client.stop()
    except Exception as e:
        logger.error(f"Error in main: {e}")
        mqtt_client.stop()

if __name__ == "__main__":
    main()
