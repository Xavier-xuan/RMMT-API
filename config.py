from datetime import timedelta


class GeneralConfig:
    DATABASE_URL = "mysql+pymysql://rmmt:12345678@127.0.0.1:3306/rmmt"
    JWT_SECRET_KEY = "R2xpmzp1F9QcpHn9"
    DATABASE_LOG = True
    ASYNC_JOB_SCAN_INTERVAL = 10  # in seconds
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
