import datetime
import json
from decimal import Decimal
from uuid import UUID


def _isoformat(o):
    return o._isoformat()


class UniversalEncoder(json.JSONEncoder):
    ENCODER_BY_TYPE = {
        UUID: str,
        datetime.datetime: _isoformat,
        datetime.date: _isoformat,
        datetime.time: _isoformat,
        set: list,
        frozenset: list,
        bytes: lambda o: o.decode(),
        Decimal: str,
    }

    def default(self, obj):
        try:
            encoder = self.ENCODER_BY_TYPE[type(obj)]
        except KeyError:
            return super().default(obj)
        return encoder(obj)


def pretty_lenient_json(data):
    return json.dumps(data, indent=2, cls=UniversalEncoder) + '\n'


def lenient_json(v):
    if isinstance(v, (str, bytes)):
        try:
            return json.loads(v)
        except (ValueError, TypeError):
            pass
    return v
