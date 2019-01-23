import asyncio

from .. import BaseSettings


async def async_flush_redis(settings: BaseSettings, loop):
    from arq import create_pool_lenient

    redis = await create_pool_lenient(settings.redis_settings, loop=loop)
    await redis.flushdb()
    redis.close()
    await redis.wait_closed()


def flush_redis(settings: BaseSettings):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_flush_redis(settings, loop))
