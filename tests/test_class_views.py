async def test_post(cli):
    r = await cli.post_json('/exec/', {'pow': 3}, origin='null')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {'ans': 8}
    assert r.headers['Foobar'] == 'testing'


async def test_get(cli):
    r = await cli.get('/exec/')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {
        'title': 'Model',
        'type': 'object',
        'properties': {'pow': {'title': 'Pow', 'type': 'integer'}},
        'required': ['pow'],
    }
    assert r.headers['Foobar'] == 'testing'


async def test_options(cli):
    r = await cli.options('/exec/')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {
        'title': 'Model',
        'type': 'object',
        'properties': {'pow': {'title': 'Pow', 'type': 'integer'}},
        'required': ['pow'],
    }
    assert r.headers['Foobar'] == 'testing'


async def test_put(cli):
    r = await cli.put(
        '/exec/',
        data='{}',
        headers={
            'Content-Type': 'application/json',
            'Referer': f'http://127.0.0.1:{cli.server.port}/foobar/',
            'Origin': f'http://127.0.0.1:{cli.server.port}',
        },
    )
    assert r.status == 405, await r.text()
    obj = await r.json()
    assert obj == {'message': 'Method not permitted.', 'details': {'allowed_methods': ['GET', 'OPTIONS', 'POST']}}
    assert r.headers['Foobar'] == 'testing'


async def test_error(cli):
    r = await cli.post_json('/exec/', {'pow': -2}, origin='null')
    assert r.status == 470, await r.text()
    obj = await r.json()
    assert obj == {'message': 'values less than 1 no allowed'}
    assert r.headers['Foobar'] == 'testing'


async def test_no_headers(cli):
    r = await cli.post_json('/exec-simple/', {'v': 'ping'}, origin='null')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {'ans': 'pong'}
    assert r.headers.keys() == {'Content-Type', 'Content-Length', 'Date', 'Server'}


async def test_no_headers_error(cli):
    r = await cli.post_json('/exec-simple/', {'v': 'x'}, origin='null')
    assert r.status == 400, await r.text()
    obj = await r.json()
    assert obj == {
        'message': 'Invalid Data',
        'details': [
            {
                'loc': ['v'],
                'msg': "value is not a valid enumeration member; permitted: 'ping', 'pong'",
                'type': 'type_error.enum',
                'ctx': {'enum_values': ['ping', 'pong']},
            }
        ],
    }
    assert r.headers.keys() == {'Content-Type', 'Content-Length', 'Date', 'Server'}
