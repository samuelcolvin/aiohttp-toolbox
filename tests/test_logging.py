import logging
import os

import pytest

from atoolbox.logs import ColouredAccessLogger, build_logging_config, setup_logging
from conftest import pre_startup_app
from demo.main import create_app


@pytest.fixture
def cli_access_logger(settings, db_conn, aiohttp_server, aiohttp_client, caplog):
    async def create_cli():
        caplog.set_level(logging.INFO)
        app = await create_app(settings=settings)
        app['test_conn'] = db_conn
        app.on_startup.insert(0, pre_startup_app)
        server = await aiohttp_server(app, access_log_class=ColouredAccessLogger)
        return await aiohttp_client(server)

    return create_cli


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
async def test_log_msg(cli_access_logger, caplog, method, status, in_log):
    cli = await cli_access_logger()
    headers = {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1', 'Referer': 'http://127.0.0.1'}
    r = await cli.request(method, f'/status/{status}/', headers=headers)
    assert r.status == status, await r.text()
    assert in_log in caplog.text


async def test_log_msg_no_colour(cli_access_logger, caplog, mocker):
    cli = await cli_access_logger()
    mocker.patch('atoolbox.logs.sformat', new=None)
    r = await cli.get('/status/524/')
    assert r.status == 524, await r.text()
    assert '] GET /status/524/ 524' in caplog.text


async def test_log_msg_exception(cli_access_logger, caplog, mocker):
    mocker.patch('atoolbox.logs.isatty', return_value=True)
    setup_logging()
    cli = await cli_access_logger()
    r = await cli.get('/errors/value_error')
    assert r.status == 500, await r.text()
    assert '\x1b[38;5;26mTraceback' in caplog.text


@pytest.mark.parametrize('size,output', [(10_000_000, '9.5MB'), (1024 ** 2, '1.0MB'), (10000, '9.8KB'), (10, '10B')])
def test_format_size(size, output):
    assert ColouredAccessLogger.format_size(size) == output


def test_build_logging_config():
    config, client = build_logging_config(True)
    assert client is None
    assert config['disable_existing_loggers'] is False
    assert config['handlers']['atoolbox.default']['level'] == 'DEBUG'
    assert config['handlers']['atoolbox.warning']['class'] == 'atoolbox.logs.HighlightStreamHandler'
    assert 'app' in config['loggers']
    assert 'foobar' not in config['loggers']


def test_build_logging_config_sentry():
    os.environ['SENTRY_DSN'] = 'https://thekey@sentry.io/123456789'
    try:
        config, client = build_logging_config(False, True, 'foobar')
        assert client is not None
        assert config['disable_existing_loggers'] is True
        assert config['handlers']['atoolbox.default']['level'] == 'INFO'
        assert config['handlers']['atoolbox.warning']['class'] == 'raven.handlers.logging.SentryHandler'

        assert 'foobar' in config['loggers']
        assert 'app' not in config['loggers']
    finally:
        os.environ.pop('SENTRY_DSN')
