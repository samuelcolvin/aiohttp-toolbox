from pathlib import Path
from urllib.parse import urlparse

from arq import RedisSettings
from pydantic import BaseSettings, PyObject, validator

from .utils import pseudo_random_str


class Settings(BaseSettings):
    sql_path: Path
    pg_dsn: str
    pg_name: str = None
    # eg. the db already exists on heroku and never has to be created
    pg_db_exists = False

    redis_settings: RedisSettings = 'redis://localhost:6379'
    cookie_max_age = 25 * 3600
    cookie_update_age = 600
    port: int = 8000

    # you'll need to set this, pseudo_random_str is used to avoid a public default value ever being used in production
    auth_key = pseudo_random_str()

    max_request_size = 10 * 1024 ** 2  # 10MB
    locale = 'en_GB.utf8'

    worker_path: str = None  # note this needs to be a string not an object
    worker_name: str = 'Worker'

    create_app: PyObject = None

    @property
    def sql(self):
        return self.sql_path.read_text()

    @validator('pg_name', always=True, pre=True)
    def set_pg_name(cls, v, values, **kwargs):
        return urlparse(values['pg_dsn']).path.lstrip('/')

    @validator('redis_settings', always=True, pre=True)
    def parse_redis_settings(cls, v):
        conf = urlparse(v)
        return RedisSettings(
            host=conf.hostname, port=conf.port, password=conf.password, database=int((conf.path or '0').strip('/'))
        )

    class Config:
        fields = {'port': 'PORT', 'pg_dsn': 'DATABASE_URL'}
        arbitrary_types_allowed = True
