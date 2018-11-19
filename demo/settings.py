from typing import List, Pattern

from aiohttptools import BaseSettings


class Settings(BaseSettings):
    pg_dsn: str = 'postgres://postgres@localhost:5432/atools_demo'
    csrf_cross_origin_paths: List[Pattern] = ['/exec/']
