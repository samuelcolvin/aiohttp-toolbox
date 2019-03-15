import asyncio
import os

import pytest
from aiohttp.web_app import Application

from atoolbox.cli import main as cli_main


@pytest.fixture(name='env')
def env_fixture():
    os.environ.pop('ATOOLBOX_ROOT_DIR', None)
    os.environ['ATOOLBOX_SETTINGS'] = 'demo.settings.Settings'
    os.environ['APP_CREATE_APP'] = 'demo.main.create_app'
    os.environ['APP_SQL_PATH'] = 'tests/demo/models.sql'
    os.environ['DATABASE_URL'] = 'postgres://postgres@localhost:5432/atoolbox_test'


def test_reset_database(mocker, env):
    f = mocker.patch('atoolbox.db.reset_database')
    assert 0 == cli_main('reset_database')
    assert f.called


def mock_run_app(create_app, **kwargs):
    loop = asyncio.get_event_loop()
    app = loop.run_until_complete(create_app)
    assert isinstance(app, Application)


def test_web(mocker, env):
    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('web')
    f.assert_called_once()
    assert f.call_args[1].keys() == {'port', 'shutdown_timeout', 'print', 'access_log'}


def test_web_logger(mocker, env):
    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('web', '--access-log')
    f.assert_called_once()
    assert f.call_args[1].keys() == {'port', 'shutdown_timeout', 'print', 'access_log', 'access_log_class'}


def test_args_error(capsys, env):
    assert 1 == cli_main()
    assert 'error: the following arguments are required: command' in capsys.readouterr().err


def test_settings_import_error(caplog, env, mocker):
    os.environ['ATOOLBOX_SETTINGS'] = 'wrong'
    f = mocker.patch('atoolbox.db.reset_database')
    assert 1 == cli_main('reset_database')
    assert f.called is False
    assert 'unable to import "wrong", ' in caplog.text


def test_not_settings(caplog, env):
    os.environ['ATOOLBOX_SETTINGS'] = 'math.cos'
    assert 1 == cli_main('web')
    assert '(from "math.cos"), is not a valid Settings class' in caplog.text


def test_invalid_command(capsys, env):
    assert 1 == cli_main('x')
    assert "argument command: invalid choice: 'x'" in capsys.readouterr().err


def test_worker(env, tmp_work_path):
    code = 'def bar(*args, **kwargs):\n  with open("sentinal.txt", "w") as f:\n    f.write("executed")\n'
    (tmp_work_path / 'foo.py').write_text(code)
    os.environ['APP_WORKER_FUNC'] = 'foo.bar'
    assert 0 == cli_main('worker')
    assert (tmp_work_path / 'sentinal.txt').read_text() == 'executed'


def test_no_worker(caplog, env):
    del os.environ['APP_WORKER_FUNC']
    assert 1 == cli_main('worker')
    assert "settings.worker_func not set, can't run the worker" in caplog.text


def test_list_patches(caplog, env):
    assert 0 == cli_main('patch')
    assert '  rerun_sql: rerun the contents of settings.sql_path' in caplog.text


def test_patch_not_live(caplog, env, db_conn):
    assert 0 == cli_main('patch', 'rerun_sql')
    assert 'running patch rerun_sql live False' in caplog.text
    assert 'not live, rolling back' in caplog.text


def test_patch_live(caplog, env, db_conn):
    assert 0 == cli_main('patch', 'rerun_sql', '--live')
    assert 'running patch rerun_sql live True' in caplog.text
    assert 'live, committed patch' in caplog.text


def test_patch_error(caplog, env, db_conn):
    assert 1 == cli_main('patch', 'error_patch', '--live')
    assert 'RuntimeError: xx' in caplog.text


def test_patch_direct_not_live(caplog, env, db_conn):
    assert 1 == cli_main('patch', 'direct_path')
    assert 'direct patches must be called with' in caplog.text


def test_patch_direct_live(caplog, env, db_conn):
    assert 0 == cli_main('patch', 'direct_path', '--live')
    assert 'running patch direct_path direct' in caplog.text
    assert 'result' not in caplog.text


def test_patch_func_returns(caplog, env, db_conn):
    assert 0 == cli_main('patch', 'non_coro', 'foo', 'bar', 'spam')
    assert 'running patch non_coro live False' in caplog.text
    assert 'result: 3' in caplog.text


def test_patch_not_found(caplog, env, db_conn):
    assert 1 == cli_main('patch', 'xxx')
    assert (
        'patch "xxx" not found in patches: [\'rerun_sql\', \'error_patch\', \'direct_path\', \'non_coro\']'
        in caplog.text
    )


def test_flush_redis(env):
    assert 0 == cli_main('flush_redis')


def test_check_server(caplog, env):
    assert 1 == cli_main('check_web', 'http://localhost:666/', '234')
    assert 'checking server is running at "http://localhost:666/" expecting 234...' in caplog.text
    assert 'ClientConnectorError: Cannot connect to host localhost:666' in caplog.text


def test_check_server_url_only(caplog, env):
    assert 1 == cli_main('check_web', 'http://localhost:666/')
    assert 'checking server is running at "http://localhost:666/" expecting 200...' in caplog.text


def test_check_server_default_args(caplog, env):
    assert 1 == cli_main('check_web')
    assert 'checking server is running at "http://localhost:8000/" expecting 200...' in caplog.text


def test_auto_web(mocker, env):
    os.environ['ATOOLBOX_COMMAND'] = 'web'
    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('auto')
    f.assert_called_once()


def test_auto_worker(mocker, env, tmp_work_path):
    os.environ['ATOOLBOX_COMMAND'] = 'worker'
    f = mocker.patch('atoolbox.cli.run_app')
    code = 'def bar(*args, **kwargs):\n  with open("sentinal.txt", "w") as f:\n    f.write("executed")\n'
    (tmp_work_path / 'foo.py').write_text(code)
    os.environ['APP_WORKER_FUNC'] = 'foo.bar'
    assert not (tmp_work_path / 'sentinal.txt').exists()

    assert 0 == cli_main('auto')
    assert (tmp_work_path / 'sentinal.txt').exists()
    assert not f.called


def test_auto_invalid(mocker, env, caplog):
    os.environ['ATOOLBOX_COMMAND'] = 'foobar'
    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 1 == cli_main('auto')
    assert not f.called
    assert "Invalid value for ATOOLBOX_COMMAND: 'foobar'" in caplog.text


def test_auto_web_dyno(mocker, env):
    os.environ.pop('ATOOLBOX_COMMAND', None)
    os.environ['DYNO'] = 'web.1'
    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('auto')
    f.assert_called_once()


def test_auto_web_port(mocker, env, caplog):
    os.environ.pop('ATOOLBOX_COMMAND', None)
    os.environ.pop('DYNO', None)
    os.environ['PORT'] = '123'
    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('auto')
    f.assert_called_once()
    assert "using environment variable PORT=123 to infer command as web" in caplog.text


def test_auto_worker_nothing_set(mocker, env, caplog, tmp_work_path):
    os.environ.pop('ATOOLBOX_COMMAND', None)
    os.environ.pop('DYNO', None)
    os.environ.pop('PORT', None)

    code = 'def bar(*args, **kwargs):\n  with open("sentinal.txt", "w") as f:\n    f.write("executed")\n'
    (tmp_work_path / 'foo.py').write_text(code)
    os.environ['APP_WORKER_FUNC'] = 'foo.bar'

    f = mocker.patch('atoolbox.cli.run_app')
    f.side_effect = mock_run_app
    assert 0 == cli_main('auto')
    assert not f.called
    assert (tmp_work_path / 'sentinal.txt').read_text() == 'executed'
    assert 'no environment variable found to infer command, assuming worker' in caplog.text
