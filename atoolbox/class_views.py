from asyncio import shield
from functools import update_wrapper
from typing import TYPE_CHECKING, Dict, Type

from aiohttp import web
from aiohttp.hdrs import METH_GET, METH_OPTIONS, METH_POST
from aiohttp.web_exceptions import HTTPException
from pydantic import BaseModel

from .utils import JsonErrors, json_response, parse_request_json

if TYPE_CHECKING:  # pragma: no cover
    from buildpg.asyncpg import BuildPgConnection  # noqa
    from aioredis import Redis


class View:
    __slots__ = 'request', 'app', 'conn', 'redis', 'settings'

    def __init__(self, request):
        self.request: web.Request = request
        self.app: web.Application = request.app
        self.conn: 'BuildPgConnection' = request.get('conn')
        self.redis: 'Redis' = self.app.get('redis')
        self.settings = self.app['settings']

    @classmethod
    def view(cls):
        async def view(request):
            self: cls = cls(request)
            await self.check_permissions()
            return await self.call()

        view.view_class = cls

        # take name and docstring from class
        update_wrapper(view, cls, updated=())
        # and possible attributes set by decorators
        update_wrapper(view, cls.call, assigned=())
        return view

    async def check_permissions(self):
        pass

    async def call(self):
        raise NotImplementedError


class ExecView(View):
    Model: Type[BaseModel] = NotImplemented
    headers: Dict[str, str] = None

    async def execute(self, m: Model):
        raise NotImplementedError

    async def get(self):
        return json_response(**self.Model.schema())

    async def options(self):
        return json_response(**self.Model.schema())

    async def post(self):
        m = await parse_request_json(self.request, self.Model)
        response_data = await shield(self.execute(m))
        response_data = response_data or {'status': 'ok'}
        return json_response(**response_data)

    def build_headers(self):
        return self.headers

    async def call(self):
        try:
            if self.request.method == METH_OPTIONS:
                response = await self.options()
            elif self.request.method == METH_GET:
                response = await self.get()
            elif self.request.method == METH_POST:
                response = await self.post()
            else:
                raise JsonErrors.HTTPMethodNotAllowed('Method not permitted.', [METH_GET, METH_OPTIONS, METH_POST])
        except HTTPException as exc:
            headers = self.build_headers()
            if headers:
                exc.headers.update(headers)
                raise exc from exc
            else:
                raise
        else:
            headers = self.build_headers()
            if headers:
                response.headers.update(headers)
            return response
