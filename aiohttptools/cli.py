#!/usr/bin/env python3.6
import asyncio
import locale
import logging.config
import os
import sys
from typing import Callable

import uvloop
from aiohttp import web
from arq import RunWorkerProcess
from pydantic.utils import import_string

from .db import reset_database
from .db.patch import run_patch
from .logs import setup_logging
from .settings import BaseSettings

logger = logging.getLogger('atools.cli')
sys.path.append(os.getcwd())


class CliError(RuntimeError):
    pass


def main(*args):  # noqa: C901 (ignore complexity)
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging_client = setup_logging()
    try:
        settings_str = os.getenv('ATOOLS_SETTINGS', 'settings.Settings')
        Settings = import_string(settings_str)
        if not isinstance(Settings, type) or not issubclass(Settings, BaseSettings):
            raise CliError(f'settings "{Settings}" (from "{settings_str}"), is not a valid Settings class')

        settings = Settings()
        locale.setlocale(locale.LC_ALL, settings.locale)
        try:
            _, command, *args = args
        except ValueError:
            raise CliError('no command provided, options are: "reset_database", "patch", "worker" or "web"')

        if command == 'reset_database':
            logger.info('running reset_database...')
            reset_database(settings)
        elif command == 'patch':
            logger.info('running patch...')
            live = '--live' in args
            if live:
                args.remove('--live')
            return run_patch(settings, live, args[0] if args else None) or 0
        elif command == 'web':
            logger.info('running web server at %s...', settings.port)
            create_app: Callable = settings.create_app
            app = create_app(settings=settings)
            web.run_app(app, port=settings.port, shutdown_timeout=6, access_log=None, print=lambda *args: None)
        elif command == 'worker':
            if settings.worker_path:
                logger.info('running worker...')
                RunWorkerProcess(settings.worker_path, settings.worker_name)
            else:
                raise CliError("settings.worker_path not set, can't run the worker")
        else:
            raise CliError(f'unknown command "{command}"')
    except CliError as exc:
        logger.error('%s', exc)
        return 1
    finally:
        loop = asyncio.get_event_loop()
        if logging_client and not loop.is_closed():
            transport = logging_client.remote.get_transport()
            transport and loop.run_until_complete(transport.close())
    return 0


def cli():  # pragma: no cover
    sys.exit(main(*sys.argv) or 0)


if __name__ == '__main__':  # pragma: no cover
    cli()
