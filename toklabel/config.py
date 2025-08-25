from dotenv import load_dotenv
import os

# Load environment variables from .env file
load_dotenv()

# Label Studio configuration
LABEL_STUDIO_URL = os.getenv('LABEL_STUDIO_URL', 'http://example.com:8080')
LABEL_STUDIO_API_KEY = os.getenv('LABEL_STUDIO_API_KEY')

# File server configuration
FILE_SERVER_URL = os.getenv('FILE_SERVER_URL', 'http://example.com:8000')

# Extractor server configuration
EXTRACTOR_SERVER_URL = os.getenv('EXTRACTOR_SERVER_URL', 'http://example.com:8001')

# Redis configuration
REDIS_HOST = os.getenv('REDIS_HOST', 'example.com')
REDIS_PORT = int(os.getenv('REDIS_PORT', '6379'))
REDIS_PASSWORD = os.getenv('REDIS_PASSWORD', 'example_password')
REDIS_DB = int(os.getenv('REDIS_DB', '0'))

# PostgreSQL configuration
POSTGRE_HOST = os.getenv('POSTGRE_HOST', 'example.com')
POSTGRE_PORT = os.getenv('POSTGRE_PORT', '5432')
POSTGRE_USER = os.getenv('POSTGRE_USER', 'example_user')
POSTGRE_PASSWORD = os.getenv('POSTGRE_PASSWORD', 'example_password')
POSTGRE_DATABASE = os.getenv('POSTGRE_DATABASE', 'example_db')

# Doris configuration
DORIS_FE_HOST = os.getenv('DORIS_FE_HOST', 'example.com')
DORIS_FE_PORT = int(os.getenv('DORIS_FE_PORT', '9030'))
DORIS_USER = os.getenv('DORIS_USER', 'root')
DORIS_PASSWORD = os.getenv('DORIS_PASSWORD', 'example_password')
DORIS_DATABASE = os.getenv('DORIS_DATABASE', 'example_db')

# Database type selection
DATABASE_TYPE = os.getenv('DATABASE_TYPE', 'postgresql')  # 'postgresql' or 'doris'

# Database connection pool settings
DB_POOL_SIZE = int(os.getenv('DB_POOL_SIZE', '10'))
DB_MAX_OVERFLOW = int(os.getenv('DB_MAX_OVERFLOW', '20'))
DB_POOL_TIMEOUT = int(os.getenv('DB_POOL_TIMEOUT', '30'))

# Performance tuning settings
DORIS_QUERY_TIMEOUT = int(os.getenv('DORIS_QUERY_TIMEOUT', '300'))  # seconds
DORIS_BATCH_SIZE = int(os.getenv('DORIS_BATCH_SIZE', '1000'))
POSTGRES_QUERY_TIMEOUT = int(os.getenv('POSTGRES_QUERY_TIMEOUT', '300'))
POSTGRES_BATCH_SIZE = int(os.getenv('POSTGRES_BATCH_SIZE', '1000'))

# Feature flags
ENABLE_QUERY_CACHE = os.getenv('ENABLE_QUERY_CACHE', 'false').lower() == 'true'
ENABLE_CONNECTION_POOLING = os.getenv('ENABLE_CONNECTION_POOLING', 'true').lower() == 'true'
ENABLE_QUERY_LOGGING = os.getenv('ENABLE_QUERY_LOGGING', 'false').lower() == 'true'
