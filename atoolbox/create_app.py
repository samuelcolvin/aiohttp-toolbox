import asyncio
import logging

from aiohttp import ClientSession, ClientTimeout, web
from aiohttp_session import session_middleware
from aiohttp_session.cookie_storage import EncryptedCookieStorage
from arq import create_pool_lenient
from buildpg import asyncpg
from cryptography import fernet

from .db import prepare_database
from .logs import setup_logging
from .middleware import csrf_middleware, error_middleware, pg_middleware
from .settings import BaseSettings

logger = logging.getLogger('atoolbox.web')


async def startup(app: web.Application):
    settings: BaseSettings = app['settings']
    # if pg is already set the database doesn't need to be created
    'pg' in app or await prepare_database(settings, False)

    redis = await create_pool_lenient(settings.redis_settings, app.loop)
    http_client = ClientSession(timeout=ClientTimeout(total=settings.http_client_timeout), loop=app.loop)
    app.update(
        pg=app.get('pg') or await asyncpg.create_pool_b(dsn=settings.pg_dsn, min_size=2),
        redis=redis,
        http_client=http_client,
    )


async def cleanup(app: web.Application):
    redis = app['redis']
    if not redis.closed:
        redis.close()
    await asyncio.gather(app['pg'].close(), app['http_client'].close(), redis.wait_closed())
    logging_client = app['logging_client']
    transport = logging_client and logging_client.remote.get_transport()
    transport and await transport.close()


async def create_default_app(*, settings: BaseSettings, logging_client=None, middleware=None, routes=None):
    logging_client = logging_client or setup_logging()

    middleware = middleware or (
        session_middleware(EncryptedCookieStorage(settings.auth_key, cookie_name=settings.cookie_name)),
        error_middleware,
        pg_middleware,
        csrf_middleware,
    )

    app = web.Application(logger=None, middlewares=middleware, client_max_size=settings.max_request_size)

    app.update(settings=settings, auth_fernet=fernet.Fernet(settings.auth_key), logging_client=logging_client)

    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    if routes:
        app.add_routes(routes)
    return app
