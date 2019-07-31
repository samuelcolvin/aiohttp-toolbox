import json
import re
from typing import Any, Tuple, Type, TypeVar, Union

from aiohttp.web import Response
from pydantic import BaseModel, ValidationError, validate_model
from pydantic.fields import Shape

from .exceptions import JsonErrors
from .json_tools import JSON_CONTENT_TYPE

IP_HEADER = 'X-Forwarded-For'
PROTO_HEADER = 'X-Forwarded-Proto'
URI_NOT_ALLOWED = re.compile(r'[^a-zA-Z0-9_\-/.]')
REMOVE_PORT = re.compile(r':\d{2,}$')
PydanticModel = TypeVar('PydanticModel', bound=BaseModel)

__all__ = (
    'raw_json_response',
    'json_response',
    'parse_request_json',
    'parse_request_json_ignore_missing',
    'parse_request_query',
    'get_ip',
    'request_root',
    'encrypt_json',
    'decrypt_json',
    'get_offset',
    'slugify',
    'remove_port',
)


def raw_json_response(json_str: Union[str, bytes, None], status_: int = 200):
    if isinstance(json_str, str):
        body = json_str.encode()
    elif isinstance(json_str, bytes):
        body = json_str
    elif json_str is None:
        body = b'null'
    else:
        raise TypeError(f'json_str must be bytes or str, not "{type(json_str)}')
    return Response(body=body + b'\n', status=status_, content_type=JSON_CONTENT_TYPE)


def json_response(*, status_=200, list_=None, headers_=None, **data):
    return Response(
        body=json.dumps(data if list_ is None else list_).encode() + b'\n',
        status=status_,
        content_type=JSON_CONTENT_TYPE,
        headers=headers_,
    )


async def parse_request_json(request, model: Type[PydanticModel], *, headers=None) -> PydanticModel:
    error_details = None
    try:
        data = await request.json()
    except ValueError:
        error_msg = 'Invalid JSON'
    else:
        try:
            return model.parse_obj(data)
        except ValidationError as e:
            error_msg = 'Invalid Data'
            error_details = e.errors()

    raise JsonErrors.HTTPBadRequest(message=error_msg, details=error_details, headers=headers)


def parse_request_query(request, model: Type[PydanticModel], *, headers=None) -> PydanticModel:
    data = {}
    for k in request.query:
        v = request.query.getall(k)
        f = model.__fields__.get(k)
        if len(v) > 1 or f and f.shape != Shape.SINGLETON:
            data[k] = v
        else:
            data[k] = v[0]

    try:
        return model(**data)
    except ValidationError as e:
        raise JsonErrors.HTTPBadRequest(message='Invalid query data', details=e.errors(), headers=headers)


async def parse_request_json_ignore_missing(
    request, model: Type[PydanticModel], *, headers=None
) -> Tuple[PydanticModel, dict]:
    try:
        raw_data = await request.json()
    except ValueError:
        raise JsonErrors.HTTPBadRequest(message='Invalid JSON', headers=headers)
    if not isinstance(raw_data, dict):
        raise JsonErrors.HTTPBadRequest(message='data not a dictionary', headers=headers)

    data, _, e = validate_model(model, raw_data, raise_exc=False)
    if e:
        errors = [e for e in e.errors() if not (e['type'] == 'value_error.missing' and len(e['loc']) == 1)]
        if errors:
            raise JsonErrors.HTTPBadRequest(message='Invalid Data', details=errors, headers=headers)

    return model.construct(values=data, fields_set=set(data.keys())), raw_data


def get_ip(request):
    ips = request.headers.get(IP_HEADER)
    if ips:
        return ips.split(',', 1)[0].strip(' ')
    else:
        return request.remote


def request_root(request):
    # request.url.scheme doesn't work as https is already terminated
    scheme = request.headers.get(PROTO_HEADER) or 'http'
    return f'{scheme}://{request.host}'


def encrypt_json(app, data: Any) -> str:
    return app['auth_fernet'].encrypt(json.dumps(data).encode()).decode()


def decrypt_json(app, token: bytes, *, ttl: int = None, headers=None) -> Any:
    from cryptography.fernet import InvalidToken

    try:
        return json.loads(app['auth_fernet'].decrypt(token, ttl=ttl).decode())
    except InvalidToken:
        raise JsonErrors.HTTPBadRequest(message='invalid token', headers=headers)


def get_offset(request, paginate_by=100):
    page = request.query.get('page')
    if not page:
        return 0

    try:
        p = int(page)
        if p < 1:
            raise ValueError()
    except ValueError:
        raise JsonErrors.HTTPBadRequest(f"invalid page '{page}'")
    else:
        return (p - 1) * paginate_by


def slugify(title):
    name = title.replace(' ', '-').lower()
    name = URI_NOT_ALLOWED.sub('', name)
    name = re.sub('-{2,}', '-', name)
    return name.strip('_-')


def remove_port(host):
    return REMOVE_PORT.sub('', host)
