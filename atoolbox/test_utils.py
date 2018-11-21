from typing import List, NamedTuple

from aiohttp import web
from aiohttp.test_utils import TestServer
from aiohttp.web import Application
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response, json_response


async def return_200(request):
    return Response()


async def grecaptcha(request):
    data = await request.post()
    request.app['log'][-1] = 'grecaptcha {response}'.format(**data)
    if data['response'] == '__ok__':
        return json_response(dict(success=True, hostname='127.0.0.1'))
    elif data['response'] == '__400__':
        return json_response({}, status=400)
    else:
        return json_response(dict(success=False, hostname='127.0.0.1'))


@middleware
async def log_middleware(request, handler):
    request.app['log'].append(request.method + ' ' + request.path.strip('/'))
    return await handler(request)


def create_dummy_app() -> Application:
    app = web.Application(middlewares=(log_middleware,))
    app.add_routes([web.route('*', '/200/', return_200), web.post('/grecaptcha_url/', grecaptcha)])
    app['log'] = []
    return app


class DummyServer(NamedTuple):
    server: TestServer
    app: Application
    log: List
    server_name: str


async def create_dummy_server(create_server, *, extra_routes=None, extra_context=None) -> DummyServer:
    app = create_dummy_app()
    if extra_routes:
        app.add_routes(extra_routes)
    if extra_context:
        app.update(extra_context)
    server = await create_server(app)
    return DummyServer(server, app, app['log'], f'http://localhost:{server.port}')
