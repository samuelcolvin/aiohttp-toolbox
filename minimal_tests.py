"""
Tests for aiohttp-toolbox without [all] installed
"""
import pytest


async def test_create_default_app():
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


async def test_settings():
    from atoolbox.settings import BaseSettings, RedisSettings
    assert not hasattr(RedisSettings, 'port')

    class Settings(BaseSettings):
        pass

    s = Settings()
    assert s.redis_settings is None

    with pytest.raises(RuntimeError):
        Settings(REDISCLOUD_URL='redis://localhost:6379')
