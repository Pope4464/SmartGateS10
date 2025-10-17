#!/usr/bin/env python3
"""
SSH Reverse Tunnel Client for Jetson Nano
Connects to AWS EC2 and creates reverse tunnel
"""

import subprocess
import time
import logging
import os
import signal
import sys
import json
from pathlib import Path

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ReverseTunnelClient:
    def __init__(self, config_path="../config.json"):
        # Load configuration
        self.config = self.load_config(config_path)
        
        # Extract tunnel settings
        tunnel_config = self.config['reverse_tunnel']
        aws_config = self.config['aws_ec2']
        
        self.aws_host = aws_config['instance_ip']
        self.aws_port = tunnel_config['aws_port']
        self.local_port = tunnel_config['local_port']
        self.remote_port = tunnel_config['remote_port']
        self.key_path = Path(__file__).parent / "aws_key"
        self.ssh_process = None
        
    def load_config(self, config_path):
        """Load configuration from JSON file"""
        try:
            with open(config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            # Fallback to default values
            return {
                'aws_ec2': {
                    'instance_ip': 'localhost'
                },
                'reverse_tunnel': {
                    'aws_port': 22,
                    'local_port': 22,
                    'remote_port': 2222
                }
            }
        
    def start_tunnel(self):
        """Start SSH reverse tunnel client"""
        try:
            # Make sure key has correct permissions
            os.chmod(self.key_path, 0o600)
            
            # SSH command to create reverse tunnel
            ssh_cmd = [
                "ssh", "-i", str(self.key_path),
                "-N", "-R", f"{self.remote_port}:localhost:{self.local_port}",
                "-o", "StrictHostKeyChecking=no",
                "-o", "UserKnownHostsFile=/dev/null",
                "-o", "ServerAliveInterval=30",
                "-o", "ServerAliveCountMax=3",
                f"ec2-user@{self.aws_host}"
            ]
            
            logger.info(f"Connecting to AWS EC2 at {self.aws_host}")
            logger.info(f"Creating reverse tunnel: {self.remote_port}:localhost:{self.local_port}")
            logger.info(f"Command: {' '.join(ssh_cmd)}")
            
            # Start SSH process
            self.ssh_process = subprocess.Popen(ssh_cmd)
            
            # Wait for process
            while self.ssh_process.poll() is None:
                time.sleep(1)
                
        except Exception as e:
            logger.error(f"Failed to start reverse tunnel: {e}")
            
    def stop_tunnel(self):
        """Stop the reverse tunnel"""
        if self.ssh_process:
            logger.info("Stopping reverse tunnel...")
            self.ssh_process.terminate()
            self.ssh_process.wait()
            
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal")
        self.stop_tunnel()
        sys.exit(0)

def main():
    """Main function"""
    # Create tunnel client (loads config automatically)
    tunnel = ReverseTunnelClient()
    
    # Check if AWS host is configured
    if tunnel.aws_host == "YOUR_EC2_PUBLIC_IP":
        logger.error("Please update config.json with your actual EC2 instance IP address")
        sys.exit(1)
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, tunnel.signal_handler)
    signal.signal(signal.SIGTERM, tunnel.signal_handler)
    
    try:
        tunnel.start_tunnel()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        tunnel.stop_tunnel()

if __name__ == "__main__":
    main()
