import logging

from pydantic import BaseModel

from .exceptions import JsonErrors, RequestError
from .settings import GREPAPTCHA_TEST_SECRET, BaseSettings
from .utils import get_ip, remove_port

logger = logging.getLogger('atoolbox.auth')


async def check_grecaptcha(m: BaseModel, request, *, error_headers=None):
    settings: BaseSettings = request.app['settings']
    client_ip = get_ip(request)
    if not m.grecaptcha_token:
        logger.warning('grecaptcha not provided, path="%s" ip=%s', request.path, client_ip)
        raise JsonErrors.HTTPBadRequest(message='No recaptcha value', headers=error_headers)

    post_data = {'secret': settings.grecaptcha_secret, 'response': m.grecaptcha_token, 'remoteip': client_ip}
    async with request.app['http_client'].post(settings.grecaptcha_url, data=post_data) as r:
        if r.status != 200:
            raise RequestError(r.status, settings.grecaptcha_url, text=await r.text())
        data = await r.json()

    if data['success']:
        hostname = data['hostname']
        if remove_port(request.host) == hostname:
            logger.info('grecaptcha success')
        if hostname == 'testkey.google.com' and settings.grecaptcha_secret == GREPAPTCHA_TEST_SECRET:
            logger.info('grecaptcha test key success')
    else:
        logger.warning(
            'grecaptcha failure, path="%s" ip=%s response=%s',
            request.path,
            client_ip,
            data,
            extra={'data': {'grecaptcha_response': data}},
        )
        raise JsonErrors.HTTPBadRequest(message='Invalid recaptcha value', headers=error_headers)
