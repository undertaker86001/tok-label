import sys
import os

# Add the mining_audio directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'ml-backends', 'mining_audio'))

from model import S3Config
import json

def test_s3_config():
    # Test loading configuration from file
    config_file_path = os.path.join(os.path.dirname(__file__), 'ml-backends', 'mining_audio', 'config.json')
    
    print("Testing S3 Configuration Loading...")
    s3_config = S3Config(config_file_path)
    
    print(f"URL: {s3_config.url}")
    print(f"Access Key: {s3_config.access_key}")
    print(f"Secret Key: {s3_config.secret_key}")
    print(f"API: {s3_config.api}")
    print(f"Path Style: {s3_config.path_style}")
    
    print("\nTesting boto3 configuration conversion...")
    boto3_config = s3_config.to_boto3_config()
    print(f"Boto3 Config: {boto3_config}")
    
    print(f"\nIs configured: {s3_config.is_configured()}")

if __name__ == "__main__":
    test_s3_config()