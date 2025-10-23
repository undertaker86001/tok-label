#!/usr/bin/env python3
"""
Script to start the Mining Audio ML Backend Service
"""

import subprocess
import sys
import os

def start_service():
    """Start the mining audio ML backend service"""
    print("Starting Mining Audio ML Backend Service...")
    print()
    
    # Check if we're in the right directory
    if not os.path.exists('_wsgi.py'):
        print("Error: _wsgi.py not found in current directory.")
        print("Please run this script from the mining_audio directory.")
        return 1
    
    # Build the command
    cmd = [
        sys.executable,
        '_wsgi.py',
        '--host', '0.0.0.0',
        '--port', '9090',
        '--debug'
    ]
    
    print("Starting the ML backend service on port 9090...")
    print("Command:", ' '.join(cmd))
    print()
    
    try:
        # Run the command
        process = subprocess.Popen(cmd)
        print(f"Service started with PID {process.pid}")
        print("Press Ctrl+C to stop the service")
        print()
        
        # Wait for the process to complete
        process.wait()
        return process.returncode
        
    except KeyboardInterrupt:
        print("\nStopping service...")
        process.terminate()
        process.wait()
        print("Service stopped.")
        return 0
    except Exception as e:
        print(f"Error starting service: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(start_service())