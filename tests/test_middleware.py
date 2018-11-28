from aiohttp import FormData

from atoolbox.middleware import exc_extra


async def test_200(cli, caplog):
    r = await cli.get('/errors/whatever')
    assert r.status == 200, await r.text()
    assert len(caplog.records) == 0


async def test_404_no_path(cli, caplog):
    r = await cli.get('/errors/foo/bar/')
    assert r.status == 404, await r.text()
    assert len(caplog.records) == 0


async def test_500(cli, caplog):
    r = await cli.get('/errors/500', data='foobar')
    assert r.status == 500, await r.text()
    assert 'custom 500 error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.data['request']['text'] == 'foobar'
    assert record.data['response']['text'] == 'custom 500 error'
    assert record.user == {'ip_address': '127.0.0.1', 'username': 'foobar'}
    assert record.tags == {}


async def test_not_unicode(cli, caplog):
    r = await cli.get('/errors/500', data=b'\xff')
    assert r.status == 500, await r.text()
    assert 'custom 500 error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.data['request']['text'] is None
    assert record.user == {'ip_address': '127.0.0.1', 'username': 'foobar'}
    assert record.tags == {}


async def test_499(cli, caplog):
    r = await cli.get('/errors/return_499')
    assert r.status == 499, await r.text()
    assert len(caplog.records) == 2
    record = caplog.records[1]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_value_error(cli, caplog):
    r = await cli.get('/errors/value_error')
    assert r.status == 500, await r.text()
    assert '500: Internal Server Error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response', 'exception_extra'}
    assert record.data['exception_extra'] is None
    assert record.user == {'ip_address': '127.0.0.1', 'username': 'foobar'}
    assert record.tags == {}


async def test_user(cli, caplog):
    r = await cli.get('/user')
    assert r.status == 488, await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.user == {'ip_address': '127.0.0.1', 'username': 'foobar'}
    assert record.tags == {}


def test_exc_extra_ok():
    class Foo(Exception):
        def extra(self):
            return {'x': 1}

    assert exc_extra(Foo()) == {'x': 1}


def test_exc_extra_error():
    class Foo(Exception):
        def extra(self):
            raise RuntimeError()

    assert exc_extra(Foo()) is None


async def test_csrf_no_path(cli):
    r = await cli.post('/orgs/add/', data='null')
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: Content-Type not application/json'}


async def test_csrf_failure_ct(cli):
    r = await cli.post('/orgs/add/foobar', data='null')
    assert r.status == 404, await r.text()


async def test_csrf_failure_origin_missing(cli):
    r = await cli.post('/orgs/add/', data='null', headers={'Content-Type': 'application/json'})
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: Origin missing'}


async def test_csrf_failure_origin_wrong(cli):
    h = {'Content-Type': 'application/json', 'Origin': 'http://example.com'}
    r = await cli.post('/orgs/add/', data='null', headers=h)
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: Origin wrong'}


async def test_csrf_failure_origin_wrong_cross(cli):
    h = {'Content-Type': 'application/json', 'Origin': 'http://example.com'}
    r = await cli.post('/exec/', data='null', headers=h)
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: Origin wrong'}


async def test_csrf_failure_referer(cli):
    h = {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1'}
    r = await cli.post('/orgs/add/', data='null', headers=h)
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: Referer wrong'}


async def test_csrf_failure_referer_cross(cli):
    h = {'Content-Type': 'application/json', 'Origin': 'http://127.0.0.1', 'Referer': 'http://whatever.com'}
    r = await cli.post('/exec/', data='null', headers=h)
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: Referer wrong'}


async def test_csrf_failure_upload(cli):
    r = await cli.post('/upload-path/', data='null')
    assert r.status == 403, await r.text()
    obj = await r.json()
    assert obj == {'message': 'CSRF failure: upload path, wrong Content-Type'}


async def test_csrf_ok_upload(cli):
    data = FormData()
    data.add_field('image', b'xxxx', filename='testing.png', content_type='application/octet-stream')
    r = await cli.post(
        '/upload-path/',
        data=data,
        headers={
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 200, await r.text()


async def test_preflight_ok(cli):

    headers = {'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'Content-Type'}
    r = await cli.options('/exec/', headers=headers)
    assert r.status == 200, await r.text()
    assert r.headers['Access-Control-Allow-Headers'] == 'Content-Type'
    assert r.headers['Access-Control-Allow-Origin'] == '*'
    t = await r.text()
    assert t == 'ok'


async def test_preflight_failed(cli):

    headers = {'Access-Control-Request-Method': 'POST', 'Access-Control-Request-Headers': 'xxx'}
    r = await cli.options('/exec/', headers=headers)
    assert r.status == 403, await r.text()
    assert 'Access-Control-Allow-Headers' not in r.headers
    assert r.headers['Access-Control-Allow-Origin'] == '*'
    obj = await r.json()
    assert obj == {'message': 'Access-Control checks failed'}
