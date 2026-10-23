import requests
import json

# Test the setup endpoint
try:
    data = {
        "project": "test_project",
        "schema": ""
    }
    response = requests.post('http://172.16.4.179:9090/setup', json=data)
    print(f"Setup Status Code: {response.status_code}")
    print(f"Setup Response: {response.text}")
except Exception as e:
    print(f"Setup Error: {e}")

# Test the health endpoint
try:
    response = requests.get('http://172.16.4.179:9090/health')
    print(f"Health Status Code: {response.status_code}")
    print(f"Health Response: {response.text}")
except Exception as e:
    print(f"Health Error: {e}")