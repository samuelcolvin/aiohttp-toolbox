from aiohttp import web
from aiohttp_session import new_session

from aiohttptools import create_default_app


async def handle(request):
    return web.Response(text='testing')


async def handle_user(request):
    session = await new_session(request)
    async with request.app['pg'].acquire() as conn:
        session.update({'user_id': await conn.fetchval('SELECT id FROM users')})
    return web.Response(status=488)


async def handle_errors(request):
    do = request.match_info['do']
    if do == '500':
        raise web.HTTPInternalServerError(text='custom 500 error')
    elif do == 'value_error':
        raise ValueError('snap')
    elif do == 'return_499':
        return web.Response(text='499 response', status=499)
    return web.Response(text='ok')


def create_app(settings):
    routes = [
        web.get('/', handle),
        web.get('/user', handle_user),
        web.get('/{do}', handle_errors),
    ]
    return create_default_app(settings=settings, routes=routes)
