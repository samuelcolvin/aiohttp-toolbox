from aiohttp import web
from aiohttp_session import new_session
from pydantic import BaseModel, constr

from aiohttptools import create_default_app
from aiohttptools.bread import Bread


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


class OrganisationBread(Bread):
    class Model(BaseModel):
        name: str
        slug: constr(max_length=80)

    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True
    delete_enabled = True

    model = Model
    table = 'organisations'
    browse_order_by_fields = 'slug',


def create_app(settings):
    routes = [
        web.get('/', handle),
        web.get('/user', handle_user),
        web.get('/errors/{do}', handle_errors),
        *OrganisationBread.routes('/orgs/'),
    ]
    return create_default_app(settings=settings, routes=routes)
