#!/usr/bin/env python3.6
import asyncio
import locale
import logging.config
import sys
from typing import Callable

import uvloop
from aiohttp import web
from arq import RunWorkerProcess

from .db import reset_database
from .db.patch import run_patch
from .logs import setup_logging
from .settings import Settings

logger = logging.getLogger('atools.cli')


def main():
    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    logging_client = setup_logging()
    try:
        settings = Settings()
        locale.setlocale(locale.LC_ALL, settings.locale)
        try:
            _, command, *args = sys.argv
        except ValueError:
            logger.error('no command provided, options are: "reset_database", "patch", "worker" or "web"')
            return 1

        if command == 'reset_database':
            logger.info('running reset_database...')
            reset_database(settings)
        elif command == 'patch':
            logger.info('running patch...')
            live = '--live' in args
            if live:
                args.remove('--live')
            return run_patch(settings, live, args[0] if args else None)
        elif command == 'web':
            logger.info('running web server...')
            create_app: Callable = settings.create_app
            app = create_app(settings=settings)
            web.run_app(app, port=settings.port, shutdown_timeout=6, access_log=None, print=lambda *args: None)
        elif command == 'worker':
            if settings.worker_path:
                logger.info('running worker...')
                RunWorkerProcess(settings.worker_path, settings.worker_name)
            else:
                logger.error("settings.worker_path not set, can't run the worker")
                return 1
        else:
            logger.error(f'unknown command "%s"', command)
            return 1
    finally:
        loop = asyncio.get_event_loop()
        if logging_client and not loop.is_closed():
            transport = logging_client.remote.get_transport()
            transport and loop.run_until_complete(transport.close())


def cli():
    sys.exit(main() or 0)


if __name__ == '__main__':
    cli()
