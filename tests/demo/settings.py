from typing import List, Pattern

from atoolbox import BaseSettings, patch


class Settings(BaseSettings):
    pg_dsn: str = 'postgres://postgres@localhost:5432/atoolbox_demo'
    csrf_cross_origin_paths: List[Pattern] = ['/exec/']
    csrf_upload_paths: List[Pattern] = ['/upload-path/']


@patch
async def error_patch(*, conn, settings, **kwargs):
    """
    Patch which throws an error
    """
    raise RuntimeError('xx')


@patch(direct=True)
async def direct_path(*, conn, settings, **kwargs):
    """
    this is a "direct" patch
    """
    pass


@patch
def non_coro(*, conn, settings, args, **kwargs):
    """
    this is not a coroutine.
    """
    return len(args)
