#!/usr/bin/env python3.6
import asyncio
import locale
import logging
import os
import sys
from pathlib import Path
from typing import Callable, List

import uvloop
from aiohttp.web import Application, run_app
from pydantic.utils import import_string

from .logs import ColouredAccessLogger, setup_logging
from .network import check_server, wait_for_services
from .settings import BaseSettings

logger = logging.getLogger('atoolbox.cli')
commands = {}


def command(func: Callable):
    commands[func.__name__] = func
    return func


@command
def web(args: List[str], settings: BaseSettings):
    logger.info('running web server at %s...', settings.port)
    create_app: Callable[[BaseSettings], Application] = import_string(settings.create_app)
    wait_for_services(settings)
    app = create_app(settings=settings)
    kwargs = dict(port=settings.port, shutdown_timeout=8, print=lambda *args: None)  # pragma: no branch
    if '--access-log' in args:
        kwargs.update(access_log_class=ColouredAccessLogger, access_log=logging.getLogger('atoolbox.access'))
    else:
        kwargs['access_log'] = None
    run_app(app, **kwargs)


@command
def worker(args: List[str], settings: BaseSettings):
    if settings.worker_func:
        logger.info('running worker...')
        worker_func: Callable[[BaseSettings], None] = import_string(settings.worker_func)
        wait_for_services(settings)
        worker_func(settings=settings)
    else:
        raise CliError("settings.worker_path not set, can't run the worker")


@command
def patch(args: List[str], settings: BaseSettings):
    logger.info('running patch...')
    live = '--live' in args
    if live:
        args.remove('--live')
    from .db.patch import run_patch

    wait_for_services(settings)
    return run_patch(settings, live, args[0] if args else None) or 0


@command
def reset_database(args: List[str], settings: BaseSettings):
    logger.info('running reset_database...')
    from .db import reset_database

    wait_for_services(settings)
    reset_database(settings)


@command
def flush_redis(args: List[str], settings: BaseSettings):
    from .db.redis import flush_redis

    flush_redis(settings)


@command
def check_web(args: List[str], settings: BaseSettings):
    url = exp_status = None
    if args:
        url = args[0]
        if len(args) == 2:
            exp_status = int(args[1])

    url = url or os.getenv('ATOOLBOX_CHECK_URL') or f'http://localhost:{settings.port}/'
    exp_status = exp_status or int(os.getenv('ATOOLBOX_CHECK_STATUS') or 200)
    logger.info('checking server is running at "%s" expecting %d...', url, exp_status)
    return check_server(url, exp_status)


class CliError(RuntimeError):
    pass


def main(*args) -> int:
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging_client = setup_logging()
    sys.path.append(os.getcwd())
    try:
        root_dir = Path(os.getenv('ATOOLBOX_ROOT_DIR', '.')).resolve()
        sys.path.append(str(root_dir))
        os.chdir(str(root_dir))
        settings_str = os.getenv('ATOOLBOX_SETTINGS', 'settings.Settings')
        try:
            Settings = import_string(settings_str)
        except (ModuleNotFoundError, ImportError) as exc:
            raise CliError(f'unable to import "{settings_str}", {exc.__class__.__name__}: {exc}')

        if not isinstance(Settings, type) or not issubclass(Settings, BaseSettings):
            raise CliError(f'settings "{Settings}" (from "{settings_str}"), is not a valid Settings class')

        settings = Settings()
        locale.setlocale(locale.LC_ALL, settings.locale)
        try:
            _, command_name, *args = args
        except ValueError:
            raise CliError('no command provided, options are: {}'.format(', '.join(commands)))

        try:
            func = commands[command_name]
        except KeyError:
            raise CliError('unknown command "{}", options are: {}'.format(command_name, ', '.join(commands)))
        else:
            return func(args, settings) or 0
    except CliError as exc:
        logger.error('%s', exc)
        return 1
    finally:
        loop = asyncio.get_event_loop()
        if logging_client and not loop.is_closed():
            transport = logging_client.remote.get_transport()
            transport and loop.run_until_complete(transport.close())


def cli():  # pragma: no cover
    sys.exit(main(*sys.argv))


if __name__ == '__main__':  # pragma: no cover
    cli()
