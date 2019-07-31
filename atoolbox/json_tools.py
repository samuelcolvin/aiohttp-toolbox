import json

from pydantic.json import pydantic_encoder

JSON_CONTENT_TYPE = 'application/json'


def _isoformat(o):
    return o._isoformat()


def pretty_lenient_json(data):
    return json.dumps(data, indent=2, default=pydantic_encoder) + '\n'


def lenient_json(v):
    if isinstance(v, (str, bytes)):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            pass
    return v
