import string

from buildpg import MultipleValues, Values
from pytest_toolbox.comparison import AnyInt


async def test_list_empty(cli):
    r = await cli.get('/orgs/')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {'items': [], 'count': 0, 'pages': 0}


async def test_list_lots(cli, db_conn):
    orgs = [Values(name=f'Org {string.ascii_uppercase[i]}', slug=f'org-{i}') for i in range(7)]
    await db_conn.execute_b('INSERT INTO organisations (:values__names) VALUES :values', values=MultipleValues(*orgs))
    r = await cli.get('/orgs/')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {
        'items': [
            {'id': AnyInt(), 'name': 'Org A', 'slug': 'org-0'},
            {'id': AnyInt(), 'name': 'Org B', 'slug': 'org-1'},
            {'id': AnyInt(), 'name': 'Org C', 'slug': 'org-2'},
            {'id': AnyInt(), 'name': 'Org D', 'slug': 'org-3'},
            {'id': AnyInt(), 'name': 'Org E', 'slug': 'org-4'},
        ],
        'count': 7,
        'pages': 2,
    }
    r = await cli.get('/orgs/?page=2')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {
        'items': [
            {'id': AnyInt(), 'name': 'Org F', 'slug': 'org-5'},
            {'id': AnyInt(), 'name': 'Org G', 'slug': 'org-6'},
        ],
        'count': 7,
        'pages': 2,
    }


async def test_get(cli, db_conn):
    org_id = await db_conn.fetchval_b(
        'INSERT INTO organisations (:values__names) VALUES :values RETURNING id',
        values=Values(name='Test Org', slug='test-org'),
    )
    r = await cli.get(f'/orgs/{org_id}/')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {'id': org_id, 'name': 'Test Org', 'slug': 'test-org'}


async def test_create(cli, db_conn):
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM organisations')
    r = await cli.post_json('/orgs/add/', dict(name='Test Org', slug='whatever'))
    assert r.status == 201, await r.text()
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM organisations')
    data = await r.json()
    org = dict(await db_conn.fetchrow('SELECT * FROM organisations'))
    assert data == {'status': 'ok', 'pk': org.pop('id')}
    assert org == {'name': 'Test Org', 'slug': 'whatever'}


async def test_update(cli, db_conn):
    org_id = await db_conn.fetchval_b(
        'INSERT INTO organisations (:values__names) VALUES :values RETURNING id',
        values=Values(name='Test Org', slug='test-org'),
    )

    data = dict(name='Different')
    r = await cli.post_json(f'/orgs/{org_id}/', data)
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'status': 'ok'}
    assert 1 == await db_conn.fetchval('SELECT COUNT(*) FROM organisations')
    org = dict(await db_conn.fetchrow('SELECT * FROM organisations'))
    assert org == {'id': org_id, 'name': 'Different', 'slug': 'test-org'}


async def test_delete(cli, db_conn):
    org_id = await db_conn.fetchval_b(
        'INSERT INTO organisations (:values__names) VALUES :values RETURNING id',
        values=Values(name='Test Org', slug='test-org'),
    )

    r = await cli.post_json(f'/orgs/{org_id}/delete/')
    assert r.status == 200, await r.text()
    data = await r.json()
    assert data == {'message': f'item {org_id} deleted from organisations', 'pk': org_id}
    assert 0 == await db_conn.fetchval('SELECT COUNT(*) FROM organisations')


async def test_add_conflict(cli, db_conn):
    await db_conn.execute_b(
        'INSERT INTO organisations (:values__names) VALUES :values RETURNING id',
        values=Values(name='Test Org', slug='test-org'),
    )
    data = dict(name='Test Org', slug='test-org')
    r = await cli.post_json('/orgs/add/', data)
    assert r.status == 409, await r.text()
    obj = await r.json()
    assert obj == {
        'message': 'Conflict',
        'details': [
            {
                'loc': ['slug'],
                'msg': 'This value conflicts with an existing "slug", try something else.',
                'type': 'value_error.conflict',
            }
        ],
    }


async def test_update_conflict(cli, db_conn):
    orgs = [Values(name='Test Org 1', slug='test-org-1'), Values(name='Test Org 2', slug='test-org-2')]
    await db_conn.execute_b('INSERT INTO organisations (:values__names) VALUES :values', values=MultipleValues(*orgs))
    org_id = await db_conn.fetchval("select id from organisations where slug='test-org-2'")
    data = dict(slug='test-org-1')
    r = await cli.post_json(f'/orgs/{org_id}/', data)
    assert r.status == 409, await r.text()
    obj = await r.json()
    assert obj == {
        'message': 'Conflict',
        'details': [
            {
                'loc': ['slug'],
                'msg': 'This value conflicts with an existing "slug", try something else.',
                'type': 'value_error.conflict',
            }
        ],
    }


async def test_exec_view(cli):
    r = await cli.post_json('/exec/', {'pow': 3}, origin='null')
    assert r.status == 200, await r.text()
    obj = await r.json()
    assert obj == {'ans': 8}


async def test_invalid_page(cli):
    r = await cli.get('/orgs/?page=-1')
    assert r.status == 400, await r.text()
    obj = await r.json()
    assert obj == {'message': "invalid page '-1'"}
