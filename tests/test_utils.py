import json
import os

import pytest

from atoolbox.db.helpers import SimplePgPool, run_sql_section
from atoolbox.logs import setup_logging
from atoolbox.utils import get_ip, slugify


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


def test_loggin_no_raven():
    os.environ['RAVEN_DSN'] = '-'
    assert setup_logging() is None


def test_loggin_raven():
    os.environ['RAVEN_DSN'] = 'https://123:456@sentry.io/789'
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
