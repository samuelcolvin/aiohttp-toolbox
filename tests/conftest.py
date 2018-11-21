import asyncio
import json

import pytest
from aiohttp.test_utils import teardown_test_loop
from aioredis import create_redis
from buildpg import asyncpg

from atoolbox.db import prepare_database
from atoolbox.db.helpers import SimplePgPool
from atoolbox.test_utils import DummyServer, create_dummy_server
from demo.main import create_app
from demo.settings import Settings

settings_args = dict(
    DATABASE_URL='postgres://postgres@localhost:5432/atoolbox_test',
    REDISCLOUD_URL='redis://localhost:6379/6',
    create_app='tests.demo.main.create_app',
    sql_path='tests/demo/models.sql',
)


@pytest.fixture(scope='session', name='settings_session')
def _fix_settings_session():
    return Settings(**settings_args)


@pytest.fixture(scope='session', name='clean_db')
def _fix_clean_db(request, settings_session):
    # loop fixture has function scope so can't be used here.
    loop = asyncio.new_event_loop()
    loop.run_until_complete(prepare_database(settings_session, True))
    teardown_test_loop(loop)


@pytest.fixture(name='dummy_server')
async def _fix_dummy_server(loop, aiohttp_server):
    return await create_dummy_server(aiohttp_server)


replaced_url_fields = ('grecaptcha_url',)


@pytest.fixture(name='settings')
def _fix_settings(dummy_server: DummyServer, request, tmpdir):
    return Settings(**{f: f'{dummy_server.server_name}/{f}/' for f in replaced_url_fields}, **settings_args)


@pytest.fixture(name='db_conn')
async def _fix_db_conn(loop, settings, clean_db):
    conn = await asyncpg.connect_b(dsn=settings.pg_dsn, loop=loop)

    tr = conn.transaction()
    await tr.start()

    yield conn

    await tr.rollback()
    await conn.close()


@pytest.yield_fixture
async def redis(loop, settings):
    addr = settings.redis_settings.host, settings.redis_settings.port
    redis = await create_redis(addr, db=settings.redis_settings.database, loop=loop)
    await redis.flushdb()

    yield redis

    redis.close()
    await redis.wait_closed()


async def pre_startup_app(app):
    app['pg'] = SimplePgPool(app['test_conn'])


@pytest.fixture(name='cli')
async def _fix_cli(settings, db_conn, aiohttp_client, redis, loop):
    loop.set_debug(True)
    app = await create_app(settings=settings)
    app['test_conn'] = db_conn
    app.on_startup.insert(0, pre_startup_app)
    cli = await aiohttp_client(app)

    async def post_json(url, data=None, *, origin=None):
        if isinstance(data, (dict, list)):
            data = json.dumps(data)

        return await cli.post(
            url,
            data=data,
            headers={
                'Content-Type': 'application/json',
                'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
                'Origin': origin or f'http://127.0.0.1:{cli.server.port}',
            },
        )

    cli.post_json = post_json
    return cli
