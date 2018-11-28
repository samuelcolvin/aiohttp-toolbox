import asyncio
import os

import pytest
from aiohttp.web_app import Application

from atoolbox.cli import main as cli_main


@pytest.fixture(name='env')
def env_fixture():
    os.environ['ATOOLBOX_SETTINGS'] = 'demo.settings.Settings'
    os.environ['APP_CREATE_APP'] = 'demo.main.create_app'
    os.environ['APP_SQL_PATH'] = 'tests/demo/models.sql'
    os.environ['DATABASE_URL'] = 'postgres://postgres@localhost:5432/atoolbox_test'


def test_reset_database(mocker, env):
    f = mocker.patch('atoolbox.cli.reset_database')
    assert 0 == cli_main('_', 'reset_database')
    assert f.called


def mock_run_app(create_app, **kwargs):
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(create_app)
    assert isinstance(app, Application)


def test_web(mocker, env):
    f = mocker.patch('atoolbox.cli.web.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('_', 'web')
    assert f.called


def test_args_error(caplog, env):
    assert 1 == cli_main()
    assert 'no command provided, options are' in caplog.text


def test_settings_import_error(caplog, env, mocker):
    os.environ['ATOOLBOX_SETTINGS'] = 'wrong'
    f = mocker.patch('atoolbox.cli.reset_database')
    assert 1 == cli_main('_', 'reset_database')
    assert f.called is False
    assert 'unable to import "wrong", ' in caplog.text


def test_not_settings(caplog, env):
    os.environ['ATOOLBOX_SETTINGS'] = 'math.cos'
    assert 1 == cli_main('_', 'x')
    assert '(from "math.cos"), is not a valid Settings class' in caplog.text


def test_invalid_command(caplog, env):
    assert 1 == cli_main('_', 'x')
    assert 'unknown command "x"' in caplog.text


def test_worker(env, tmpworkdir):
    code = 'def bar(*args, **kwargs):\n  with open("sentinal.txt", "w") as f:\n    f.write("executed")\n'
    tmpworkdir.join('foo.py').write_text(code, 'utf8')
    os.environ['APP_WORKER_FUNC'] = 'foo.bar'
    assert 0 == cli_main('_', 'worker')
    assert tmpworkdir.join('sentinal.txt').read_text('utf8') == 'executed'


def test_no_worker(caplog, env):
    del os.environ['APP_WORKER_FUNC']
    assert 1 == cli_main('_', 'worker')
    assert "settings.worker_path not set, can't run the worker" in caplog.text


def test_list_patches(caplog, env):
    assert 0 == cli_main('_', 'patch')
    assert '  rerun_sql: rerun the contents of settings.sql_path' in caplog.text


def test_patch_not_live(caplog, env, db_conn):
    assert 0 == cli_main('_', 'patch', 'rerun_sql')
    assert 'running patch rerun_sql live False' in caplog.text
    assert 'not live, rolling back' in caplog.text


def test_patch_live(caplog, env, db_conn):
    assert 0 == cli_main('_', 'patch', 'rerun_sql', '--live')
    assert 'running patch rerun_sql live True' in caplog.text
    assert 'live, committed patch' in caplog.text


def test_patch_error(caplog, env, db_conn):
    assert 1 == cli_main('_', 'patch', 'error_patch', '--live')
    assert 'RuntimeError: xx' in caplog.text


def test_patch_direct_not_live(caplog, env, db_conn):
    assert 1 == cli_main('_', 'patch', 'direct_path')
    assert 'direct patches must be called with' in caplog.text


def test_patch_direct_live(caplog, env, db_conn):
    assert 0 == cli_main('_', 'patch', 'direct_path', '--live')
    assert 'running patch direct_path direct' in caplog.text


def test_patch_not_found(caplog, env, db_conn):
    assert 1 == cli_main('_', 'patch', 'xxx')
    assert 'patch "xxx" not found in patches: [\'rerun_sql\', \'error_patch\', \'direct_path\']' in caplog.text
