#!/usr/bin/env python3
import asyncio
import locale
import logging
import os
import sys
from argparse import ArgumentParser
from importlib import import_module
from pathlib import Path
from typing import Callable, Dict, Optional

import uvloop
from aiohttp.web import Application, run_app
from pydantic import BaseSettings as PydanticBaseSettings
from pydantic.utils import import_string

from .logs import ColouredAccessLogger, setup_logging
from .network import check_server, wait_for_services
from .settings import BaseSettings
from .version import VERSION

logger = logging.getLogger('atoolbox.cli')
commands: Dict[str, Optional[Callable]] = {'auto': None}


def command(func: Callable):
    commands[func.__name__] = func
    return func


@command
def web(args, settings: BaseSettings):
    logger.info('running web server at %s...', settings.port)
    create_app: Callable[[BaseSettings], Application] = import_string(settings.create_app)
    wait_for_services(settings)
    app = create_app(settings=settings)
    kwargs = dict(port=settings.port, shutdown_timeout=8, print=lambda *args: None)  # pragma: no branch
    if args.access_log:
        kwargs.update(access_log_class=ColouredAccessLogger, access_log=logging.getLogger('atoolbox.access'))
    else:
        kwargs['access_log'] = None
    run_app(app, **kwargs)


@command
def worker(args, settings: BaseSettings):
    if settings.worker_func:
        logger.info('running worker...')
        worker_func: Callable[[BaseSettings], None] = import_string(settings.worker_func)
        wait_for_services(settings)
        worker_func(settings=settings)
    else:
        raise CliError("settings.worker_func not set, can't run the worker")


@command
def patch(args, settings: BaseSettings):
    logger.info('running patch...')
    from .patch_methods import run_patch

    wait_for_services(settings)
    args.patches_path and import_module(args.patches_path)
    if args.extra:
        patch_name = args.extra[0]
        extra_args = args.extra[1:]
    else:
        patch_name = None
        extra_args = ()
    return run_patch(settings, patch_name, args.live, extra_args)


@command
def reset_database(args, settings: BaseSettings):
    logger.info('running reset_database...')
    from .db import reset_database

    wait_for_services(settings)
    reset_database(settings)


@command
def flush_redis(args, settings: BaseSettings):
    from .db.redis import flush_redis

    flush_redis(settings)


@command
def check_web(args, settings: BaseSettings):
    url = exp_status = None
    if args.extra:
        url = args.extra[0]
        if len(args.extra) == 2:
            exp_status = int(args.extra[1])

    url = url or os.getenv('ATOOLBOX_CHECK_URL') or f'http://localhost:{settings.port}/'
    exp_status = exp_status or int(os.getenv('ATOOLBOX_CHECK_STATUS') or 200)
    logger.info('checking server is running at "%s" expecting %d...', url, exp_status)
    return check_server(url, exp_status)


@command
def shell(args, settings: BaseSettings):
    """
    Run an interactive python shell
    """
    from IPython import start_ipython
    from IPython.terminal.ipapp import load_default_config

    c = load_default_config()

    settings_path, settings_name = args.settings_path.rsplit('.', 1)
    exec_lines = [
        'import asyncio, base64, math, hashlib, json, os, pickle, re, secrets, sys, time',
        'from datetime import datetime, date, timedelta, timezone',
        'from pathlib import Path',
        'from pprint import pprint as pp',
        '',
        f'root_dir = "{args.root}"',
        'sys.path.append(root_dir)',
        'os.chdir(root_dir)',
        '',
        f'from {settings_path} import {settings_name}',
        'settings = Settings()',
    ]
    exec_lines += ['print("\\n    Python {v.major}.{v.minor}.{v.micro}\\n".format(v=sys.version_info))'] + [
        f"print('    {l}')" for l in exec_lines
    ]

    c.TerminalIPythonApp.display_banner = False
    c.TerminalInteractiveShell.confirm_exit = False
    c.InteractiveShellApp.exec_lines = exec_lines

    start_ipython(argv=(), config=c)


class CliError(RuntimeError):
    pass


def get_auto_command():
    command_env = os.getenv('ATOOLBOX_COMMAND')
    port_env = os.getenv('PORT')
    dyno_env = os.getenv('DYNO')
    if command_env:
        logger.info('using environment variable ATOOLBOX_COMMAND=%r to infer command', command_env)
        command_env = command_env.lower()
        if command_env != 'auto' and command_env in commands:
            return commands[command_env]
        else:
            raise CliError(f'Invalid value for ATOOLBOX_COMMAND: {command_env!r}')
    elif dyno_env:
        logger.info('using environment variable DYNO=%r to infer command', dyno_env)
        return web if dyno_env.lower().startswith('web') else worker
    elif port_env and port_env.isdigit():
        logger.info('using environment variable PORT=%s to infer command as web', port_env)
        return web
    else:
        logger.info('no environment variable found to infer command, assuming worker')
        return worker


def main(*args) -> int:
    parser = ArgumentParser(description=f'aiohttp-toolbox command line interface v{VERSION}')
    parser.add_argument(
        'command',
        type=str,
        choices=list(commands.keys()),
        help=(
            'The command to run, use "auto" to infer the command from environment variables, '
            'ATOOLBOX_COMMAND or DYNO (heroku) or PORT.'
        ),
    )
    parser.add_argument(
        '-r',
        '--root',
        dest='root',
        default=os.getenv('ATOOLBOX_ROOT_DIR', '.'),
        help=(
            'root directory to run the command from, defaults to to the environment variable '
            '"ATOOLBOX_ROOT_DIR" or "."'
        ),
    )
    parser.add_argument(
        '-s',
        '--settings-path',
        dest='settings_path',
        default=os.getenv('ATOOLBOX_SETTINGS', 'settings.Settings'),
        help=(
            'settings path (dotted, relative to the root directory), defaults to to the environment variable '
            '"ATOOLBOX_SETTINGS" or "settings.Settings"'
        ),
    )
    parser.add_argument('--verbose', action='store_true', help='whether to print debug logs')
    parser.add_argument(
        '--log',
        default=os.getenv('ATOOLBOX_LOG_NAME', 'app'),
        help='Root name of logs for the app, defaults to to the environment variable "ATOOLBOX_LOG_NAME" or "app"',
    )
    parser.add_argument(
        '--live',
        action='store_true',
        help='whether to run patches as live, default false, only applies to the "patch" command.',
    )
    parser.add_argument(
        '--access-log',
        dest='access_log',
        action='store_true',
        help='whether run the access logger on web, default false, only applies to the "web" command.',
    )
    parser.add_argument(
        '--patches-path', help='patch to import before running patches, only applies to the "patch" command.'
    )
    parser.add_argument('extra', nargs='*', default=[], help='Extra arguments to pass to the command.')
    try:
        ns, extra = parser.parse_known_args(args)
    except SystemExit:
        return 1

    ns.extra.extend(extra)
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging_client = setup_logging(debug=ns.verbose, main_logger_name=ns.log)
    try:
        sys.path.append(os.getcwd())
        ns.root = Path(ns.root).resolve()
        sys.path.append(str(ns.root))
        os.chdir(str(ns.root))

        try:
            settings_cls = import_string(ns.settings_path)
        except (ModuleNotFoundError, ImportError) as exc:
            raise CliError(f'unable to import "{ns.settings_path}", {exc.__class__.__name__}: {exc}')

        if not isinstance(settings_cls, type) or not issubclass(settings_cls, PydanticBaseSettings):
            raise CliError(f'settings "{settings_cls}" (from "{ns.settings_path}"), is not a valid Settings class')

        settings = settings_cls()
        locale.setlocale(locale.LC_ALL, getattr(settings, 'locale', 'en_US.utf8'))

        func = commands[ns.command] or get_auto_command()
        return func(ns, settings) or 0
    except CliError as exc:
        logger.error('%s', exc)
        return 1
    finally:
        loop = asyncio.get_event_loop()
        if logging_client and not loop.is_closed():
            transport = logging_client.remote.get_transport()
            transport and loop.run_until_complete(transport.close())


def cli():  # pragma: no cover
    sys.exit(main(*sys.argv[1:]))


if __name__ == '__main__':  # pragma: no cover
    cli()
