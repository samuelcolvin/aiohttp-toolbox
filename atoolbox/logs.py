import logging
import logging.config
import os
import sys
import traceback
from io import StringIO

try:
    import pygments
    from pygments.lexers import Python3TracebackLexer
    from pygments.formatters import Terminal256Formatter
except ImportError:  # pragma: no cover
    pyg_lexer = pyg_formatter = None
else:
    pyg_lexer, pyg_formatter = Python3TracebackLexer(), Terminal256Formatter(style='vim')

try:
    from devtools import pformat as format_extra
    from devtools.ansi import isatty
except ImportError:  # pragma: no cover
    from pprint import pformat

    def format_extra(extra, highlight):
        return pformat(extra)


# only way to get "extra" from a LogRecord is to look in record.__dict__ and ignore all the standard keys
standard_record_keys = {
    'name',
    'msg',
    'args',
    'levelname',
    'levelno',
    'pathname',
    'filename',
    'module',
    'exc_info',
    'exc_text',
    'stack_info',
    'lineno',
    'funcName',
    'created',
    'msecs',
    'relativeCreated',
    'thread',
    'threadName',
    'processName',
    'process',
    'message',
}


class WarningConsoleHandler(logging.StreamHandler):
    def setFormatter(self, fmt):
        self.formatter = fmt
        self.formatter.stream_is_tty = isatty and isatty(self.stream)


class WarningConsoleFormatter(logging.Formatter):
    def __init__(self, fmt=None, datefmt=None, style='%'):
        super().__init__(fmt, datefmt, style)
        self.stream_is_tty = False

    def formatMessage(self, record):
        s = super().formatMessage(record)
        extra = {k: v for k, v in record.__dict__.items() if k not in standard_record_keys}
        if extra:
            s += '\nExtra: ' + format_extra(extra, highlight=self.stream_is_tty)
        return s

    def formatException(self, ei):
        sio = StringIO()
        traceback.print_exception(*ei, file=sio)
        stack = sio.getvalue()
        sio.close()
        if self.stream_is_tty and pyg_lexer:
            return pygments.highlight(stack, lexer=pyg_lexer, formatter=pyg_formatter).rstrip('\n')
        else:
            return stack


class NotWarnings(logging.Filter):
    def filter(self, record):
        return record.levelno < logging.WARNING


def get_env_multiple(*names):
    for name in names:
        v = os.getenv(name, None) or os.getenv(name.lower(), None)
        if v:
            return v


def setup_logging(debug=None, disable_existing=False, main_logger_name=None):
    """
    setup logging config by updating the arq logging config
    """
    if debug is None:
        debug = '--verbose' in sys.argv
    log_level = 'DEBUG' if debug else 'INFO'
    sentry_dsn = os.getenv('SENTRY_DSN', None)
    if sentry_dsn in ('', '-'):
        # thus setting an environment variable of "-" means no sentry
        sentry_dsn = None

    client = None
    if sentry_dsn:
        from raven import Client
        from raven_aiohttp import AioHttpTransport

        client = Client(
            transport=AioHttpTransport,
            dsn=sentry_dsn,
            release=get_env_multiple('COMMIT', 'RELEASE'),
            name=get_env_multiple('DYNO', 'SERVER_NAME', 'HOSTNAME', 'HOST', 'NAME'),
        )
        warning_handler = {'level': 'WARNING', 'class': 'raven.handlers.logging.SentryHandler', 'client': client}
        default_filters = []
    else:
        warning_handler = {
            'level': 'WARNING',
            'class': 'atoolbox.logs.WarningConsoleHandler',
            'formatter': 'atoolbox.console_warnings',
        }
        # we don't print above warnings on atoolbox.default to avoid duplicate errors in the console
        default_filters = ['not_warnings']

    main_logger_name = main_logger_name or os.getenv('APP_LOGGER_NAME', 'app')
    config = {
        'version': 1,
        'disable_existing_loggers': disable_existing,
        'formatters': {
            'atoolbox.default': {'format': '%(levelname)-7s %(name)19s: %(message)s'},
            'atoolbox.console_warnings': {'class': 'atoolbox.logs.WarningConsoleFormatter'},
        },
        'filters': {'not_warnings': {'()': 'atoolbox.logs.NotWarnings'}},
        'handlers': {
            'atoolbox.default': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'atoolbox.default',
                'filters': default_filters,
            },
            'atoolbox.warning': warning_handler,
        },
        'loggers': {
            'atoolbox': {'handlers': ['atoolbox.default', 'atoolbox.warning'], 'level': log_level},
            main_logger_name: {'handlers': ['atoolbox.default', 'atoolbox.warning'], 'level': log_level},
            'arq': {'handlers': ['atoolbox.default', 'atoolbox.warning'], 'level': log_level},
        },
    }
    logging.config.dictConfig(config)
    return client
