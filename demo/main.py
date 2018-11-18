from aiohttp import web
from aiohttptools import create_default_app


async def handle(request):
    return web.Response(text='testing')


def create_app(settings):
    return create_default_app(settings=settings, routes=[web.get('/', handle)])
