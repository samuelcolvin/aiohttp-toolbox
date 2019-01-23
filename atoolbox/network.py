import asyncio
import logging

from aiohttp import ClientSession
from async_timeout import timeout

from .settings import BaseSettings

logger = logging.getLogger('atoolbox.network')


async def async_wait_port_open(host, port, delay, loop):
    step_size = 0.05
    steps = int(delay / step_size)
    start = loop.time()
    for i in range(steps):
        step_start = loop.time()
        try:
            async with timeout(step_size, loop=loop):
                transport, proto = await loop.create_connection(lambda: asyncio.Protocol(), host=host, port=port)
        except (asyncio.TimeoutError, OSError):
            elapsed = loop.time() - step_start
            await asyncio.sleep(max(0, step_size - elapsed), loop=loop)
        else:
            transport.close()
            logger.debug('Connected successfully to %s:%s after %0.2fs', host, port, loop.time() - start)
            return
    raise RuntimeError(f'Unable to connect to {host}:{port} after {loop.time() - start:0.2f}s')


def wait_for_services(settings: BaseSettings, *, delay=5) -> int:
    """
    Wait for up to `delay` seconds for postgres and redis ports to be open. Will raise an error if ports
    are not open in time. Returns the number of services checked.
    """
    loop = asyncio.get_event_loop()
    coros = []
    if settings.pg_dsn:
        coros.append(async_wait_port_open(settings.pg_host, settings.pg_port, delay, loop))
        logger.debug('waiting for postgres to come up...')
    if settings.redis_settings:
        coros.append(async_wait_port_open(settings.redis_settings.host, settings.redis_settings.port, delay, loop))
        logger.debug('waiting for redis to come up...')

    if coros:
        return len(loop.run_until_complete(asyncio.gather(*coros)))
    else:
        return 0


async def async_check_server(url: str, expected_status: int, loop) -> int:
    start = loop.time()
    try:
        async with timeout(5):
            async with ClientSession() as session:
                async with session.get(url) as r:
                    assert r.status == expected_status, f'response error {r.status} != {expected_status}'
    except (asyncio.TimeoutError, ValueError, AssertionError, OSError) as e:
        logger.error('web check error, %s: %s, url: "%s"', e.__class__.__name__, e, url)
        return 1
    else:
        logger.info('web check successful "%s" > %d in %0.3fs', url, expected_status, loop.time() - start)
        return 0


def check_server(url: str, expected_status: int = 200) -> int:
    """
    Check whether an HTTP server at url is running, return 0 if it is (and has correct response code) and 1 if not.
    """
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(async_check_server(url, expected_status, loop))
