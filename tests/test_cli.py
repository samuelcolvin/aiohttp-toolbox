import os

from aiohttptools.cli import main as cli_main


def test_reset_database(mocker):
    os.environ['ATOOLS_SETTINGS'] = 'demo.settings.Settings'
    os.environ['APP_CREATE_APP'] = 'demo.main.create_app'
    f = mocker.patch('aiohttptools.cli.reset_database')
    assert 0 == cli_main('_', 'reset_database')
    assert f.called
