from aiohttp import web
from aiohttp_session import new_session
from pydantic import BaseModel, constr

from atoolbox import create_default_app, parse_request
from atoolbox.auth import check_grecaptcha
from atoolbox.bread import Bread, ExecView
from atoolbox.utils import decrypt_json, encrypt_json, json_response


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


async def encrypt(request):
    data = await request.json()
    return json_response(token=encrypt_json(request.app, data))


async def decrypt(request):
    data = await request.json()
    return json_response(**decrypt_json(request.app, data['token'].encode()))


class MyModel(BaseModel):
    v: int
    grecaptcha_token: str


async def grecaptcha(request):
    m = await parse_request(request, MyModel)
    await check_grecaptcha(m, request)
    return json_response(v_squared=m.v ** 2)


class OrganisationBread(Bread):
    class Model(BaseModel):
        name: str
        slug: constr(max_length=10)

    browse_limit_value = 5
    browse_enabled = True
    retrieve_enabled = True
    add_enabled = True
    edit_enabled = True
    delete_enabled = True

    table = 'organisations'
    browse_order_by_fields = ('slug',)


class TestExecView(ExecView):
    class Model(BaseModel):
        pow: int

    async def execute(self, m: Model):
        v = await self.conn.fetchval('SELECT 2 ^ $1', m.pow)
        return {'ans': v}


async def create_app(settings):
    routes = [
        web.get('/', handle),
        web.get('/user', handle_user),
        web.get('/errors/{do}', handle_errors),
        web.post('/exec/', TestExecView.view()),
        web.get('/encrypt/', encrypt),
        web.get('/decrypt/', decrypt),
        web.post('/grecaptcha/', grecaptcha),
        *OrganisationBread.routes('/orgs/'),
    ]
    return await create_default_app(settings=settings, routes=routes)
