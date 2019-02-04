import asyncio
import json
import os
from typing import List

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request
from pydantic import BaseModel, BaseSettings as PydanticBaseSettings

from atoolbox.create_app import cleanup, create_default_app, startup
from atoolbox.db.helpers import SimplePgPool, run_sql_section
from atoolbox.logs import setup_logging
from atoolbox.middleware import error_middleware
from atoolbox.test_utils import Offline, create_dummy_server, return_any_status
from atoolbox.utils import JsonErrors, get_ip, parse_request_query, raw_json_response, slugify


@pytest.mark.parametrize(
    'input,output', [('This is the input ', 'this-is-the-input'), ('in^put', 'input'), ('in_put', 'in_put')]
)
def test_slugify(input, output):
    assert slugify(input) == output


def test_get_ip():
    request = type('Request', (), {'headers': {'X-Forwarded-For': '1.2.3.4 ,5.6.7.8'}})
    assert get_ip(request) == '1.2.3.4'


async def test_encrypt_decrypt(cli):
    r = await cli.get('/encrypt/', data='{"foo": "bar"}')
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data.keys() == {'token'}

    r = await cli.get('/decrypt/', data=json.dumps({'token': data['token']}))
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'foo': 'bar'}


async def test_decrypt_invalid(cli):
    r = await cli.get('/decrypt/', data=json.dumps({'token': 'xxx'}))
    assert r.status == 400, await r.text()
    data = await r.json()
    assert data == {'message': 'invalid token'}


def test_logging_no_raven():
    os.environ['SENTRY_DSN'] = '-'
    assert setup_logging() is None


def test_logging_raven():
    os.environ['SENTRY_DSN'] = 'https://123:456@sentry.io/789'
    os.environ['RELEASE'] = 'testing'
    assert setup_logging() is not None


async def test_run_sql_section():
    sql_execute = None

    async def execute(sql):
        nonlocal sql_execute
        sql_execute = sql

    conn = type('Connection', (), {'execute': execute})
    sql = 'xxx\n-- { foobar\nthis is the sql to run\n-- } foobar\n'
    await run_sql_section('foobar', sql, conn)
    assert 'this is the sql to run' == sql_execute


async def test_run_sql_section_error():
    with pytest.raises(RuntimeError):
        await run_sql_section('foobar', 'xx', None)


async def test_simple_pool(db_conn):
    conn = SimplePgPool(db_conn)
    assert 625 == await conn.fetchval('SELECT 25 * 25')
    assert (625,) == await conn.fetchrow('SELECT 25 * 25')
    assert [(625,)] == await conn.fetch('SELECT 25 * 25')
    assert 'SELECT 1' == await conn.execute('SELECT 25 * 25')


@pytest.mark.parametrize(
    'input,output', [('{"foo": 42}', b'{"foo": 42}\n'), (b'{"foo": 42}', b'{"foo": 42}\n'), (None, b'null\n')]
)
async def test_raw_json_response(input, output):
    r = raw_json_response(input)
    assert r.body == output
    assert r.content_type == 'application/json'
    assert r.status == 200


async def test_raw_json_response_status():
    r = raw_json_response('null', status_=401)
    assert r.body == b'null\n'
    assert r.content_type == 'application/json'
    assert r.status == 401


async def test_raw_json_response_error():
    with pytest.raises(TypeError):
        raw_json_response(42)


class Model(BaseModel):
    x: int
    y: str
    z: List[int]


@pytest.mark.parametrize(
    'query,result',
    [
        ('/?x=123&y=foo%20bar&z=1&z=2', {'x': 123, 'y': 'foo bar', 'z': [1, 2]}),
        ('/?x=123&y=foo%20bar&z=1', {'x': 123, 'y': 'foo bar', 'z': [1]}),
    ],
)
def test_parse_request_query(query, result):
    m = parse_request_query(make_mocked_request('GET', query), Model)
    assert m.dict() == result


def test_parse_request_query_error():
    with pytest.raises(JsonErrors.HTTPBadRequest) as exc_info:
        parse_request_query(make_mocked_request('GET', '/?x=1&y=2'), Model)

    error = json.loads(exc_info.value.body.decode())
    assert error == {
        'message': 'Invalid Data',
        'details': [{'loc': ['z'], 'msg': 'field required', 'type': 'value_error.missing'}],
    }


async def awaitable():
    pass


async def test_create_app_no_settings(mocker):
    f = mocker.patch('atoolbox.db.prepare_database')
    app = await create_default_app()
    assert app['settings'] is None
    assert 'auth_fernet' not in app
    assert 'http_client' not in app
    assert len(app.middlewares) == 3

    await startup(app)
    assert 'http_client' not in app
    assert 'pg' not in app
    assert 'redis' not in app
    await cleanup(app)
    assert not f.called


async def test_create_app_custom_middleware():
    app = await create_default_app(middleware=(error_middleware,))
    assert len(app.middlewares) == 1


async def test_create_app_pg(mocker):
    f = mocker.patch('atoolbox.db.prepare_database', return_value=awaitable())

    class Settings(PydanticBaseSettings):
        pg_dsn: str = 'postgres://postgres@localhost:5432/atoolbox_test'
        create_http_client = True

    app = await create_default_app(settings=Settings())
    assert app['settings'] is not None
    assert 'http_client' not in app

    await startup(app)
    await cleanup(app)
    assert f.called
    assert 'http_client' in app


async def test_redis_settings_module():
    from atoolbox.settings import BaseSettings, RedisSettings

    assert RedisSettings.__module__ == 'arq.utils'

    s = BaseSettings()
    assert s.redis_settings is not None
    assert s.pg_dsn is not None
    assert s.auth_key is not None


def test_is_offline(mocker):
    ci_value = os.environ.pop('CI', None)
    try:
        fake_dns_resolver = mocker.patch('aiodns.DNSResolver.query')
        fake_dns_resolver.side_effect = asyncio.TimeoutError('timed out')
        offline = Offline()
        assert bool(offline) is True
        assert bool(offline) is True
        fake_dns_resolver.assert_called_once_with('google.com', 'A')
    finally:
        if ci_value:
            os.environ['CI'] = ci_value


def test_is_offline_ci(mocker):
    os.environ['CI'] = '1'
    try:
        fake_dns_resolver = mocker.patch('aiodns.DNSResolver.query')
        fake_dns_resolver.side_effect = asyncio.TimeoutError('timed out')
        offline = Offline()
        assert bool(offline) is False
        assert bool(offline) is False
        assert not fake_dns_resolver.called
    finally:
        os.environ.pop('CI')


def test_is_online(mocker):
    async def _query(*args):
        pass

    ci_value = os.environ.pop('CI', None)
    try:
        fake_dns_resolver = mocker.patch('aiodns.DNSResolver.query')
        fake_dns_resolver.side_effect = _query
        offline = Offline()
        assert bool(offline) is False
        assert bool(offline) is False
        fake_dns_resolver.assert_called_once_with('google.com', 'A')
    finally:
        if ci_value:
            os.environ['CI'] = ci_value


async def test_create_dummy_server(aiohttp_server):
    routes = [web.get('/extra-route/', return_any_status, name='extra-route')]  # just so we have something
    server = await create_dummy_server(aiohttp_server, extra_routes=routes, extra_context={'x': 42})
    assert list(server.app.router._named_resources) == ['any-status', 'grecaptcha-dummy', 'extra-route']
    assert server.app['x'] == 42
