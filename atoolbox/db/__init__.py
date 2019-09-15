import asyncio
import logging
import os

from buildpg import asyncpg

from ..settings import BaseSettings
from .connection import lenient_conn

logger = logging.getLogger('atoolbox.db')
DROP_CONNECTIONS = """
select pg_terminate_backend(pg_stat_activity.pid)
from pg_stat_activity
where pg_stat_activity.datname = $1 AND pid <> pg_backend_pid();
"""


async def prepare_database(settings: BaseSettings, overwrite_existing: bool) -> bool:  # noqa: C901 (ignore complexity)
    """
    (Re)create a fresh database and run migrations.
    :param settings: settings to use for db connection
    :param overwrite_existing: whether or not to drop an existing database if it exists
    :return: whether or not a database has been (re)created
    """
    if settings.pg_db_exists:
        conn = await lenient_conn(settings, with_db=True)
        try:
            tables = await conn.fetchval("select count(*) from information_schema.tables where table_schema='public'")
            logger.info('existing tables: %d', tables)
            if tables > 0:
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.debug('database already exists ✓')
                    return False
        finally:
            await conn.close()
    else:
        conn = await lenient_conn(settings, with_db=False)
        try:
            if not overwrite_existing:
                # don't drop connections and try creating a db if it already exists and we're not overwriting
                exists = await conn.fetchval('select 1 from pg_database where datname=$1', settings.pg_name)
                if exists:
                    return False

            await conn.execute(DROP_CONNECTIONS, settings.pg_name)
            logger.debug('attempting to create database "%s"...', settings.pg_name)
            try:
                await conn.execute('create database {}'.format(settings.pg_name))
            except (asyncpg.DuplicateDatabaseError, asyncpg.UniqueViolationError):
                if overwrite_existing:
                    logger.debug('database already exists...')
                else:
                    logger.debug('database already exists, skipping creation')
                    return False
            else:
                logger.debug('database did not exist, now created')

            logger.debug('settings db timezone to utc...')
            await conn.execute(f"alter database {settings.pg_name} set timezone to 'UTC';")
        finally:
            await conn.close()

    logger.debug('dropping and re-creating teh schema...')
    conn = await asyncpg.connect(dsn=settings.pg_dsn)
    try:
        async with conn.transaction():
            await conn.execute('drop schema public cascade;\ncreate schema public;')
    finally:
        await conn.close()

    logger.debug('creating tables from model definition...')
    conn = await asyncpg.connect(dsn=settings.pg_dsn)
    try:
        async with conn.transaction():
            await conn.execute(settings.sql)
    finally:
        await conn.close()
    logger.info('database successfully setup ✓')
    return True


def reset_database(settings: BaseSettings):
    if not (os.getenv('CONFIRM_DATABASE_RESET') == 'confirm' or input('Confirm database reset? [yN] ') == 'y'):
        print('cancelling')
    else:
        print('resetting database...')
        loop = asyncio.get_event_loop()
        loop.run_until_complete(prepare_database(settings, True))
        print('done.')
