import logging

from pydantic import BaseModel

from .settings import BaseSettings
from .utils import JsonErrors, RequestError, get_ip, remove_port

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

    if data['success'] and remove_port(request.host) == data['hostname']:
        logger.info('grecaptcha success')
    else:
        logger.warning(
            'grecaptcha failure, path="%s" ip=%s response=%s',
            request.path,
            client_ip,
            data,
            extra={'data': {'grecaptcha_response': data}},
        )
        raise JsonErrors.HTTPBadRequest(message='Invalid recaptcha value', headers=error_headers)
