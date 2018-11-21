async def test_grecaptcha_ok(cli, dummy_server):
    data = {'v': 4, 'grecaptcha_token': '__ok__'}
    assert dummy_server.log == []
    r = await cli.post_json('/grecaptcha/', data=data)
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {'v_squared': 16}
    assert dummy_server.log == ['grecaptcha __ok__']


async def test_grecaptcha_wrong(cli, dummy_server):
    data = {'v': 4, 'grecaptcha_token': 'wrong'}
    r = await cli.post_json('/grecaptcha/', data=data)
    assert r.status == 400, await r.text()
    obj = await r.json()
    assert obj == {'message': 'Invalid recaptcha value'}
    assert dummy_server.log == ['grecaptcha wrong']


async def test_grecaptcha_missing(cli, dummy_server):
    data = {'v': 4, 'grecaptcha_token': ''}
    r = await cli.post_json('/grecaptcha/', data=data)
    assert r.status == 400, await r.text()
    obj = await r.json()
    assert obj == {'message': 'No recaptcha value'}
    assert dummy_server.log == []


async def test_grecaptcha_400(cli, dummy_server):
    data = {'v': 4, 'grecaptcha_token': '__400__'}
    r = await cli.post_json('/grecaptcha/', data=data)
    assert r.status == 500, await r.text()
