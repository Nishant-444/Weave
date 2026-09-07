import logging
from typing import Any, Dict, List, Optional
from contextlib import asynccontextmanager
import asyncpg

from app.core.config import get_settings

logger = logging.getLogger("uvicorn.error")


class Database:
    """Thin hand-written asyncpg connection manager with raw SQL helpers."""

    def __init__(self) -> None:
        self.pool: Optional[asyncpg.Pool] = None

    async def connect(self) -> None:
        """Create database connection pool."""
        settings = get_settings()
        try:
            # Handle standard postgres:// scheme if provided by Supabase
            dsn = settings.database_url
            if dsn.startswith("postgres://"):
                dsn = dsn.replace("postgres://", "postgresql://", 1)

            # statement_cache_size=0 prevents PgBouncer / Supabase transaction pooler type introspection timeouts
            self.pool = await asyncpg.create_pool(
                dsn=dsn,
                min_size=1,
                max_size=10,
                command_timeout=60,
                statement_cache_size=0,
            )
            logger.info("Database connection pool established.")
        except Exception as e:
            logger.warning(f"Database connection failed on startup (can connect later): {e}")
            self.pool = None

    async def disconnect(self) -> None:
        """Close connection pool."""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database connection pool closed.")

    async def _ensure_pool(self) -> asyncpg.Pool:
        """Ensure connection pool is active, attempting reconnect if needed."""
        if not self.pool:
            await self.connect()
        if not self.pool:
            raise RuntimeError("Database connection is not available. Please check DATABASE_URL.")
        return self.pool

    async def fetch_all(self, query: str, *args: Any) -> List[Dict[str, Any]]:
        """Execute a query and return all rows as a list of dicts."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch(query, *args)
            return [dict(record) for record in records]

    async def fetch_one(self, query: str, *args: Any) -> Optional[Dict[str, Any]]:
        """Execute a query and return a single row as a dict, or None."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(query, *args)
            return dict(record) if record else None

    async def fetch_val(self, query: str, *args: Any) -> Any:
        """Execute a query and return a single scalar value."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    async def execute(self, query: str, *args: Any) -> str:
        """Execute a single query without returning rows."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    async def execute_many(self, query: str, args_list: List[tuple]) -> None:
        """Execute a query for multiple records in a batch."""
        if not args_list:
            return
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            await conn.executemany(query, args_list)

    @asynccontextmanager
    async def transaction(self):
        """Context manager for running multiple operations within a database transaction."""
        pool = await self._ensure_pool()
        async with pool.acquire() as conn:
            async with conn.transaction():
                yield conn

    async def check_health(self) -> Dict[str, Any]:
        """Verify DB connectivity."""
        # Intentional lazy reconnect-on-check behavior: allows the health endpoint
        # to recover if the database connection was temporarily unavailable at startup.
        if not self.pool:
            await self.connect()

        if not self.pool:
            return {
                "status": "unreachable",
                "error": "No database pool available",
            }

        try:
            async with self.pool.acquire() as conn:
                await conn.fetchval("SELECT 1")
                return {
                    "status": "connected",
                }
        except Exception as e:
            logger.error(f"Database health check query failed: {e}")
            settings = get_settings()
            err_msg = str(e) if settings.app_env != "production" else "Database query failed"
            return {
                "status": "unreachable",
                "error": err_msg,
            }


db = Database()
