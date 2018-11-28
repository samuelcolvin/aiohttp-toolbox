from pathlib import Path
from typing import List, Pattern
from urllib.parse import urlparse

from arq import RedisSettings
from cryptography.fernet import Fernet
from pydantic import BaseSettings as _BaseSettings, validator


class BaseSettings(_BaseSettings):
    worker_func: str = None
    create_app: str = 'main.create_app'

    sql_path: Path = 'models.sql'
    pg_dsn: str = 'postgres://postgres@localhost:5432/app'
    # eg. the db already exists on heroku and never has to be created
    pg_db_exists = False

    redis_settings: RedisSettings = 'redis://localhost:6379'
    port: int = 8000

    # you'll need to set this, generate_key is used to avoid a public default value ever being used in production
    auth_key: str = Fernet.generate_key().decode()

    max_request_size = 10 * 1024 ** 2  # 10MB
    locale = 'en_GB.utf8'

    http_client_timeout = 10

    csrf_ignore_paths: List[Pattern] = []
    csrf_upload_paths: List[Pattern] = []
    csrf_cross_origin_paths: List[Pattern] = []
    cross_origin_origins: List[Pattern] = []

    cookie_name = 'aiohttp-app'

    grecaptcha_url = 'https://www.google.com/recaptcha/api/siteverify'
    grecaptcha_secret = 'not-configured'

    @property
    def sql(self):
        return self.sql_path.read_text()

    @property
    def pg_name(self):
        return urlparse(self.pg_dsn).path.lstrip('/')

    @validator('redis_settings', always=True, pre=True)
    def parse_redis_settings(cls, v):
        conf = urlparse(v)
        return RedisSettings(
            host=conf.hostname, port=conf.port, password=conf.password, database=int((conf.path or '0').strip('/'))
        )

    class Config:
        fields = {'port': 'PORT', 'pg_dsn': 'DATABASE_URL', 'redis_settings': 'REDISCLOUD_URL'}
