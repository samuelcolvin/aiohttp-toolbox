import asyncio
import re

from asyncpg import Connection


class _LockedExecute:
    def __init__(self, conn, lock=None):
        self._conn: Connection = conn
        # could also add lock to each method of the returned connection
        self._lock: asyncio.Lock = lock or asyncio.Lock(loop=self._conn._loop)

    async def execute(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.execute(*args, **kwargs)

    async def execute_b(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.execute_b(*args, **kwargs)

    async def fetch(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.fetch(*args, **kwargs)

    async def fetch_b(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.fetch_b(*args, **kwargs)

    async def fetchval(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.fetchval(*args, **kwargs)

    async def fetchval_b(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.fetchval_b(*args, **kwargs)

    async def fetchrow(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.fetchrow(*args, **kwargs)

    async def fetchrow_b(self, *args, **kwargs):
        async with self._lock:
            return await self._conn.fetchrow_b(*args, **kwargs)


class DummyPgTransaction(_LockedExecute):
    _tr = None

    async def __aenter__(self):
        async with self._lock:
            self._tr = self._conn.transaction()
            await self._tr.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        async with self._lock:
            if exc_type:
                await self._tr.rollback()
            else:
                await self._tr.commit()
            self._tr = None


class DummyPgConn(_LockedExecute):
    def transaction(self):
        return DummyPgTransaction(self._conn, self._lock)


class _ConnAcquire:
    def __init__(self, conn, lock):
        self._conn: Connection = conn
        self._lock: asyncio.Lock = lock

    async def __aenter__(self):
        return DummyPgConn(self._conn, self._lock)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass


class DummyPgPool(DummyPgConn):
    """
    dummy connection pool useful for testing, only one connection is used, but this will behave like
    Connection or BuildPgConnection, including locking before using the underlying connection.
    """

    def acquire(self):
        return _ConnAcquire(self._conn, self._lock)

    async def close(self):
        pass


async def update_enums(enums, conn):
    """
    update sql enums from python enums, this requires @patch(direct=True) on the patch
    """
    for name, enum in enums.items():
        for t in enum:
            await conn.execute(f"ALTER TYPE {name} ADD VALUE IF NOT EXISTS '{t.value}'")


async def run_sql_section(chunk_name, sql, conn):
    """
    Run a section of a sql string (eg. settings.sql) based on tags in the following format:
        -- { <chunk name>
        <sql to run>
        -- } <chunk name>
    """
    m = re.search(f'^-- *{{+ *{chunk_name}(.*)^-- *}}+ *{chunk_name}', sql, flags=re.DOTALL | re.MULTILINE)
    if not m:
        raise RuntimeError(f'chunk with name "{chunk_name}" not found')
    sql = m.group(1).strip(' \n')
    await conn.execute(sql)
