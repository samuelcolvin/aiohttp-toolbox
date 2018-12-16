"""
Tests for aiohttp-toolbox without [all] installed
"""
import pytest
from pydantic import BaseSettings as PydanticBaseSettings


async def test_create_no_setting():
    from atoolbox import create_default_app
    from atoolbox.create_app import startup, cleanup
    app = await create_default_app()
    assert app['settings'] is None
    assert 'auth_fernet' not in app
    assert 'http_client' not in app
    assert len(app.middlewares) == 3

    await startup(app)
    assert 'http_client' in app
    assert 'pg' not in app
    assert 'redis' not in app
    await cleanup(app)


async def test_create_setting():
    from atoolbox import BaseSettings, create_default_app
    from atoolbox.create_app import startup, cleanup
    settings = BaseSettings()
    app = await create_default_app(settings=settings)
    assert app['settings'] is not None
    assert 'auth_fernet' not in app
    assert 'http_client' not in app
    assert len(app.middlewares) == 3

    await startup(app)
    assert 'http_client' in app
    assert 'pg' not in app
    assert 'redis' not in app
    await cleanup(app)


async def test_create_setting_warnings():
    from atoolbox import create_default_app
    from atoolbox.create_app import startup, cleanup

    class Settings(PydanticBaseSettings):
        pg_dsn = 'x'
        redis_settings = True
        auth_key = True

    with pytest.warns(RuntimeWarning) as record:
        # can't use normal BaseSettings as parse_redis_settings would raise an error
        app = await create_default_app(settings=Settings())
    assert len(record) == 2

    assert app['settings'] is not None

    with pytest.warns(RuntimeWarning) as record:
        await startup(app)
    assert len(record) == 2

    assert 'pg' not in app
    assert 'redis' not in app
    await cleanup(app)


async def test_settings_defaults_none():
    from atoolbox.settings import BaseSettings, RedisSettings
    assert RedisSettings.__module__ == 'atoolbox.settings'

    s = BaseSettings()
    assert s.redis_settings is None
    assert s.pg_dsn is None
    assert s.auth_key is None

    with pytest.raises(RuntimeError):
        BaseSettings(REDISCLOUD_URL='redis://localhost:6379')
