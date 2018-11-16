import logging
import logging.config
import os
import sys


def get_env_mulitple(*names):
    for name in names:
        v = os.getenv(name, None) or os.getenv(name.lower(), None)
        if v:
            return v


def setup_logging(disable_existing=False):
    """
    setup logging config by updating the arq logging config
    """
    verbose = '--verbose' in sys.argv
    log_level = 'DEBUG' if verbose else 'INFO'
    raven_dsn = os.getenv('RAVEN_DSN', None)
    if raven_dsn in ('', '-'):
        # thus setting an environment variable of "-" means no raven
        raven_dsn = None

    client = None
    if raven_dsn:
        from raven import Client
        from raven_aiohttp import AioHttpTransport

        client = Client(
            transport=AioHttpTransport,
            dsn=raven_dsn,
            release=get_env_mulitple('COMMIT', 'RELEASE'),
            name=get_env_mulitple('DYNO', 'SERVER_NAME', 'HOSTNAME', 'HOST', 'NAME'),
        )
    config = {
        'version': 1,
        'disable_existing_loggers': disable_existing,
        'formatters': {'atools.default': {'format': '%(levelname)-7s %(name)16s: %(message)s'}},
        'handlers': {
            'atools.default': {'level': log_level, 'class': 'logging.StreamHandler', 'formatter': 'atools.default'},
            'sentry': {'level': 'WARNING', 'class': 'raven.handlers.logging.SentryHandler', 'client': client}
            if client
            else {'level': 'WARNING', 'class': 'logging.NullHandler'},
        },
        'loggers': {
            'atools': {'handlers': ['atools.default', 'sentry'], 'level': log_level},
            os.getenv('APP_LOGGER_NAME', 'app'): {'handlers': ['atools.default', 'sentry'], 'level': log_level},
            'arq': {'handlers': ['atools.default', 'sentry'], 'level': log_level},
        },
    }
    logging.config.dictConfig(config)
    return client
