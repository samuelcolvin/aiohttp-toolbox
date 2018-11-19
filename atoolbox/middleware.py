import contextlib
import logging
from time import time

from aiohttp.hdrs import METH_GET, METH_OPTIONS, METH_POST
from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response

from .json_tools import lenient_json
from .settings import BaseSettings
from .utils import HEADER_CROSS_ORIGIN, JSON_CONTENT_TYPE, JsonErrors, get_ip, request_root

logger = logging.getLogger('atoolbox.middleware')


def exc_extra(exc):
    exception_extra = getattr(exc, 'extra', None)
    if exception_extra:
        try:
            v = exception_extra()
        except Exception:
            pass
        else:
            return lenient_json(v)


async def log_extra(request, response=None, **more):
    request_text = response_text = None
    with contextlib.suppress(Exception):  # UnicodeDecodeError or HTTPRequestEntityTooLarge maybe other things too
        request_text = await request.text()
    with contextlib.suppress(Exception):  # UnicodeDecodeError
        response_text = lenient_json(getattr(response, 'text', None))
    start = request.get('start_time') or time()
    data = dict(
        request_duration=f'{(time() - start) * 1000:0.2f}ms',
        request=dict(
            url=str(request.rel_url),
            user_agent=request.headers.get('User-Agent'),
            method=request.method,
            host=request.host,
            headers=dict(request.headers),
            text=lenient_json(request_text),
        ),
        response=dict(
            status=getattr(response, 'status', None), headers=dict(getattr(response, 'headers', {})), text=response_text
        ),
        **more,
    )

    tags = dict()
    user = dict(ip_address=get_ip(request))
    get_user = request.app.get('middleware_log_user')
    if get_user:
        try:
            user.update(await get_user(request))
        except Exception:
            logger.exception('error getting user for middleware logging')
    return dict(data=data, user=user, tags=tags)


async def log_warning(request, response):
    logger.warning(
        '%s unexpected response %d',
        request.rel_url,
        response.status,
        extra={'fingerprint': [request.rel_url, str(response.status)], **await log_extra(request, response)},
    )


def should_warn(r):
    return r.status > 310 and r.status not in {401, 404, 470}


def get_request_start(request):
    try:
        return float(request.headers.get('X-Request-Start', '.')) / 1000
    except ValueError:
        return time()


@middleware
async def error_middleware(request, handler):
    request['start_time'] = get_request_start(request)
    try:
        r = await handler(request)
    except HTTPException as e:
        should_warn_ = request.app.get('middleware_should_warn') or should_warn
        if should_warn_(e):
            await log_warning(request, e)
        raise
    except Exception as exc:
        logger.exception(
            '%s: %s',
            exc.__class__.__name__,
            exc,
            extra={
                'fingerprint': [exc.__class__.__name__, str(exc)],
                **await log_extra(request, exception_extra=exc_extra(exc)),
            },
        )
        raise HTTPInternalServerError()
    else:
        should_warn_ = request.app.get('middleware_should_warn') or should_warn
        if should_warn_(r):
            await log_warning(request, r)
    return r


@middleware
async def pg_middleware(request, handler):
    async with request.app['pg'].acquire() as conn:
        request['conn'] = conn
        return await handler(request)


def _path_match(request, paths):
    return any(p.fullmatch(request.path) for p in paths)


def csrf_checks(request, settings: BaseSettings):
    """
    content-type, origin and referrer checks for CSRF.

    Forces all non OPTIONS or GET requests to be json except upload paths
    """
    if request.method == METH_GET or _path_match(request, settings.csrf_ignore_paths):
        yield True
        return

    ct = request.headers.get('Content-Type', '')
    if _path_match(request, settings.csrf_upload_paths):
        yield ct.startswith('multipart/form-data; boundary')
    else:
        yield ct == JSON_CONTENT_TYPE

    origin = request.headers.get('Origin')
    path_root = request_root(request)
    if _path_match(request, settings.csrf_cross_origin_paths):
        yield origin == 'null' or origin is None or request.host.startswith('localhost')
    else:
        # origin and host ports differ on localhost when testing, so ignore this case
        yield origin == path_root or origin is None or request.host.startswith('localhost')

        # iframe requests don't include a referrer, thus this isn't checked for cross origin urls
        r = request.headers.get('Referer', '')
        yield r.startswith(path_root + '/')


@middleware
async def csrf_middleware(request, handler):
    settings: BaseSettings = request.app['settings']
    if request.method == METH_OPTIONS:
        if 'Access-Control-Request-Method' in request.headers:
            if (
                request.headers.get('Access-Control-Request-Method') == METH_POST
                and _path_match(request, settings.csrf_cross_origin_paths)
                and request.headers.get('Access-Control-Request-Headers').lower() == 'content-type'
            ):
                # can't check origin here as it's null since the iframe's requests are "cross-origin"
                headers = {'Access-Control-Allow-Headers': 'Content-Type', **HEADER_CROSS_ORIGIN}
                return Response(text='ok', headers=headers)
            else:
                raise JsonErrors.HTTPForbidden('Access-Control checks failed', headers=HEADER_CROSS_ORIGIN)
    elif not all(csrf_checks(request, settings)):
        raise JsonErrors.HTTPForbidden('CSRF failure', headers=HEADER_CROSS_ORIGIN)

    return await handler(request)
