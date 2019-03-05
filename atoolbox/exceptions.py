import json

from aiohttp.web_exceptions import HTTPException

from .json_tools import JSON_CONTENT_TYPE, pretty_lenient_json


class JsonErrors:
    class _HTTPExceptionJson(HTTPException):
        custom_reason = None

        def __init__(self, message, *, details=None, headers=None):
            self.message = message
            self.details = details
            data = {'message': message}
            if details:
                data['details'] = details
            super().__init__(
                text=pretty_lenient_json(data),
                content_type=JSON_CONTENT_TYPE,
                headers=headers,
                reason=self.custom_reason,
            )

        def __repr__(self) -> str:
            return f'{super().__repr__()}, {self.status}: {self.message}'

        def __str__(self) -> str:
            return repr(self)

    class HTTPAccepted(_HTTPExceptionJson):
        status_code = 202

    class HTTPBadRequest(_HTTPExceptionJson):
        status_code = 400

    class HTTPUnauthorized(_HTTPExceptionJson):
        status_code = 401

    class HTTPPaymentRequired(_HTTPExceptionJson):
        status_code = 402

    class HTTPForbidden(_HTTPExceptionJson):
        status_code = 403

    class HTTPNotFound(_HTTPExceptionJson):
        status_code = 404

    class HTTPMethodNotAllowed(_HTTPExceptionJson):
        status_code = 405

        def __init__(self, message, allowed_methods, *, headers=None):
            headers = headers or {}
            headers.setdefault('Allow', ','.join(allowed_methods))
            super().__init__(message, details={'allowed_methods': allowed_methods}, headers=headers)

    class HTTPConflict(_HTTPExceptionJson):
        status_code = 409

    class HTTP470(_HTTPExceptionJson):
        status_code = 470
        custom_reason = 'Invalid user input'


class RequestError(RuntimeError):
    def __init__(self, status, url, *, text: str = None):
        self.status = status
        self.url = url
        self.text = text

    def __str__(self):
        return f'response {self.status} from "{self.url}"' + (f':\n{self.text[:400]}' if self.text else '')

    def json(self):
        return json.loads(self.text)

    def extra(self):
        return self.text
