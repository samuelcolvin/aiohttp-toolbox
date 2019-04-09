async def test_spa(cli):
    r = await cli.get('/spa/')
    assert r.status == 200, await r.text()
    assert '<h1>this is the index page</h1>\n' == await r.text()
    assert r.headers['Content-Type'] == 'text/html'


async def test_spa_missing(cli):
    r = await cli.get('/spa/this-does-not-exist/')
    assert r.status == 200, await r.text()
    assert '<h1>this is the index page</h1>\n' == await r.text()
    assert r.headers['Content-Type'] == 'text/html'


async def test_spa_css(cli):
    r = await cli.get('/spa/foobar.css')
    assert r.status == 200, await r.text()
    assert 'body {background: black;}\n' == await r.text()
    assert r.headers['Content-Type'] == 'text/css'
