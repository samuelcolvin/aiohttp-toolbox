import asyncio
import logging

from async_timeout import timeout
from buildpg import asyncpg

from atoolbox.settings import BaseSettings

logger = logging.getLogger('atoolbox.db.connection')


async def lenient_conn(settings: BaseSettings, with_db=True):
    if with_db:
        dsn = settings.pg_dsn
    else:
        dsn, _ = settings.pg_dsn.rsplit('/', 1)

    for retry in range(8, -1, -1):
        try:
            async with timeout(2):
                conn = await asyncpg.connect_b(dsn=dsn)
        except (asyncpg.PostgresError, OSError) as e:
            if retry == 0:
                raise
            else:
                logger.warning('pg temporary connection error "%s", %d retries remaining...', e, retry)
                await asyncio.sleep(1)
        else:
            log = logger.debug if retry == 8 else logger.info
            log('pg connection successful, version: %s', await conn.fetchval('SELECT version()'))
            return conn
