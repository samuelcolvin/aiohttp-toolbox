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
    assert obj == {'message': 'Only GET, OPTIONS and POST requests are permitted.'}
    assert r.headers['Foobar'] == 'testing'
