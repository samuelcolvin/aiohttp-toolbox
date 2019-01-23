import logging

import pytest

from atoolbox.logs import ColouredAccessLogger
from conftest import pre_startup_app
from demo.main import create_app


@pytest.mark.parametrize(
    'method,status,in_log',
    [
        ('GET', 200, ']\x1b[0m GET /status/200/ 200'),
        ('GET', 500, ']\x1b[0m \x1b[31mGET'),
        ('GET', 400, ']\x1b[0m \x1b[33mGET'),
        ('GET', 304, ']\x1b[0m \x1b[2mGET'),
        ('POST', 200, ']\x1b[0m \x1b[32mPOST'),
    ],
)
async def test_log_msg(settings, db_conn, aiohttp_server, aiohttp_client, caplog, method, status, in_log):
    caplog.set_level(logging.INFO)
    app = await create_app(settings=settings)
    app['test_conn'] = db_conn
    app.on_startup.insert(0, pre_startup_app)
    server = await aiohttp_server(app, access_log_class=ColouredAccessLogger)
    cli = await aiohttp_client(server)

    headers = {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1', 'Referer': 'http://127.0.0.1'}
    r = await cli.request(method, f'/status/{status}/', headers=headers)
    assert r.status == status, await r.text()
    assert in_log in caplog.text


@pytest.mark.parametrize('size,output', [(10_000_000, '9.5MB'), (1024 ** 2, '1.0MB'), (10000, '9.8KB'), (10, '10B')])
def test_format_size(size, output):
    assert ColouredAccessLogger.format_size(size) == output
