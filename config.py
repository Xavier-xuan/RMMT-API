from datetime import timedelta


class GeneralConfig:
    DATABASE_URL = "mysql+pymysql://root:@localhost:4403/RMMT"
    JWT_SECRET_KEY = "R2xpmzp1F9QcpHn9"
    DATABASE_LOG = True
    ASYNC_JOB_SCAN_INTERVAL = 10  # in seconds
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)
    JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=30)
