import asyncio
import re


class SimplePgPool:
    """
    dummy connection pool useful for testing.
    """

    def __init__(self, conn):
        self.conn = conn
        # could also add lock to each method of the returned connection
        self._lock = asyncio.Lock(loop=self.conn._loop)

    def acquire(self):
        return self

    async def __aenter__(self):
        return self.conn

    async def execute(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.execute(*args, **kwargs)

    async def fetch(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.fetch(*args, **kwargs)

    async def fetchval(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.fetchval(*args, **kwargs)

    async def fetchrow(self, *args, **kwargs):
        async with self._lock:
            return await self.conn.fetchrow(*args, **kwargs)

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass

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
