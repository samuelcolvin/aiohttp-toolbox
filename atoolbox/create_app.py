import asyncio
import logging
import warnings
from typing import Optional

from aiohttp import ClientSession, ClientTimeout, web

from .middleware import csrf_middleware, error_middleware, pg_middleware
from .settings import BaseSettings

logger = logging.getLogger('atoolbox.web')


async def startup(app: web.Application):
    settings: Optional[BaseSettings] = app['settings']
    if not settings:
        return
    # if pg is already set the database doesn't need to be created
    if 'pg' not in app and getattr(settings, 'pg_dsn', None):
        try:
            from .db import prepare_database
            from buildpg import asyncpg
        except ImportError:
            warnings.warn('buildpg and asyncpg need to be installed to use postgres', RuntimeWarning)
        else:
            await prepare_database(settings, False)
            app['pg'] = await asyncpg.create_pool_b(dsn=settings.pg_dsn, min_size=2)

    if 'redis' not in app and getattr(settings, 'redis_settings', None):
        try:
            from arq import create_pool
        except ImportError:
            warnings.warn('arq and aioredis need to be installed to use redis', RuntimeWarning)
        else:
            app['redis'] = await create_pool(settings.redis_settings)

    if getattr(settings, 'create_http_client', False):
        timeout = getattr(settings, 'http_client_timeout', 30)
        app['http_client'] = ClientSession(timeout=ClientTimeout(total=timeout))


async def cleanup(app: web.Application):
    close_coros = []
    http_client = app.get('http_client')
    if http_client:
        close_coros.append(http_client.close())

    redis = app.get('redis')
    if redis and not redis.closed:
        redis.close()
        close_coros.append(redis.wait_closed())

    pg = app.get('pg')
    if pg:
        close_coros.append(pg.close())

    await asyncio.gather(*close_coros)


async def create_default_app(*, settings: BaseSettings = None, middleware=None, routes=None):
    auth_key = getattr(settings, 'auth_key', None)
    if not middleware:
        middleware = (error_middleware, pg_middleware, csrf_middleware)
        if auth_key:
            try:
                from aiohttp_session import session_middleware
                from aiohttp_session.cookie_storage import EncryptedCookieStorage
            except ImportError:
                warnings.warn('aiohttp_session and cryptography needs to be installed to use sessions', RuntimeWarning)
            else:
                cookie_name = getattr(settings, 'cookie_name', None) or 'AIOHTTP_SESSION'
                middleware = (
                    session_middleware(EncryptedCookieStorage(auth_key, cookie_name=cookie_name)),
                ) + middleware

    kwargs = {}
    if hasattr(settings, 'max_request_size'):
        kwargs['client_max_size'] = settings.max_request_size

    app = web.Application(middlewares=middleware, **kwargs)

    app['settings'] = settings
    if auth_key:
        try:
            from cryptography import fernet
        except ImportError:
            warnings.warn('cryptography needs to be installed to use auth_key', RuntimeWarning)
        else:
            app['auth_fernet'] = fernet.Fernet(auth_key)

    app.on_startup.append(startup)
    app.on_cleanup.append(cleanup)
    if routes:
        app.add_routes(routes)
    return app
