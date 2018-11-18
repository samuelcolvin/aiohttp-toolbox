from aiohttptools import BaseSettings


class Settings(BaseSettings):
    pg_dsn: str = 'postgres://postgres@localhost:5432/atools_demo'
