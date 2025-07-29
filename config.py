import os
from datetime import timedelta

class GeneralConfig:
    # 从环境变量读取数据库配置
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = os.getenv('DB_PORT', '3306')
    DB_NAME = os.getenv('DB_NAME', 'roommate')
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD', '')
    
    # 构建数据库URL
    DATABASE_URL = f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
    
    JWT_SECRET_KEY = os.getenv('JWT_SECRET', "R2xpmzp1F9QcpHn9")
    DATABASE_LOG = os.getenv('DATABASE_LOG', 'True').lower() == 'true'
    ASYNC_JOB_SCAN_INTERVAL = int(os.getenv('ASYNC_JOB_SCAN_INTERVAL', '10'))  # in seconds
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
