import logging
import logging.config
import os
import traceback
from datetime import datetime, timedelta
from io import StringIO

from aiohttp.abc import AbstractAccessLogger
from aiohttp.hdrs import METH_POST

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
    from devtools.ansi import isatty, sformat
except ImportError:  # pragma: no cover
    from pprint import pformat

    isatty = False
    sformat = None

    def format_extra(extra, highlight):
        return pformat(extra)


MB = 1024 ** 2
KB = 1024


class ColouredAccessLogger(AbstractAccessLogger):
    def log(self, request, response, time):
        msg = '{method} {path} {code} {size} {ms:0.0f}ms'.format(
            method=request.method,
            path=request.path,
            code=response.status,
            size=self.format_size(response.body_length),
            ms=time * 1000,
        )
        time_str = (datetime.now() - timedelta(seconds=time)).strftime('[%H:%M:%S]')
        if sformat:
            time_str = sformat(time_str, sformat.magenta)

            if response.status >= 500:
                msg = sformat(msg, sformat.red)
            elif response.status >= 400:
                msg = sformat(msg, sformat.yellow)
            elif response.status == 304:
                msg = sformat(msg, sformat.dim)
            elif request.method == METH_POST:
                msg = sformat(msg, sformat.green)

        self.logger.info(time_str + ' ' + msg)

    @staticmethod
    def format_size(num):
        if num >= MB:
            return '{:0.1f}MB'.format(num / MB)
        elif num >= KB:
            return '{:0.1f}KB'.format(num / KB)
        else:
            return '{:0.0f}B'.format(num)


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


class HighlightStreamHandler(logging.StreamHandler):
    def setFormatter(self, fmt):
        self.formatter = fmt
        self.formatter.stream_is_tty = isatty and isatty(self.stream)


class HighlightExtraFormatter(logging.Formatter):
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


def build_logging_config(debug, disable_existing, main_logger_name):
    """
    setup logging config by updating the arq logging config
    """
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
            'class': 'atoolbox.logs.HighlightStreamHandler',
            'formatter': 'atoolbox.highlighted_formatter',
        }
        # we don't print above warnings on atoolbox.default to avoid duplicate errors in the console
        default_filters = ['not_warnings']

    config = {
        'version': 1,
        'disable_existing_loggers': disable_existing,
        'formatters': {
            'atoolbox.simple_formatter': {'format': '%(message)s'},
            'atoolbox.default_formatter': {'format': '%(levelname)-7s %(name)19s: %(message)s'},
            'atoolbox.highlighted_formatter': {'class': 'atoolbox.logs.HighlightExtraFormatter'},
        },
        'filters': {'not_warnings': {'()': 'atoolbox.logs.NotWarnings'}},
        'handlers': {
            'atoolbox.simple': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'atoolbox.simple_formatter',
            },
            'atoolbox.default': {
                'level': log_level,
                'class': 'logging.StreamHandler',
                'formatter': 'atoolbox.default_formatter',
                'filters': default_filters,
            },
            'atoolbox.warning': warning_handler,
        },
        'loggers': {
            'atoolbox': {'handlers': ['atoolbox.default', 'atoolbox.warning'], 'level': log_level},
            'atoolbox.access': {'handlers': ['atoolbox.simple'], 'level': log_level, 'propagate': False},
            main_logger_name: {'handlers': ['atoolbox.default', 'atoolbox.warning'], 'level': log_level},
            'arq': {'handlers': ['atoolbox.default', 'atoolbox.warning'], 'level': log_level},
        },
    }
    return config, client


def setup_logging(debug=False, disable_existing=False, main_logger_name='app'):
    config, client = build_logging_config(debug, disable_existing, main_logger_name)
    logging.config.dictConfig(config)
    return client
