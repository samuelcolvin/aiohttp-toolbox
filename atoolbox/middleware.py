import contextlib
import logging
from time import time

from aiohttp.hdrs import METH_GET, METH_OPTIONS, METH_POST
from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
from aiohttp.web_middlewares import middleware
from aiohttp.web_response import Response
from aiohttp.web_urldispatcher import MatchInfoError
from yarl import URL

from .json_tools import lenient_json
from .settings import BaseSettings
from .utils import JSON_CONTENT_TYPE, JsonErrors, get_ip, remove_port, request_root

logger = logging.getLogger('atoolbox.middleware')
CROSS_ORIGIN_ANY = {'Access-Control-Allow-Origin': '*'}


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


async def log_warning(request, response, exc_info=False):
    logger.warning(
        '%s %s unexpected response %d',
        request.method,
        request.rel_url,
        response.status,
        exc_info=exc_info,
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
            await log_warning(request, e, exc_info=True)
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
        # TODO cope with case that r is not a response
        should_warn_ = request.app.get('middleware_should_warn') or should_warn
        if should_warn_(r):
            await log_warning(request, r)
    return r


@middleware
async def pg_middleware(request, handler):
    check = request.app.get('pg_middleware_check')
    if check and not check(request):
        return await handler(request)
    else:
        async with request.app['pg'].acquire() as conn:
            request['conn'] = conn
            return await handler(request)


def _path_match(request, paths):
    return any(p.fullmatch(request.path) for p in paths)


def csrf_checks(request, settings: BaseSettings):  # noqa: C901 (ignore complexity)
    """
    Content-Type, Origin and Referrer checks for CSRF.
    """
    if request.method == METH_GET or _path_match(request, settings.csrf_ignore_paths):
        return

    if isinstance(request.match_info, MatchInfoError):
        # let the other error 404 or 405 occur
        return

    ct = request.headers.get('Content-Type', '')
    if _path_match(request, settings.csrf_upload_paths):
        if not ct.startswith('multipart/form-data; boundary'):
            return 'upload path, wrong Content-Type'
    else:
        if not ct == JSON_CONTENT_TYPE:
            return 'Content-Type not application/json'

    if request.host.startswith('localhost:'):
        # avoid the faff of CSRF checks on localhost
        return

    origin = request.headers.get('Origin')
    if not origin:
        # being strict here and requiring Origin to be present, are there any cases where this breaks
        return 'Origin missing'

    origin = remove_port(origin)
    referrer = request.headers.get('Referer')
    if referrer:
        referrer_url = URL(referrer)
        referrer_root = remove_port(referrer_url.scheme + '://' + referrer_url.host)
    else:
        referrer_root = None

    if _path_match(request, settings.csrf_cross_origin_paths):
        # no origin is okay
        if not any(r.fullmatch(origin) for r in settings.cross_origin_origins):
            return 'Origin wrong'

        # iframe requests don't include a referrer
        if referrer_root is not None and not any(r.fullmatch(referrer_root) for r in settings.cross_origin_origins):
            return 'Referer wrong'
    else:
        path_root = remove_port(request_root(request))

        if origin != path_root:
            return 'Origin wrong'
        if referrer_root != path_root:
            return 'Referer wrong'


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
                headers = {'Access-Control-Allow-Headers': 'Content-Type', **CROSS_ORIGIN_ANY}
                return Response(text='ok', headers=headers)
            else:
                raise JsonErrors.HTTPForbidden('Access-Control checks failed', headers=CROSS_ORIGIN_ANY)
    else:
        csrf_error = csrf_checks(request, settings)
        if csrf_error:
            raise JsonErrors.HTTPForbidden('CSRF failure: ' + csrf_error, headers=CROSS_ORIGIN_ANY)

    return await handler(request)
