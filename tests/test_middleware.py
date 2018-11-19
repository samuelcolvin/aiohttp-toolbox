from aiohttptools.middleware import exc_extra


async def test_200(cli, caplog):
    r = await cli.get('/whatever')
    assert r.status == 200, await r.text()
    assert len(caplog.records) == 0


async def test_404_no_path(cli, caplog):
    r = await cli.get('/foo/bar/')
    assert r.status == 404, await r.text()
    assert len(caplog.records) == 0


async def test_500(cli, caplog):
    r = await cli.get('/500', data='foobar')
    assert r.status == 500, await r.text()
    assert 'custom 500 error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.data['request']['text'] == 'foobar'
    assert record.data['response']['text'] == 'custom 500 error'
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_not_unicode(cli, caplog):
    r = await cli.get('/500', data=b'\xff')
    assert r.status == 500, await r.text()
    assert 'custom 500 error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.data['request']['text'] is None
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_499(cli, caplog):
    r = await cli.get('/return_499')
    assert r.status == 499, await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_value_error(cli, caplog):
    r = await cli.get('/value_error')
    assert r.status == 500, await r.text()
    assert '500: Internal Server Error' == await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response', 'exception_extra'}
    assert record.data['exception_extra'] is None
    assert record.user == {'ip_address': '127.0.0.1'}
    assert record.tags == {}


async def test_user(cli, caplog):

    r = await cli.get('/user')
    assert r.status == 488, await r.text()
    assert len(caplog.records) == 1
    record = caplog.records[0]
    assert record.data.keys() == {'request_duration', 'request', 'response'}
    assert record.user == {'ip_address': '127.0.0.1'}
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
