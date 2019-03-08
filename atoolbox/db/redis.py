import asyncio

from .. import BaseSettings


async def async_flush_redis(settings: BaseSettings):
    from arq import create_pool

    redis = await create_pool(settings.redis_settings)
    await redis.flushdb()
    redis.close()
    await redis.wait_closed()


def flush_redis(settings: BaseSettings):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(async_flush_redis(settings))
